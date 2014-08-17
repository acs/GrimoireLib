#! /usr/bin/python
# -*- coding: utf-8 -*-

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
## Package to deal with Demography from *Grimoire (CVSAnalY, Bicho, MLStats
## databases)
##
## Authors:
##   Jesus M. Gonzalez-Barahona <jgb@bitergia.com>
##

from common import Family, DBFamily
from scm_query import SCMDatabase, SCMQuery
from its_query import ITSDatabase, ITSQuery
from mls_query import MLSDatabase, MLSQuery
from scm import PeriodCondition as SCMPeriodCondition
from scm import SCMDatabaseDefinition
from scm import NomergesCondition as SCMNomergesCondition
from its_conditions import PeriodCondition as ITSPeriodCondition
from its import ITSDatabaseDefinition
from mls import MLSDatabaseDefinition

class ActivityPersons (DBFamily):
    """Root constructor of entities in the ActivityPersons family.

    This class can be used to instantiate entities from the ActivityPersons
    family: those related to activity of persons.

    This is the root of ahierarchy of classes for the ActivityPersons
    families corresponding to the different data sources (SCM, ITS, MLS, etc.).

    Objects of this class provide the function activity() to
    obtain an ActivityList object. From this ActivityList, ages or
    idle period for actors can be obtained.

    """

    def _produce_query (self, name):
        """Produce the base query to obtain activity per person.

        This function assumes that self.query was already initialized.
        The produced query replaces self.query.
        Conditions will be applied (as filters) later to the query
        produced by this function.

        Parameters
        ----------
        
        name: string
           Entity name.

        """

        raise Exception ("_produce_query should be provided by child class")

    def activity (self):
        """Obtain the activity list (ActivityList object).

        Extracts the activity list by querying the database
        according to the initialization of the object.
        
        Returns
        -------

        ActivityList: activity list for all actors

        """

        return self.query.activity()

class SCMActivityPersons (ActivityPersons):
    """Constructor of entities in the SCMActivityPersons family.

    Interface to entities related to activity of persons in SCM.
    
    """

    def _produce_query (self, name):
        """Produce the base query to obtain activity per person.

        This function assumes that self.query was already initialized.
        The produced query replaces self.query.
        Conditions will be applied (as filters) later to the query
        produced by this function.

        Parameters
        ----------
        
        name: {"list_authors" | "list_committers" |
           "list_uauthors" | "list_ucommitters"}
           Entity name.

        """

        if name in ("list_authors", "list_uauthors"):
            persons = "authors"
        elif name in ("list_committers", "list_ucommitters"):
            persons = "committers"
        else:
            raise Exception ("SCMActivityPersons: " + \
                                 "Invalid entity name for this family, " + \
                                 name)
        if name in ("list_authors", "list_committers"):
            self.query = self.query.select_personsdata(persons)
        elif name in ("list_uauthors", "list_ucommitters"):
            self.query = self.query.select_personsdata_uid(persons)
        self.query = self.query \
            .select_commitsperiod() \
            .group_by_person()


class ITSActivityPersons (ActivityPersons):
    """Constructor of entities in the ITSActivityPersons family.

    Interface to entities related to activity of persons in ITS.
    
    """

    def _produce_query (self, name):
        """Produce the base query to obtain activity per person.

        This function assumes that self.query was already initialized.
        The produced query replaces self.query.
        Conditions will be applied (as filters) later to the query
        produced by this function.

        Parameters
        ----------
        
        name: {"list_changers" | "list_uchangers"}
           Entity name.

        """

        if name in ("list_changers", "list_uchangers"):
            persons = "changers"
        else:
            raise Exception ("ITSActivityPersons: " + \
                                 "Invalid entity name for this family, " + \
                                 name)
        self.query = self.session.query()
        if name in ("list_changers"):
            self.query = self.query.select_personsdata(persons)
        elif name in ("list_uchangers"):
            self.query = self.query.select_personsdata_uid(persons)
        self.query = self.query \
            .select_changesperiod() \
            .group_by_person()


class MLSActivityPersons (ActivityPersons):
    """Constructor of entities in the MLSActivityPersons family.

    Interface to entities related to activity of persons in MLS.
    
    """

    def _produce_query (self, name):
        """Produce the base query to obtain activity per person.

        This function assumes that self.query was already initialized.
        The produced query replaces self.query.
        Conditions will be applied (as filters) later to the query
        produced by this function.

        Parameters
        ----------
        
        name: {"list_senders" | "list_usenders"}
           Entity name.

        """

        if name in ("list_senders", "list_usenders"):
            persons = "senders"
        else:
            raise Exception ("MLSActivityPersons: " + \
                                 "Invalid entity name for this family, " + \
                                 name)
        
        self.query = self.session.query()
        if name in ("list_senderss"):
            self.query = self.query.select_personsdata(persons)
        elif name in ("list_usenders"):
            self.query = self.query.select_personsdata_uid(persons)
        self.query = self.query \
            .select_activeperiod() \
            .group_by_person()


