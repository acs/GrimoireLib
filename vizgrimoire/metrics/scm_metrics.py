## Copyright (C) 2014 Bitergia
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
##
## This file is a part of GrimoireLib
##  (an Python library for the MetricsGrimoire and vizGrimoire systems)
##
##
## Authors:
##   Daniel Izquierdo-Cortazar <dizquierdo@bitergia.com>
##   Alvaro del Castillo  <acs@bitergia.com>
##


import logging
import MySQLdb

import re, sys

from vizgrimoire.GrimoireUtils import completePeriodIds, GetDates, GetPercentageDiff, check_array_values, checkListArray

from vizgrimoire.metrics.metrics import Metrics

from vizgrimoire.metrics.metrics_filter import MetricFilters

from vizgrimoire.metrics.query_builder import SCMQuery

from vizgrimoire.SCM import SCM

from sets import Set


class InitialActivity(Metrics):
    """ For the given dates of activity, this returns the first trace found
    """

    id = "first_date"
    name = "First activity date"
    desc = "First commit between the two provided dates"
    data_source = SCM

    def get_agg(self):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("DATE_FORMAT(min(s.author_date),'%Y-%m-%d') as first_date")

        tables.add("scmlog s")
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        filters.union_update(self.db.GetSQLReportWhere(self.filters))

        query = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                                   self.filters.enddate, "s.author_date", fields,
                                   tables, filters, False,
                                   self.filters.type_analysis)
        return self.db.ExecuteQuery(query)

class EndOfActivity(Metrics):
    """ For the given dates of activity, this returns the last trace found
    """
    id = "last_date"
    name = "Last activity date"
    desc = "Last commit between the two provided dates"
    data_source = SCM

    def get_agg(self):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("DATE_FORMAT(max(s.author_date),'%Y-%m-%d') as last_date")

        tables.add("scmlog s")
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        filters.union_update(self.db.GetSQLReportWhere(self.filters))

        query = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                                   self.filters.enddate, "s.author_date", fields,
                                   tables, filters, False,
                                   self.filters.type_analysis)

        return self.db.ExecuteQuery(query)


class Commits(Metrics):
    """ Commits metric class for source code management systems """

    id = "commits"
    name = "Commits"
    desc = "Changes to the source code"
    envision = {"y_labels" : "true",
                "show_markers" : "true" }
    data_source = SCM

    def _get_sql(self, evolutionary):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(s.rev)) as commits")

        tables.add("scmlog s")
        tables.add("(select distinct(a.commit_id) as id from actions a) nomergers")
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        filters.add("s.id = nomergers.id")
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        query = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                                   self.filters.enddate, " s.author_date ", fields,
                                   tables, filters, evolutionary, self.filters.type_analysis)
        return query


class NewAuthors(Metrics):
    """ A new author comes to the community when her first commit is detected

        By definition a new author joins the Git community when her first patchset
        has landed into the code. This is calculated as the minimum date found in
        the database for her actions.
    """

    id = "newauthors"
    name = "New Authors"
    desc = "New authors joining the community"
    data_source = SCM

    def _get_sql_generic(self, evolutionary, islist = False):

        fields = Set([])
        tables = Set([])
        filters = Set([])

        if not islist:
            fields.add("count(distinct(t.uuid)) as newauthors")
        else:
            fields.add("t.uuid as uid, p.name, p.email, t.date")
        tables.add("scmlog s")
        tables.add("people_uidentities pup")
        tables.add("people p")
        tables.add("""(select pup.uuid as uuid, min(s.author_date) as date
                       from people_uidentities pup, scmlog s
                       where s.author_id=pup.people_id
                       group by pup.uuid) t
                   """)
        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        filters.add("s.author_id = pup.people_id")
        filters.add("pup.uuid=t.uuid")
        filters.add("pup.people_id=p.id")
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " t.date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        if islist:
            q += " GROUP BY t.uuid "
            if not evolutionary: q += " ORDER BY t.date DESC"

        return q

    def _get_sql(self, evolutionary):
        return self._get_sql_generic(evolutionary)

    def get_list(self):
        q = self._get_sql_generic(None, True)
        data = self.db.ExecuteQuery(q)
        return data


