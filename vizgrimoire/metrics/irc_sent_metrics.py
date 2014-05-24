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
##   Alvaro del Castillo <acs@bitergia.com>

""" Opened metric for the issue tracking system """

import logging
import MySQLdb

from GrimoireUtils import completePeriodIds

from metrics import Metrics

from metrics_filter import MetricFilters

from query_builder import IRCQuery

from IRC import IRC

class Sent(Metrics):
    """ Messages sent  metric class for mailing lists """
    id = "sent"
    name = "Sent messages"
    desc = "Number of messages sent to mailing list(s)"
    data_source = IRC

    def __get_sent__ (self, evolutionary):
        # This function contains basic parts of the query to COUNT opened tickets.
        # That query is built and results returned.
        query = self.__get_sql__(evolutionary)
        return self.db.ExecuteQuery(query)


    def __get_sql__(self, evolutionary):
        fields = " COUNT(DISTINCT(message)) AS sent "
        tables = " irclog " + self.db.GetSQLReportFrom(self.db.identities_db, self.filters.type_analysis)
        filters = self.db.GetSQLReportWhere(self.filters.type_analysis)
        filters += " and type='COMMENT' "
        q = self.db.BuildQuery(self.filters.period, self.filters.startdate, 
                               self.filters.enddate, " date ", fields, 
                               tables, filters, evolutionary)
        return q

    def get_data_source(self):
        return self.data_source

    def get_ts (self):
        # Returns the evolution of commits through the time
        data = self.__get_sent__(True)
        return completePeriodIds(data, self.filters.period, self.filters.startdate, self.filters.enddate)

    def get_agg(self):
        return self.__get_sent__(False)

    def get_list(self):
        #to be implemented
        pass

# Examples of use
if __name__ == '__main__':
    filters = MetricFilters("week", "'2010-01-01'", "'2014-01-01'", ["company", "'Red Hat'"])
    dbcon = IRCQuery("root", "", "cp_irc_SingleProject", "cp_irc_SingleProject",)
    redhat = Sent(dbcon, filters)
    all = Sent(dbcon)
    # print redhat.get_ts()
    print redhat.get_agg()
    print all.get_agg()