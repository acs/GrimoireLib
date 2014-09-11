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
## Package to deal with queries for ITS data from *Grimoire
##  (Bicho databases)
##
## Authors:
##   Jesus M. Gonzalez-Barahona <jgb@bitergia.com>
##

from sqlalchemy import create_engine, func, Column, Integer, ForeignKey, or_
from sqlalchemy.ext.declarative import declarative_base, DeferredReflection
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.query import Query
from sqlalchemy.schema import ForeignKeyConstraint
from sqlalchemy.sql import label
from datetime import datetime
from timeseries import TimeSeries
from activity import ActivityList

#BaseId = declarative_base(cls=DeferredReflection)


def table_factory (bases, name, tablename, schemaname, columns = {}):
    """Factory for building table classes.

    Parameters
    ----------

    base: list of classes to inherit from
       Base classes, of which the resulting clase will inherit
    name: string
       Name of the class to be built
    tablename: string
       Name of the database table to be interfaced by the class
    schemaname: string
       Name of the schema to which the table belongs

    Returns
    -------

    class in the Base hierarchy

    """

    attr = dict (
        __tablename__ = tablename,
        __table_args__ = {'schema': schemaname}
        )
    for key in columns:
        attr[key] = columns[key]
    table_class = type(name, bases, attr)
    return table_class


class ITSDatabase():
    """Class for dealing with ITS (Bicho) databases.

    """

    def __init__(self, database, schema, schema_id):
        """Instatiation.

        Parameters
        ----------

        database: string
           SQLAlchemy url for the database to be used, such as
           mysql://user:passwd@host:port/
        schema: string
           Schema name for the ITS data
        schema_id: string
           Schema name for the unique ids data
        
        """

        global Changes, Issues, People, PeopleUPeople, Trackers
        global UPeople
        self.database = database
        Base = declarative_base(cls=DeferredReflection)
        self.Base = Base
        Changes = table_factory (bases = (Base,), name = 'Changes',
                                 tablename = 'changes',
                                 schemaname = schema,
                                 columns = dict (
                issue_id = Column(Integer,
                                  ForeignKey(schema + '.' + 'issues.id'))
                ))
        Issues = table_factory (bases = (Base,), name = 'Issues',
                                tablename = 'issues',
                                schemaname = schema,
                                columns = dict (
                changed_by = Column(Integer,
                                    ForeignKey(schema + '.' + 'people.id'))     
                ))
        People = table_factory (bases = (Base,), name = 'People',
                                tablename = 'people',
                                schemaname = schema)
        PeopleUPeople = table_factory (bases = (Base,), name = 'PeopleUPeople',
                                tablename = 'people_upeople',
                                schemaname = schema,
                                columns = dict (
                upeople_id = Column(Integer,
                                    ForeignKey(schema + '.' + 'upeople.id'))
                ))
        Trackers = table_factory (bases = (Base,), name = 'Trackers',
                                tablename = 'trackers',
                                schemaname = schema)
        UPeople = table_factory (bases = (Base,), name = 'UPeople',
                                tablename = 'upeople',
                                schemaname = schema_id)

    def build_session(self, echo = False):
        """Create a session with the database

        Instantiatates an engine and a session to work with it.

        Parameters
        ----------
        
        echo: boolean
           Output SQL to stdout or not
        
        """
        
        # To set Unicode interaction with MySQL
        # http://docs.sqlalchemy.org/en/rel_0_9/dialects/mysql.html#unicode
        trailer = "?charset=utf8&use_unicode=0"
        database = self.database + trailer
        engine = create_engine(database,
                               convert_unicode=True, encoding='utf8',
                               echo=echo)
        self.Base.prepare(engine)
        Session = sessionmaker(bind=engine, query_cls=ITSQuery)
        session = Session()
        return (session)

# class Changes(Base):
#     """changes table"""

#     __tablename__ = 'changes'
#     issue_id = Column(Integer, ForeignKey('issues.id'))

# class Issues (Base):
#     """issues table"""

#     __tablename__ = 'issues'
#     changed_by = Column(Integer, ForeignKey('people.id'))