class GoneAuthors(Metrics):
    """ An author has left the community after some time without activity

        That activiy is measured as number of commits. By default, 180 days
        are the timeframe selected for a developer to indicate that they have
        not been active during such period.

        This class only provides information about the set of developers that
        were active in the previous period of the same amount of "days" and
        that did not leave any trace of information during the last amount
        of "days".

        Period (1) looking for all active developers:
            (self.enddate - days - days) : (self.endate - days)

        Period (2) looking for no-active developers (those that were active
        in (1) and not in (2)):
            (self.enddate - days) : (self.enddate)

        This class is not using unique identities core table given that we
        specifically need the last email and name used by the developer.
        However, when using that table, that information is not assured.
    """

    id = "goneauthors"
    name = "Authors leaving the community"
    desc = "Authors leaving the community"
    data_source = SCM

    def _get_sql_generic(self, evolutionary, islist = False, days = 180):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        # Defining intervals of analysis
        interval = str(days)
        prev_interval = str(days * 2)

        if islist:
            fields.add("pup.uuid")
            fields.add("p.name")
            fields.add("p.email")
            fields.add("max(author_date) as last_activity")
        else:
            fields.add("count(distinct(pup.uuid))")

        tables.add("scmlog s")
        tables.add("people_uidentities pup")
        tables.add("people p")
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        filters.add("s.author_id = pup.people_id")
        filters.add("pup.people_id = p.id")
        filters.add("s.author_date >= DATE_SUB(%s, INTERVAL %s DAY)" % (self.filters.enddate, prev_interval))
        filters.add("s.author_date < DATE_SUB(%s, INTERVAL %s DAY)" % (self.filters.enddate, interval))
        filters.union_update(self.db.GetSQLReportWhere(self.filters))

        # Building subquery
        fields_sq = Set([]) #fields in the subquery
        tables_sq = Set([]) #tables in the subquery
        filters_sq = Set([]) #filters in the subquery

        fields_sq.add("distinct(pup.uuid)")

        tables_sq.add("scmlog s")
        tables_sq.add("people_uidentities pup")
        tables_sq.union_update(self.db.GetSQLReportFrom(self.filters))

        filters_sq.add("s.author_id = pup.people_id")
        filters_sq.add("s.author_date >= DATE_SUB(%s, INTERVAL %s DAY)" % (self.filters.enddate, interval))
        filters_sq.add("s.author_date < %s" % (self.filters.enddate))
        filters_sq.union_update(self.db.GetSQLReportWhere(self.filters))

        subquery = "select " + self.db._get_fields_query(fields_sq)
        subquery += " from " + self.db._get_tables_query(tables_sq)
        subquery += " where " + self.db._get_filters_query(filters_sq)

        # Building main query
        filters.add("pup.uuid not in (%s)" % (subquery))

        query = "select " + self.db._get_fields_query(fields)
        query += " from " + self.db._get_tables_query(tables)
        query += " where " + self.db._get_filters_query(filters)

        if islist:
            query += " group by pup.uuid "
            query += " order by last_activity desc "

        return query

    def get_agg(self):
        query = self._get_sql_generic(False)
        return self.db.ExecuteQuery(query)

    def get_ts(self):
       raise NotImplementedError

    def get_list(self):
        query = self._get_sql_generic(False, True)
        return self.db.ExecuteQuery(query)