class DurationCondition ():
    """Root of all conditions for DurationPersons objects

    Provides a filter method which will be called when applying
    the condition.
    """

    def filter (object):
        """Filter to apply for this condition

        - query: query to which the filter will be applied
        """

        return object

class SnapshotCondition (DurationCondition):
    """Condition for specifiying "origin" of durations.

    Durations (age, idle) are to be calculated from the time
    specified by this condition.

    """

    def __init__ (self, date):
        """Instatiation of the object.

        Parameters
        ----------

        date: datetime.datetime
           Time used as reference for the snapshot.

        """

        self.date = date

    def modify (self, object):
        """Modification for this condition.

        Specifies the time for the snapshot.

        """

        object.set_snapshot(self.date)


class ActiveCondition (DurationCondition):
    """Condition for filtering persons active during a period

    Only persons active during the specified period are to
    be considered.

    """

    def __init__ (self, after = None, before = None):
        """Instatiation of the object.

        Parameters
        ----------

        after: datetime.datetime
           Start of the activity period to consider (default: None).
           None means "since the begining of time"
        before: datetime.datetime
           End of the activity period to consider (default: None).
           None means "until the end of time

        """

        self.after = after
        self.before = before

    def modify (self, object):
        """Modification for this condition.

        Sets the new activity list, considering only active
        persons during the period.

        """

        object.set_activity(object.activity.active(after = self.after,
                                                   before = self.before))
    

class DurationPersons (Family):
    """Constructor of entities in the DurationPersons family.

    This class can be used to instantiate entities from the DurationPersons
    family: those related to duration of persons.
    
    Duration can be periods of different kinds, such as age or idle time.
    
    Objects of this class provide the functions durations() to
    obtain an ActorsDuration object.

    """

    def __init__ (self, name, conditions = (), activity = None):
        """Instantiation of an entity of the family.

        Instantiation can be specified with an ActivityPersons object.

        Parameters
        ----------
        
        name: {"age" | "idle"}
           Enitity name.
        conditions: list of Condition objects
           Conditions to be applied to provide context to the entity.
           (default: empty list).
        activity: ActivityPersons
           ActivityPersons object with the activity of persons to consider.

        """

        if activity is None:
            raise Exception ("DurationPersons: " + \
                                 "acitivity parameter is needed.")
        self.activity = activity
        if name not in ("age", "idle"):
            raise Exception ("DurationPersons: " + \
                                 "Invalid entity name for this family: " + \
                                 name)
        self.name = name
        self.snapshot = None
        for condition in conditions:
            condition.modify(self)

    def set_snapshot (self, time):
        """Define a snapshot time for durations.

        Durations (age, idle) are to be calculated from the time
        specified.

        Parameters
        ----------

        time: datetime.datetime
           Time of snapshot.
        """

        self.snapshot = time

    def set_activity (self, activity):
        """Change the activity considered by the object.

        Parameters
        ---------

        activity: ActivityPersons
           New list of activity per person to be used.

        """

        self.activity = activity

    def durations (self):
       """Durations for each person (age, idle,...) depending on entity

       """

       if self.snapshot is None:
           snapshot = self.activity.maxend()
       else:
           snapshot = self.snapshot
       if self.name == "age":
           durations = self.activity.age(date = snapshot)
       elif self.name == "idle":
           durations = self.activity.idle(date = snapshot)
       return durations