# class People(Base):
#     """people table"""

#     __tablename__ = 'people'

# class PeopleUPeople(Base):
#     """people_upeople table"""

#     __tablename__ = 'people_upeople'
#     upeople_id = Column(Integer, ForeignKey('upeople.id'))

# class Trackers(Base):
#     """repositories table"""

#     __tablename__ = 'trackers'

# class UPeople(BaseId):
#     """upeople table"""

#     __tablename__ = 'upeople'

class ITSQuery (Query):
    """Class for dealing with ITS queries"""

    def __init__ (self, entities, session):
        """Create an ITSQuery.

        Parameters
        ----------

        entities: list of SQLAlchemy entities
           Entities (tables) to include in the query
        session: SQLAlchemy session
           SQLAlchemy session to use to connect to the database

        Attributes
        ----------

        self.start: datetime.datetime
           Start of the period to consider for commits. Default: None
           (start from the first commit)
        self.end: datetime.datetime
           End of the period to consider for commits. Default: None
           (end in the last commit)

        """

        self.start = None
        self.end = None
        # Keep an accounting of which tables have been joined, to avoid
        # undesired repeated joins
        self.joined = []
        Query.__init__(self, entities, session)


    def __repr__ (self):

        if self.start is not None:
            start = self.start.isoformat()
        else:
            start = "ever"
        if self.end is not None:
            end = self.end.isoformat()
        else:
            end = "ever"
        repr = "ITSQuery from %s to %s\n" % (start, end)
        repr = "  Joined: %s\n" % str(self.joined)
        repr += Query.__str__(self)
        return repr

    def __str__ (self):

        return self.__repr__()


    def select_personsdata(self, kind):
        """Adds columns with persons data to select clause.

        Adds people.user, people.email to the select clause of query.
        Does not join new tables.

        Parameters
        ----------

        kind: {"openers", "closers", "changers"}
           Kind of person to select

        Returns
        -------

        SCMObject: Result query, with new fields: id, name, email        

        """

        query = self.add_columns (label("person_id", People.id),
                                  label("name", People.user_id),
                                  label('email', People.email))
        if kind == "openers":
            person = Issues.submitted_by
            table = Issues
        elif kind == "changers":
            person = Changes.changed_by
            table = Changes
        elif kind == "closers":
            raise Exception ("select_personsdata: Not yet implemented")
        else:
            raise Exception ("select_personsdata: Unknown kind %s." \
                             % kind)

        if table in self.joined:
            query = query.filter (People.id == person)
        else:
            self.joined.append (table)
            query = query.join (table, People.id == person)
        return query


    def select_personsdata_uid(self, kind):
        """Adds columns with persons data to select clause (uid version).

        Adds person_id, name, to the select clause of query,
        having unique identities into account.
        Joins with PeopleUPeople, UPeople, and Changes / Isues if they
        are not already joined.
        Relationships: UPeople.id == PeopleUPeople.upeople_id,
        PeopleUPeople.people_id == person

        Parameters
        ----------

        kind: {"openers", "closers", "changers"}
           Kind of person to select

        Returns
        -------

        SCMObject: Result query, with new fields: id, name, email        

        """

        query = self.add_columns (label("person_id", UPeople.id),
                                  label("name", UPeople.identifier))
        if kind == "openers":
            person = Issues.submitted_by
            table = Issues
        elif kind == "changers":
            person = Changes.changed_by
            table = Changes
        elif kind == "closers":
            raise Exception ("select_personsdata: Not yet implemented")
        else:
            raise Exception ("select_personsdata: Unknown kind %s." \
                             % kind)
        if not self.joined:
            # First table, UPeople is in FROM
            self.joined.append (UPeople)
        if not self.joined or UPeople in self.joined:
            # First table, UPeople is in FROM, or we have UPeople
            if PeopleUPeople not in self.joined:
                self.joined.append (PeopleUPeople)
                query = query.join (PeopleUPeople,
                                    UPeople.id == PeopleUPeople.upeople_id)
            if table in self.joined:
                query = query.filter (PeopleUPeople.people_id == person)
            else:
                self.joined.append (table)
                query = query.join (table, PeopleUPeople.people_id == person)
        elif PeopleUPeople in self.joined:
            # We have PeopleUPeople (table should be joined), no UPeople
            if table not in self.joined:
                raise Exception ("select_personsdata_uid: " + \
                                     "If PeopleUPeople is joined, " + \
                                     str(table) + " should be joined too")
            self.joined.append (UPeople)
            query = query.join (UPeople,
                                UPeople.id == PeopleUPeople.upeople_id)
        elif table in self.joined:
            # We have table, and no PeopleUPeople, no UPeople
            self.joined.append (PeopleUPeople)
            query = query.join (PeopleUPeople,
                                PeopleUPeople.people_id == person)
            self.joined.append (UPeople)
            query = query.join (UPeople,
                                UPeople.id == PeopleUPeople.upeople_id)
        else:
            # No table, no PeopleUPeople, no UPeople but some other table
            raise Exception ("select_personsdata_uid: " + \
                                 "Unknown table to join to")
        return query


    def select_changesperiod(self):
        """Add to select the period of the changed tickets.

        Adds min(changes.changed_on) and max(changes.changed_on)
        for selected commits.
        
        Returns
        -------

        SCMObject: Result query, with two new fields: firstdate, lastdate

        """

        query = self.add_columns (label('firstdate',
                                        func.min(Changes.changed_on)),
                                  label('lastdate',
                                        func.max(Changes.changed_on)))
        return query


    def filter_period(self, start = None, end = None, date = "change"):
        """Filter variable for a period

        - start: datetime, starting date
        - end: datetime, end date
        - date: "change"

        Commits considered are between starting date and end date
        (exactly: start <= date < end)
        """

        query = self
        if date == "change":
            date_field = Changes.changed_on
        else:
            raise Exception ("filter_period: Unknown kind of date: %s." \
                                 % date)

        if start is not None:
            self.start = start
            query = query.filter(date_field >= start.isoformat())
        if end is not None:
            self.end = end
            query = query.filter(date_field < end.isoformat())
        return query


    def group_by_person (self):
        """Group by person

        Uses person_id field in the query to do the grouping.
        That field should be added by some other method.

        Parameters
        ----------

        None

        Returns
        -------

        SCMQuery object, with a new field (person_id)
        and a "group by" clause for grouping the results.

        """

        return self.group_by("person_id")


    def activity (self):
        """Return an ActivityList object.

        The query has to produce rows with the following fields:
        id (string),  name (string), start (datetime), end (datetime)

        """

        list = self.all()
        return ActivityList(list)