class Authors(Metrics):
    """ Authors metric class for source code management systems """

    id = "authors"
    name = "Authors"
    desc = "People authoring commits (changes to source code)"
    envision = {"gtype" : "whiskers"}
    action = "commits"
    data_source = SCM

    def _get_sql (self, evolutionary):
        # This function contains basic parts of the query to count authors
        # That query is later built and executed
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(pup.uuid)) as authors")
        tables.add("scmlog s")
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        #specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        # This may be redundant code. However this is needed for specific analysis
        # such as repositories or projects. Given that we're using sets, this is not
        # an issue. Not repeated tables or filters will appear in the final query.
        tables.add("people_uidentities pup")
        filters.add("s.author_id = pup.people_id")

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q


    def get_list (self, metric_filters = None, days = 0):

        fields = Set([])
        tables = Set([])
        filters = Set([])

        #TODO: Code to be removed after report tool properly works
        new_filters = False
        old_filters = None
        if metric_filters is not None:
            old_filters = self.filters
            self.filters = metric_filters
            self.filters.people_out = old_filters.people_out
            new_filters = True
        #TODO: End of the code to be removed

        #Building parts of the query to control timeframe of study
        if (days > 0):
            tables.add("(SELECT MAX(date) as last_date from scmlog) dt")
            filters.add("DATEDIFF (last_date, date) < %s " % (days))

        #Building core part of the query.
        fields.add("u.uuid as id")
        fields.add("pro.name as authors")
        fields.add("count(distinct(s.id)) as commits")

        tables.add("scmlog s")
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        #specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        # This may be redundant code. However this is needed for specific analysis
        # such as repositories or projects. Given that we're using sets, this is not
        # an issue. Not repeated tables or filters will appear in the final query.
        tables.add("people_uidentities pup")
        tables.add(self.db.identities_db + ".uidentities u")
        tables.add(self.db.identities_db + ".profiles pro")
        filters.add("s.author_id = pup.people_id")
        filters.add("pup.uuid = u.uuid")
        filters.add("pup.uuid = pro.uuid")

        query = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                                   self.filters.enddate, " s.author_date ", fields,
                                   tables, filters, False, self.filters.type_analysis)

        query = query + " group by u.uuid "
        query = query + " order by count(distinct(s.id)) desc, pro.name "
        query = query + " limit " + str(self.filters.npeople)

        data = self.db.ExecuteQuery(query)
        for id in data:
            if not isinstance(data[id], (list)): data[id] = [data[id]]

        #TODO: Code to be removed after report tool properly works
        if new_filters:
            self.filters = old_filters
        #TODO: End of code to be removed

        return data

    def _get_top_supported_filters(self):
        return ['repository','company','project']


class People(Metrics):
    """ People filter metric class for source code management systems """

    id = "people2" # people is used yet for all partial filter
    name = "People"
    desc = "People authoring commits (changes to source code)"
    envision = {"gtype" : "whiskers"}
    action = "commits"
    data_source = SCM

    def _get_sql (self, evolutionary):
        """ Implemented using Authors """
        authors = SCM.get_metrics("authors", SCM)
        if authors is None:
            authors = Authors(self.db, self.filters)
            q = authors._get_sql(evolutionary)
        else:
            afilters = authors.filters
            authors.filters = self.filters
            q = authors._get_sql(evolutionary)
            authors.filters = afilters
        return q

    def _get_top_global (self, days = 0, metric_filters = None):
        """ Implemented using Authors """
        top = None
        authors = SCM.get_metrics("authors", SCM)
        if authors is None:
            authors = Authors(self.db, self.filters)
            top = authors._get_top_global(days, metric_filters)
        else:
            afilters = authors.filters
            authors.filters = self.filters
            top = authors._get_top_global(days, metric_filters)
            authors.filters = afilters
        top['name'] = top.pop('authors')
        return top

class Committers(Metrics):
    """ Committers metric class for source code management system """

    id = "committers"
    name = "Committers"
    desc = "Number of developers committing (merging changes to source code)"
    envision = {"gtype" : "whiskers"}
    action = "commits"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # This function contains basic parts of the query to count committers

        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(pup.uuid)) as committers")
        tables.add("scmlog s")
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "committer"))

        #specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        if (self.filters.type_analysis is None or len (self.filters.type_analysis) != 2) :
            #Specific case for the basic option where people_upeople table is needed
            #and not taken into account in the initial part of the query
            if "people_uidentities pup" not in tables:
                tables.add("people_uidentities pup")
                filters.add("s.committer_id = pup.people_id")

        elif (self.filters.type_analysis[0] == "repository" or self.filters.type_analysis[0] == "project"):
            #Adding people_upeople table
            if "people_uidentities pup" not in tables:
                tables.add("people_uidentities pup")
                filters.add("s.committer_id = pup.people_id")

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)

        return q