if __name__ == "__main__":

    from standalone import stdout_utf8, print_banner
    from datetime import datetime, timedelta

    stdout_utf8()

    # SCM database
    database = SCMDatabaseDefinition (url = "mysql://jgb:XXX@localhost/",
                                      schema = "vizgrimoire_cvsanaly",
                                      schema_id = "vizgrimoire_cvsanaly")
    #---------------------------------
    print_banner("List of activity for each author")
    data = SCMActivityPersons (
        datasource = database,
        name = "list_authors")
    activity = data.activity()
    print activity

    #---------------------------------
    print_banner("Age (days since first activity) for each author.")
    age = activity.age(datetime(2014,1,1))
    print age.json()
    #---------------------------------
    print_banner("Idle (days since last activity) for each author.")
    idle = activity.idle(datetime(2014,1,1))
    print idle.json()

    #---------------------------------
    print_banner("List of activity for each author (no merges)")
    period = SCMPeriodCondition (start = datetime(2014,1,1), end = None)
    nomerges = SCMNomergesCondition()

    data = SCMActivityPersons (
        datasource = database,
        name = "list_authors", conditions = (period,nomerges))
    activity = data.activity()
    print activity

    #---------------------------------
    print_banner("Age (days since first activity) for each author.")
    age = activity.age(datetime(2012,1,1))
    print age.json()
    #---------------------------------
    print_banner("Idle (days since last activity) for each author.")
    idle = activity.idle(datetime(2012,1,1))
    print idle.json()

    #---------------------------------
    print_banner("List of activity for each committer (no merges, uid)")
    session = data.get_session()
    data = SCMActivityPersons (name = "list_ucommitters",
                               conditions = (nomerges,),
                               datasource = session)
    print data.activity()
    print data.activity() \
        .active(after = datetime(2014,1,1) - timedelta(days=183))
    print data.activity() \
        .active(after = datetime(2014,1,1) - timedelta(days=183)) \
        .age(datetime(2014,1,1)).json()

    #---------------------------------
    print_banner("Age, using entity")
    age = DurationPersons (name = "age",
                           activity = data.activity())
    print age.durations().json()

    #---------------------------------
    print_banner("Age, using entity and conditions")
    snapshot = SnapshotCondition (date = datetime (2014,1,1))
    active_period = ActiveCondition (after = datetime(2014,1,1) - \
                                         timedelta(days=10))
    age = DurationPersons (name = "age",
                           conditions = (snapshot, active_period),
                           activity = data.activity())
    print age.durations().json()
    
    # ITS database
    database = ITSDatabaseDefinition (url = "mysql://jgb:XXX@localhost/",
                                      schema = "vizgrimoire_bicho",
                                      schema_id = "vizgrimoire_cvsanaly")

    #---------------------------------
    print_banner("List of activity for each changer")
    data = ITSActivityPersons (
        datasource = database,
        name = "list_changers")
    activity = data.activity()
    print activity

    #---------------------------------
    print_banner("List of activity for each changer, with period condition")
    period = ITSPeriodCondition (start = datetime(2014,1,1),
                                             end = None)
    data = ITSActivityPersons (
        datasource = database,
        name = "list_changers",
        conditions = (period,))
    activity = data.activity()
    print activity

    #---------------------------------
    print_banner("List of activity for each changer (unique ids)")
    data = ITSActivityPersons (
        datasource = database,
        name = "list_uchangers")
    activity = data.activity()
    print activity

    # MLS database
    database = MLSDatabaseDefinition (url = "mysql://jgb:XXX@localhost/",
                                      schema = "oscon_openstack_mls",
                                      schema_id = "oscon_openstack_scm")

    #---------------------------------
    print_banner("List of activity for each sender")
    data = MLSActivityPersons (
        datasource = database,
        name = "list_senders")
    activity = data.activity()
    print activity

    #---------------------------------
    print_banner("List of activity for each sender (unique ids)")
    data = MLSActivityPersons (
        datasource = database,
        name = "list_usenders")
    activity = data.activity()
    print activity

    #---------------------------------
    print_banner("MLS: Birth")
    data = MLSActivityPersons (
        datasource = database,
        name = "list_usenders")
    # Birth has the ages of all actors, considering enddate as
    # current (snapshot) time
    enddate = datetime(2014,7,1)
    snapshot = SnapshotCondition (date = enddate)
    birth = DurationPersons (name = "age",
                             conditions = (snapshot,),
                             activity = data.activity())
    print birth.durations()

    #---------------------------------
    print_banner("MLS: Aging")
    data = MLSActivityPersons (
        datasource = database,
        name = "list_usenders")
    # "Aging" has the ages of those actors active during the 
    # last half year (that is, the period from enddate - half year
    # to enddate)
    active_period = ActiveCondition (after = enddate - \
                                         timedelta(days=182))
    aging = DurationPersons (name = "age",
                             conditions = (snapshot, active_period),
                             activity = data.activity())
    print aging.durations()


    #---------------------------------
    # print_banner("List of activity for each committer (OpenStack)")
    # session = buildSession(
    #     database = 'mysql://jgb:XXX@localhost/openstack_cvsanaly_2014-06-06',
    #     echo = False)
    # data = ActivityPersons (var = "list_committers",
    #                         session = session)
    # print data.activity()
    # #---------------------------------
    # print_banner("Age for each committer (OpenStack)")
    # print data.activity().age(datetime(2014,6,6)).json()
    # #---------------------------------
    # print_banner("Time idle for each committer (OpenStack)")
    # print data.activity().idle(datetime(2014,6,6)).json()
    # #---------------------------------
    # print_banner("Age for committers active during a period (OpenStack)")
    # print data.activity() \
    #     .active(after = datetime(2014,6,6) - timedelta(days=180)) \
    #     .age(datetime(2014,6,6)).json()
