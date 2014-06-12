#!/usr/bin/env python

# Copyright (C) 2012, 2013 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# This file is a part of the vizGrimoire.R package
#
# Authors:
#   Alvaro del Castillo <acs@bitergia.com>
#

import logging, sys, time

from GrimoireUtils import getPeriod, read_main_conf, createJSON

from report import Report

from utils import read_options

def get_evol_report(startdate, enddate, identities_db, bots):
    all_ds = {}

    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        all_ds[ds.get_name()] = ds.get_evolutionary_data (period, startdate, enddate, identities_db)
    return all_ds

def create_evol_report(startdate, enddate, destdir, identities_db, bots):
    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        ds.create_evolutionary_report (period, startdate, enddate, destdir, identities_db)

def get_agg_report(startdate, enddate, identities_db, bots):
    all_ds = {}

    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        all_ds[ds.get_name()] = ds.get_agg_data (period, startdate, enddate, identities_db)
    return all_ds

def create_agg_report(startdate, enddate, destdir, identities_db, bots):
    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        ds.create_agg_report (period, startdate, enddate, destdir, identities_db)

def get_top_report(startdate, enddate, identities_db, bots):
    all_ds_top = {}

    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        top = ds.get_top_data (startdate, enddate, identities_db, opts.npeople)
        all_ds_top[ds.get_name()] = top 
    return all_ds_top

def create_top_report(startdate, enddate, destdir, npeople, identities_db, bots):
    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        ds.create_top_report (startdate, enddate, destdir, npeople, identities_db)

def create_reports_filters(period, startdate, enddate, destdir, npeople, identities_db, bots):
    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        logging.info("Creating filter reports for " + ds.get_name())
        for filter_ in Report.get_filters():
            logging.info("-> " + filter_.get_name())
            ds.create_filter_report(filter_, period, startdate, enddate, destdir, npeople, identities_db, bots)

def create_report_people(startdate, enddate, destdir, npeople, identities_db, bots):
    for ds in Report.get_data_sources():
        Report.connect_ds(ds)
        logging.info("Creating people for " + ds.get_name())
        ds().create_people_report(period, startdate, enddate, destdir, npeople, identities_db)

# TODO: refactor to generalize it
def get_top_people (startdate, enddate, destdir, idb, bots):
    """Top people for all data sources."""
    import GrimoireSQL, SCR, MLS, ITS, IRC, Mediawiki
    npeople = "10000" # max limit, all people included
    min_data_sources = 4 # min data sources to be in the list
    tops = {}
    all_top = {}
    all_top_min_ds = {}
    db = automator['generic']['db_gerrit']
    GrimoireSQL.SetDBChannel (database=db, user=opts.dbuser, password=opts.dbpassword)
    tops["scr"] = SCR.GetTopOpenersSCR(0, startdate, enddate, idb, bots, npeople)
    db = automator['generic']['db_mlstats']
    GrimoireSQL.SetDBChannel (database=db, user=opts.dbuser, password=opts.dbpassword)
    tops["mls"] = MLS.top_senders(0, startdate, enddate, idb, bots, npeople)
    db = automator['generic']['db_bicho']
    GrimoireSQL.SetDBChannel (database=db, user=opts.dbuser, password=opts.dbpassword)
    # Fixed for bugzilla, what Wikimedia uses
    closed_condition = "(new_value='RESOLVED' OR new_value='CLOSED' OR new_value='Lowest')"
    # TODO: include in "-Bot" company all the bots
    tops["its"] = ITS.GetTopOpeners(0, startdate, enddate, idb, ["-Bot"], closed_condition, npeople)
    db = automator['generic']['db_irc']
    GrimoireSQL.SetDBChannel (database=db, user=opts.dbuser, password=opts.dbpassword)
    tops["irc"] = IRC.GetTopSendersIRC(0, startdate, enddate, idb, bots, npeople)
    db = automator['generic']['db_mediawiki']
    GrimoireSQL.SetDBChannel (database=db, user=opts.dbuser, password=opts.dbpassword)
    tops["mediawiki"] = Mediawiki.GetTopAuthorsMediaWiki(0, startdate, enddate, idb, bots, npeople)
    # SCR and SCM are the same. Don't use both for Tops
    # TODO: include in "-Bot" company all the bots
    # db = automator['generic']['db_cvsanaly']
    # GrimoireSQL.SetDBChannel (database=db, user=opts.dbuser, password=opts.dbpassword)
    # tops["scm"] = SCM.top_people(0, startdate, enddate, "author" , ["-Bot"] , npeople)

    # Build the consolidated top list using all data sources data
    # Only people in all data sources is used
    for ds in tops:
        pos = 1;
        for id in tops[ds]['id']:
            if id not in all_top: all_top[id] = []
            all_top[id].append({"ds":ds,"pos":pos})
            pos += 1

    for id in all_top:
        if len(all_top[id])>=min_data_sources: all_top_min_ds[id] = all_top[id]
    return all_top_min_ds

def create_top_people_report(startdate, enddate, destdir, idb, bots):
    """Top people for all data sources."""
    all_top_min_ds = get_top_people (startdate, enddate, destdir, idb, bots)
    createJSON(all_top_min_ds, opts.destdir+"/all_top.json")


def create_reports_r(enddate, destdir):
    from rpy2.robjects.packages import importr
    opts = read_options()

    vizr = importr("vizgrimoire")

    for ds in Report.get_data_sources():
        automator = Report.get_config()
        db = automator['generic'][ds.get_db_name()]
        dbuser = Report._automator['generic']['db_user']
        dbpassword = Report._automator['generic']['db_password']
        vizr.SetDBChannel (database=db, user=dbuser, password=dbpassword)
        logging.info("Creating R reports for " + ds.get_name())
        ds.create_r_reports(vizr, enddate, destdir)