class Files(Metrics):
    """ Files metric class for source code management system """

    id = "files"
    name = "Files"
    desc = "Number of files 'touched' (added, modified, removed, ) by at least one commit"
    data_source = SCM

    def _get_sql(self, evolutionary):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(a.file_id)) as files")
        tables.add("scmlog s")
        tables.add("actions a")
        filters.add("a.commit_id = s.id")

        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        # TODO: left "author" as generic option coming from parameters
        # (this should be specified by command line)
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q


class Lines(Metrics):
    """ Added and Removed lines for source code management system """

    id = "lines"
    name = "Lines"
    desc = "Number of added and/or removed lines"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # This function contains basic parts of the query to count added and removed lines
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("sum(cl.added) as added_lines")
        fields.add("sum(cl.removed) as removed_lines")
        tables.add("scmlog s")
        tables.add("commits_lines cl")
        filters.add("cl.commit_id = s.id")

        # Eclipse specific
        filters.add("s.message not like '%cvs2svn%'")

        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        #TODO: left "author" as generic option coming from parameters (this should be specified by command line)
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

    def get_ts(self):
        #Specific needs for Added and Removed lines not considered in meta class Metrics
        query = self._get_sql(True)
        data = self.db.ExecuteQuery(query)

        if not (isinstance(data['removed_lines'], list)): data['removed_lines'] = [data['removed_lines']]
        if not (isinstance(data['added_lines'], list)): data['added_lines'] = [data['added_lines']]

        data['removed_lines'] = [float(lines)  for lines in data['removed_lines']]
        data['added_lines'] = [float(lines)  for lines in data['added_lines']]

        return completePeriodIds(data, self.filters.period,
                                 self.filters.startdate, self.filters.enddate)

    def get_trends(self, date, days):
        #Specific needs for Added and Removed lines not considered in meta class Metrics
        filters = self.filters

        chardates = GetDates(date, days)

        self.filters = MetricFilters(Metrics.default_period,
                                     chardates[1], chardates[0], None)
        last = self.get_agg()
        if last['added_lines'] is None: last['added_lines'] = 0
        last_added = int(last['added_lines'])
        if last['removed_lines'] is None: last['removed_lines'] = 0
        last_removed = int(last['removed_lines'])

        self.filters = MetricFilters(Metrics.default_period,
                                     chardates[2], chardates[1], None)
        prev = self.get_agg()
        if prev['added_lines'] is None: prev['added_lines'] = 0
        prev_added = int(prev['added_lines'])
        if prev['removed_lines'] is None: prev['removed_lines'] = 0
        prev_removed = int(prev['removed_lines'])

        data = {}
        data['diff_netadded_lines_'+str(days)] = last_added - prev_added
        data['percentage_added_lines_'+str(days)] = GetPercentageDiff(prev_added, last_added)
        data['diff_netremoved_lines_'+str(days)] = last_removed - prev_removed
        data['percentage_removed_lines_'+str(days)] = GetPercentageDiff(prev_removed, last_removed)
        data['added_lines_'+str(days)] = last_added
        data['removed_lines_'+str(days)] = last_removed

        #Returning filters to their original value
        self.filters = filters
        return (data)

class AddedLines(Metrics):
    """ Added lines for source code management system """

    id = "added_lines"
    name = "Added Lines"
    desc = "Number of added lines"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # This function contains basic parts of the query to count added and removed lines
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("sum(cl.added) as added_lines")
        tables.add("scmlog s")
        tables.add("commits_lines cl")
        filters.add("cl.commit_id = s.id")

        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        #TODO: left "author" as generic option coming from parameters (this should be specified by command line)
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

class RemovedLines(Metrics):
    """ Added and Removed lines for source code management system """

    id = "removed_lines"
    name = "Removed Lines"
    desc = "Number of removed lines"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # This function contains basic parts of the query to count added and removed lines
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("sum(cl.removed) as removed_lines")
        tables.add("scmlog s")
        tables.add("commits_lines cl")
        filters.add("cl.commit_id = s.id")

        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        #TODO: left "author" as generic option coming from parameters (this should be specified by command line)
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

