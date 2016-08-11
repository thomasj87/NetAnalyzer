#!/usr/bin/env python -tt
"""
Database Manager library for managing database.
"""

import logging
import mysql.connector

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Arno Hommel"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"

class DatbaseManager(object):
    """
    Database manager.
    """

    def __init__(self, database=None, user=None, password=None, sql_server='127.0.0.1'):
        # type: (obj, str, str, str, int, str, lst, int) -> obj
        """
        Database manager for managing connectivity and queries to MySQL database.

        Args:
        @str sql_server: MySQL database IP/FQDN address
        @str password: password for database
        @str user: username for database
        @str database: database name
        """

        self.connected = False
        self.sql_server = sql_server
        self.database = database
        self.database_user = user
        self.database_password = password
        self.connector = mysql.connector.connect()

    def disconnect(self):
        self.connector.close()
        self.connected = False
        logging.debug('Disconnected from database!')

    def connect(self):
        if self.connected:
            logging.warn('Already connected to DB, close connection first prior to opening new connection!')
        elif self.sql_server and self.database and self.database_user and self.database_password:
            try:
                self.connector = mysql.connector.connect(host=self.sql_server,
                                                         user=self.database_user,
                                                         password=self.database_password,
                                                         database=self.database)
                self.connected = True
                logging.debug('Now connected to {} ({})'.format(self.sql_server, self.database))

            except Exception as e:
                logging.error('*** Failed to connect to %s! %r' % (self.sql_server, e))
                raise
        else:
            logging.error('Not all required database settings are loaded! Cannot connect!')
            raise

    def get_device_list(self):
        # Check for connection to DB.
        if not self.connected:
            self.connect()

        # Open DB cursor
        cursor = self.connector.cursor()
        query = ("SELECT deviceid, name, ip, protocol FROM devices")
        logging.debug('Retrieving device list from DB ({})...'.format(query))
        cursor.execute(query)


        # Put data into dict
        devices = {}
        for (deviceid, name, ip, protocol) in cursor:
            devices[deviceid] = {'NAME': name,
                                 'IP': ip,
                                 'PROTOCOL': protocol}

        logging.debug('Received {} devices!'.format(str(len(devices))))

        # Close cursor
        cursor.close()

        return devices

    def save_command_output(self, data):
        # Check for connection to DB.
        if not self.connected:
            self.connect()

        # Open DB cursor
        cursor = self.connector.cursor()

        # Prepare base query
        add_output = ("REPLACE INTO `output` "
                      "(`deviceid`, `command`, `timestamp`, `output`) "
                      "VALUES ({}, '{}', '{}', '{}')")

        # Send query per command
        for deviceid in data:
            for command in data[deviceid]:
                query = add_output.format(deviceid, command,
                                          data[deviceid][command]['TIMESTAMP'],
                                          str(data[deviceid][command]['OUTPUT']).replace("'", '"'))
                # Insert data
                cursor.execute(query)
                logging.debug('Sending command data ({}) for {} to DB...'.format(command,
                                                                                 data[deviceid][command]['NAME']))

        # Make sure data is committed to the database
        self.connector.commit()
        logging.debug('Commit data to database!')

        # Close cursor
        cursor.close()