def create_people_identifiers(startdate, enddate, destdir, idb, bots):
    logging.info("Generating people identifiers")

    from SCM import GetPeopleListSCM
    import People

    scm = None
    for ds in Report.get_data_sources():
        if ds.get_name() == "scm":
            scm = ds
            break
    if scm == None: return

    Report.connect_ds(scm)

    people_data = {}
    people = GetPeopleListSCM(startdate, enddate)
    people = people['pid']
    limit = 100
    if (len(people)<limit): limit = len(people);
    people = people[0:limit]

    for upeople_id in people:
        people_data[upeople_id] = People.GetPersonIdentifiers(upeople_id)

    all_top_min_ds = get_top_people(startdate, enddate, idb, bots)
    print(all_top_min_ds)

    db = automator['generic']['db_cvsanaly']
    GrimoireSQL.SetDBChannel (database=db, user=opts.dbuser, password=opts.dbpassword)

    for upeople_id in all_top_min_ds:
        people_data[upeople_id] = People.GetPersonIdentifiers(upeople_id)

    createJSON(people_data, destdir+"/people.json")

def create_reports_studies(period, startdate, enddate, destdir):
    from metrics_filter import MetricFilters

    db_identities= Report.get_config()['generic']['db_identities']
    dbuser = Report.get_config()['generic']['db_user']
    dbpass = Report.get_config()['generic']['db_password']

    studies = Report.get_studies()
    for study in studies:
        for ds in Report.get_data_sources():
            ds_dbname = ds.get_db_name()
            dbname = Report.get_config()['generic'][ds_dbname]
            dsquery = ds.get_query_builder()
            dbcon = dsquery(dbuser, dbpass, dbname, db_identities)
            metric_filters = MetricFilters(period, startdate, enddate, [])
            logging.info("Creating report for " + study.id)
            try:
                obj = study(dbcon, metric_filters)
            except TypeError:
                logging.info(study.id + " does no support standard API. Not used.")
                continue
            obj.create_report(ds, destdir)

def set_data_source(ds_name):
    ds_ok = False
    dss_active = Report.get_data_sources()
    DS = None
    for ds in dss_active:
        if ds.get_name() == opts.data_source:
            ds_ok = True
            DS = ds
            Report.set_data_sources([DS])
    if not ds_ok:
        logging.error(opts.data_source + " data source not available")
        sys.exit(1)
    return DS

def set_filter(filter_name):
    filter_ok = False
    filters_active = Report.get_filters()
    for filter_ in filters_active:
        if filter_.get_name() == opts.filter:
            filter_ok = True
            Report.set_filters([filter_])
    if not filter_ok:
        logging.error(opts.filter + " filter not available")
        sys.exit(1)

def set_metric(metric_name, ds_name):
    metric_ok = False
    DS = set_data_source(ds_name)

    metrics = DS.get_metrics_set(DS)
    for metric in metrics:
        if metric.id == metric_name:
            metric_ok = True
            DS.set_metrics_set(DS, [metric])
    if not metric_ok:
        logging.error(metric_name + " metric not available in " + DS.get_name())
        sys.exit(1)

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    logging.info("Starting Report analysis")
    opts = read_options()
    reports = opts.reports.split(",")

    Report.init(opts.config_file, opts.metrics_path)

    automator = read_main_conf(opts.config_file)
    if 'start_date' not in automator['r']:
        logging.error("start_date (yyyy-mm-dd) not found in " + opts.config_file)
        sys.exit()
    start_date = automator['r']['start_date']
    if 'end_date' not in automator['r']:
        end_date = time.strftime('%Y-%m-%d')
    else:
        end_date = automator['r']['end_date']

    if 'period' not in automator['r']:
        period = getPeriod("months")
    else:
        period = getPeriod(automator['r']['period'])
    logging.info("Period: " + period)

    # TODO: hack because VizR library needs. Fix in lib in future
    startdate = "'"+start_date+"'"
    enddate = "'"+end_date+"'"

    identities_db = automator['generic']['db_identities']

    if (opts.data_source):
        set_data_source(opts.data_source)
    if (opts.filter):
        set_filter(opts.filter)
    if (opts.metric):
        set_metric (opts.metric, opts.data_source)

    bots = []

    if not opts.filter:
        logging.info("Creating global evolution metrics...")
        evol = create_evol_report(startdate, enddate, opts.destdir, identities_db, bots)
        logging.info("Creating global aggregated metrics...")
        agg = create_agg_report(startdate, enddate, opts.destdir, identities_db, bots)
        logging.info("Creating global top metrics...")
        top = create_top_report(startdate, enddate, opts.destdir, opts.npeople, identities_db, bots)
        if (automator['r']['reports'].find('people')>-1):
            create_report_people(startdate, enddate, opts.destdir, opts.npeople, identities_db, bots)
        create_reports_r(end_date, opts.destdir)
        create_people_identifiers(startdate, enddate, opts.destdir, identities_db, bots)

    create_reports_filters(period, startdate, enddate, opts.destdir, opts.npeople, identities_db, bots)
    create_top_people_report(startdate, enddate, opts.destdir, identities_db, bots)
    create_reports_studies(period, startdate, enddate, opts.destdir)

    logging.info("Report data source analysis OK")