class Branches(Metrics):
    """ Branches metric class for source code management system """

    id = "branches"
    name = "Branches"
    desc = "Number of active branches"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # Basic parts of the query needed when calculating branches
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(a.branch_id)) as branches")
        tables.add("scmlog s")
        tables.add("actions a")
        filters.add("a.commit_id = s.id")

        # specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        #TODO: left "author" as generic option coming from parameters (this should be specified by command line)
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q


class Actions(Metrics):
    """ Actions metrics class for source code management system """

    id = "actions"
    name = "Actions"
    desc = "Actions performed on several files (add, remove, copy, ... each file)"
    data_source = SCM

    def _get_sql (self, evolutionary):
        # Basic parts of the query needed when calculating actions
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(a.id)) as actions")
        tables.add("scmlog s")
        tables.add("actions a")
        filters.add("a.commit_id = s.id")

        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q


class CommitsPeriod(Metrics):
    """ Commits per period class for source code management system """

    id = "avg_commits"
    name = "Average Commits per period"
    desc = "Average number of commits per period"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # Basic parts of the query needed when calculating commits per period
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(s.id))/timestampdiff("+self.filters.period+",min(s.author_date),max(s.author_date)) as avg_commits_"+self.filters.period)
        tables.add("scmlog s")
        tables.add("(select distinct(a.commit_id) as id from actions a) nomergers")
        filters.add("s.id = nomergers.id")

        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

    def get_ts(self):
        # WARNING: This function should provide same information as Commits.get_ts(), do not use this.
        return {}


class FilesPeriod(Metrics):
    """ Files per period class for source code management system  """

    id = "avg_files"
    name = "Average Files per period"
    desc = "Average number of files per period"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # Basic parts of the query needed when calculating commits per period
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(a.file_id))/timestampdiff("+self.filters.period+",min(s.author_date),max(s.author_date)) as avg_files_"+self.filters.period)
        tables.add("scmlog s")
        tables.add("actions a")
        filters.add("s.id = a.commit_id")

        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

    def get_ts(self):
        # WARNING: This function should provide same information as Files.get_ts(), do not use this.
        return {}


class CommitsAuthor(Metrics):
    """ Commits per author class for source code management system """

    id = "avg_commits_author"
    name = "Average Commits per Author"
    desc = "Average number of commits per author"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # Basic parts of the query needed when calculating commits per author
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(s.id))/count(distinct(pup.uuid)) as avg_commits_author ")
        tables.add("scmlog s")
        tables.add("(select distinct(a.commit_id) as id from actions a) nomergers")
        filters.add("s.id = nomergers.id")

        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        #specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        # Needed code for specific analysis such as repositories or projects
        # Given that we're using sets, this does not add extra tables or filters.
        tables.add("people_uidentities pup")
        filters.add("s.author_id = pup.people_id")

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q


class AuthorsPeriod(Metrics):
    """ Authors per period class for source code management system """

    id = "avg_authors_period"
    name = "Average Authors per period"
    desc = "Average number of authors per period"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # Basic parts of the query needed when calculating commits per period
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(pup.uuid))/timestampdiff("+self.filters.period+",min(s.author_date),max(s.author_date)) as avg_authors_"+self.filters.period)
        tables.add("scmlog s")
        # filters = ""

        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        #specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        # Needed code for specific analysis such as repositories or projects
        # Given that we're using sets, this does not add extra tables or filters.
        tables.add("people_uidentities pup")
        filters.add("s.author_id = pup.people_id")

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q


    def get_ts(self):
        # WARNING, this function should return same information as Authors.get_ts(), do not use this
        return {}