if __name__ == "__main__":

    import sys
    import codecs
    from standalone import print_banner

    # Trick to make the script work when using pipes
    # (pipes confuse the interpreter, which sets codec to None)
    # http://stackoverflow.com/questions/492483/setting-the-correct-encoding-when-piping-stdout-in-python
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)

    ITSDB = ITSDatabase(database = 'mysql://jgb:XXX@localhost/',
                        schema = 'vizgrimoire_bicho',
                        schema_id = 'vizgrimoire_cvsanaly')
    session = ITSDB.build_session(echo = False)

    #---------------------------------
    print_banner ("List of openers")
    res = session.query() \
        .select_personsdata("openers") \
        .group_by_person()
    print res
    for row in res.limit(10).all():
        print row.person_id, row.name, row.email

    #---------------------------------
    print_banner ("Activity period for changers")
    res = session.query() \
        .select_personsdata("changers") \
        .select_changesperiod() \
        .group_by_person()
    print res
    for row in res.limit(10).all():
        print row.person_id, row.name, row.email, row.firstdate, row.lastdate

    #---------------------------------
    print_banner ("Activity period for changers (uid)")
    res = session.query() \
        .select_personsdata_uid("changers") \
        .select_changesperiod() \
        .group_by_person()
    print res
    for row in res.limit(10).all():
        print row.person_id, row.name, row.firstdate, row.lastdate