class CommittersPeriod(Metrics):
    """ Committers per period class for source code management system """

    id = "avg_committers_period"
    name = "Average Committers per period"
    desc = "Average number of committers per period"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # Basic parts of the query needed when calculating commits per period
        fields = Set([])
        tables = Set([])
        filters = Set([])

        #TODO: the following three lines should be initialize in a __init__ method.
        self.id = "avg_committers_" + self.filters.period
        self.name = "Average Committers per " + self.filters.period
        self.desc = "Average number of committers per " + self.filters.period

        fields.add("count(distinct(pup.uuid))/timestampdiff("+self.filters.period+",min(s.author_date),max(s.author_date)) as avg_committers_"+self.filters.period)
        tables.add("scmlog s")
        # filters = ""

        filters.union_update(self.db.GetSQLReportWhere(self.filters, "committer"))

        #specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        if (self.filters.type_analysis is None or len (self.filters.type_analysis) != 2) :
            #Specific case for the basic option where people_upeople table is needed
            #and not taken into account in the initial part of the query
            if "people_uidentities pup" not in tables:
                tables.add("people_uidentities pup")
                filters.add("s.committer_id = pup.people_id")

        elif (self.filters.type_analysis[0] == "repository" or self.filters.type_analysis[0] == "project"):
            #Adding people_upeople table
            if "people_uidentities pup" not in tables:
                tables.add("people_uidentities pup")
                filters.add("s.committer_id = pup.people_id")

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

    def get_ts(self):
        # WARNING, this function should return same information as Committers.get_ts(), do not use this
        return {}


class FilesAuthor(Metrics):
    """ Files per author class for source code management system """

    id = "avg_files_author"
    name = "Average Files per Author"
    desc = "Average number of files per author"
    data_source = SCM

    def _get_sql(self, evolutionary):
        # Basic parts of the query needed when calculating files per author
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(a.file_id))/count(distinct(pup.uuid)) as avg_files_author")
        tables.add("scmlog s")
        tables.add("actions a")
        filters.add("s.id = a.commit_id")

        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))

        #specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        # Needed code for specific analysis such as repositories or projects
        # Given that we're using sets, this does not add extra tables or filters.
        tables.add("people_uidentities pup")
        filters.add("s.author_id = pup.people_id")

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

class Repositories(Metrics):
    """ Number of repositories in the source code management system """
    #TO BE REFACTORED

    id = "repositories"
    name = "Repositories"
    desc = "Number of repositories in the source code management system"
    envision = {"gtype" : "whiskers"}
    data_source = SCM

    def _get_sql(self, evolutionary):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(s.repository_id)) AS repositories")
        tables.add("scmlog s")
        tables.add("actions a")

        # specific parts of the query depending on the report needed
        tables.union_update(self.db.GetSQLReportFrom(self.filters))
        #TODO: left "author" as generic option coming from parameters (this should be specified by command line)
        filters.union_update(self.db.GetSQLReportWhere(self.filters, "author"))
        filters.add("s.id = a.commit_id")
        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evolutionary, self.filters.type_analysis)
        return q

    def get_list(self):
        """Repositories list ordered by number of commits"""
        q = """
            select count(distinct(sid)) as total, r.uri AS name
            from repositories r, (
              select distinct(s.id) as sid, repository_id from actions a, scmlog s
              where s.id = a.commit_id  and s.author_date >=%s and s.author_date < %s) t
            WHERE repository_id = r.id
            group by repository_id
            order by total desc,name
            """ % (self.filters.startdate, self.filters.enddate)

        return self.db.ExecuteQuery(q)

class Companies(Metrics):
    """ Organizations participating in the source code management system """
    #TO BE REFACTORED

    id = "organizations"
    name = "Organizations"
    desc = "Organizations participating in the source code management system"
    data_source = SCM

    def _get_sql(self, evol):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(enr.organization_id)) as organizations")
        tables.add("scmlog s")
        tables.add("people_uidentities pup")
        tables.add(self.db.identities_db+".enrollments enr")
        filters.add("s.author_id = pup.people_id")
        filters.add("pup.uuid = enr.uuid")
        filters.add("s.author_date >= enr.start")
        filters.add("s.author_date < enr.end")
        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evol, self.filters.type_analysis)
        return q

    def get_list(self, metric_filters = None, days = 0):
        #TODO: metric_filters parameter is deprecated and should be removed

        fields = Set([])
        tables = Set([])
        filters = Set([])

        #Building parts of the query to control timeframe of study
        if (days > 0):
            tables.add("(SELECT MAX(date) as last_date from scmlog) dt")
            filters.add("DATEDIFF (last_date, date) < %s " % (days))

        fields.add("org.name as name")
        fields.add("count(distinct(s.id)) as company_commits")

        tables.add("scmlog s")
        tables.add("people_uidentities pup")
        tables.add(self.db.identities_db + ".uidentities u")
        tables.add(self.db.identities_db+".enrollments enr")
        tables.add(self.db.identities_db+".organizations org")
        tables.union_update(self.db.GetSQLReportFrom(self.filters))

        filters.add("pup.people_id = s.author_id")
        filters.add(" u.uuid = pup.uuid")
        filters.add(" u.uuid = enr.uuid")
        filters.add("org.id = enr.organization_id")
        filters.add("s.author_date >= " + self.filters.startdate)
        filters.add("s.author_date < " + self.filters.enddate)
        filters.add("s.author_date >= enr.start")
        filters.add("s.author_date < enr.end")
        filters.union_update(self.db.GetSQLReportWhere(self.filters))

        query = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                                   self.filters.enddate, " s.author_date ", fields,
                                   tables, filters, False, self.filters.type_analysis)

        #TODO: to be included as another filter
        if self.filters.companies_out is not None:
            for company in self.filters.companies_out:
                query = query + " and org.name <> '" + company + "' "

        query = query + " GROUP by org.name ORDER BY company_commits DESC, org.name"

        return self.db.ExecuteQuery(query)

class Countries(Metrics):
    """ Countries participating in the source code management system """
    #TO BE REFACTORED

    id = "countries"
    name = "Countries"
    desc = "Countries participating in the source code management system"
    data_source = SCM

    def _get_sql(self, evol):
        fields = Set([])
        tables = Set([])
        filters = Set([])

        fields.add("count(distinct(pro.country_code)) as countries")
        tables.add("scmlog s")
        tables.add("people_uidentities pup")
        tables.add(self.db.identities_db+".profiles pro")
        filters.add("s.author_id = pup.people_id")
        filters.add("pup.uuid = pro.uuid")

        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evol, self.filters.type_analysis)
        return q

    def get_list(self):
        rol = "author" #committer
        identities_db = self.db.identities_db
        startdate = self.filters.startdate
        enddate = self.filters.enddate

        q = "SELECT count(s.id) as commits, cou.name as name "+\
            "FROM scmlog s,  "+\
            "     people_uidentities pup, "+\
            "     "+identities_db+".countries cou, "+\
            "     "+identities_db+".profiles pro "+\
            "WHERE pup.people_id = s."+rol+"_id AND "+\
            "      pup.uuid  = pro.uuid and "+\
            "      pro.country_code = cou.code and "+\
            "      s.author_date >="+startdate+ " and "+\
            "      s.author_date < "+enddate+ " "+\
            "group by cou.name "+\
            "order by commits desc"

        return self.db.ExecuteQuery(q)

class CompaniesCountries(Metrics):
    """ Countries in Companies participating in the source code management system """

    id = "organizations+countries"
    name = "CompaniesCountries"
    desc = "Organizations per Countries participating in the source code management system"
    data_source = SCM

    def get_list(self):
        rol = "author" #committer
        identities_db = self.db.identities_db
        startdate = self.filters.startdate
        enddate = self.filters.enddate

        q = "SELECT count(s.id) as commits, CONCAT(org.name, '_', cou.name) as name "+\
            "FROM scmlog s, people_uidentities pup, "+\
            identities_db+".countries cou, "+identities_db+".profiles pro, "+\
            identities_db+".organizations org, "+identities_db+".enrollments enr "+\
            "WHERE pup.people_id = s."+rol+"_id AND "+\
            "      pup.uuid  = pro.uuid and "+\
            "      pro.country_code = cou.code and "+\
            "      pup.uuid  = enr.uuid and "+\
            "      enr.organization_id = org.id and "+\
            "      s.author_date >= enr.start  and s.author_date < enr.end and "+\
            "      s.author_date >="+startdate+ " and "+\
            "      s.author_date < "+enddate+ " "+\
            "group by org.name, cou.name "+\
            "order by commits desc, org.name, cou.name"
        clist = self.db.ExecuteQuery(q)
        return clist

class CompaniesProjects(Metrics):
    """ Projects in Companies participating in the source code management system """

    id = "organizations+projects"
    name = "CompaniesProjects"
    desc = "Organizations per Projects participating in the source code management system"
    data_source = SCM

    def get_list(self):
        rol = "author" #committer
        identities_db = self.db.identities_db
        startdate = self.filters.startdate
        enddate = self.filters.enddate

        prj_name = org_name = None # all projects and orgs
        tables = self.db.GetSQLProjectsFrom(prj_name)
        tables.union_update(self.db.GetSQLCompaniesFrom())
        filters = self.db.GetSQLProjectsWhere()
        filters.union_update(self.db.GetSQLCompaniesWhere(org_name,rol))

        tables = self.db._get_tables_query(tables)
        filters = self.db._get_filters_query(filters)

        q = """
            SELECT count(s.id) as commits, CONCAT(org.name, '_', prj.name) as name
            FROM %s
            WHERE %s
            group by org.name, prj.name
            order by commits desc, org.name, prj.name
            """ % (tables, filters)

        clist = self.db.ExecuteQuery(q)
        return clist

class Domains(Metrics):
    """ Domains participating in the source code management system """
    #TO BE REFACTORED

    id = "domains"
    name = "Domains"
    desc = "Domains participating in the source code management system"
    data_source = SCM

    def _get_sql(self, evol):
        fields = "COUNT(DISTINCT(SUBSTR(email,LOCATE('@',email)+1))) AS domains"
        tables = "scmlog s, people p "
        filters = "s.author_id = p.id"
        q = self.db.BuildQuery(self.filters.period, self.filters.startdate,
                               self.filters.enddate, " s.author_date ", fields,
                               tables, filters, evol, self.filters.type_analysis)
        return q

    def get_list(self):
        rol = "author" #committer
        identities_db = self.db.identities_db
        startdate = self.filters.startdate
        enddate = self.filters.enddate

        q = """
            SELECT DISTINCT(SUBSTR(email,LOCATE('@',email)+1)) AS domain,
                   COUNT(DISTINCT(s.rev)) AS commits
            FROM  people p, scmlog s
            WHERE p.id = s.%s_id
            AND  s.author_date >= %s
            AND  s.author_date < %s
            GROUP BY domain ORDER BY commits desc, domain
            LIMIT %i
            """ % (rol, startdate, enddate, Metrics.domains_limit)

        res = self.db.ExecuteQuery(q)
        # Change the domain column id for name
        res['name'] = res.pop('domain')
        return res

class Projects(Metrics):
    """ Projects in the source code management system """
    #TO BE COMPLETED

    id = "projects"
    name = "Projects"
    desc = "Projects in the source code management system"
    data_source = SCM

    def get_list(self):
        # Just get commits per project
        startdate = self.filters.startdate
        enddate = self.filters.enddate

        type_analysis = ['project', None]
        period = None
        evol = False
        mcommits = Commits(self.db, self.filters)
        mfilter = MetricFilters(period, startdate, enddate, type_analysis)
        mfilter_orig = mcommits.filters
        mcommits.filters = mfilter
        commits = mcommits.get_agg()
        mcommits.filters = mfilter_orig
        checkListArray(commits)
        return commits

if __name__ == '__main__':
    filters1 = MetricFilters("month", "'2014-04-01'", "'2015-01-01'", ['repository',"'OpenID'"])
    dbcon = SCMQuery("root", "", "cp_cvsanaly_GrimoireLibTests", "cp_sortinghat_GrimoireLibTests")
    gone = GoneAuthors(dbcon, filters1)
    print gone.get_agg()
    print gone.get_list()
