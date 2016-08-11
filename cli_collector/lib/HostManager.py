#!/usr/bin/env python -tt
"""
Library for HostManagement Objects
"""

import logging
import datetime
from DatabaseManager import DatbaseManager
from utils import write_dict_to_json_file

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


class Device(object):
    '''
    Device object containing device settings.
    '''

    def __init__(self, name, db_id=None,
                 ipv4=None, username=None,
                 password=None, port=None,
                 prompt=None, timeout=10,
                 ssh=None, telnet=None,
                 post_commands=[],
                 connection_type='SSH'):

        self.name = name
        self.db_id = db_id
        self.ipv4 = ipv4

        self.connection_settings = {
            "USERNAME": username,
            "PASSWORD": password,
            "PROMPT": prompt,
            "SSH_COMMAND": ssh,
            "TELNET_COMMAND": telnet,
            "CONNECTION_PORT": port,
            "TIMEOUT": timeout,
            "POST_COMMANDS": post_commands,
            "CONNECTION_TYPE": connection_type
        }

    def all_node_details(self):
        '''
        Function to return all node details.
        '''

        all_node_details = {}
        all_node_details['NAME'] = self.name
        all_node_details['DB_ID'] = self.db_id
        all_node_details['IPV4'] = self.ipv4
        all_node_details['CONNECTION_SETTINGS'] = self.connection_settings

        return all_node_details

class HostManagment(Device):
    '''
    Host Manager to keep data for hosts. Export, and import data.
    '''

    def __init__(self, prefix=None, postfix='.log', db=DatbaseManager):
        super(Device, self).__init__()

        self.hm = {}
        self.prefix = prefix
        self.postfix = postfix
        self.db = db

    def add_host(self, host, **kwargs):
        '''
        Function to add host to HostManager and add function as required.

        Create Device Object and place them into "Settings" of specified host of HostManager.

        - ipv4 = IPv4 management address
        - db_id = Database Identifier if applicable
        - prompt = Prompt of device (as of beginning new line)
        - timeout = settings for node
        '''
        self.hm[host] = {}

        d = Device(host)

        if kwargs:
            if 'ipv4' in kwargs:
                d.ipv4 = kwargs['ipv4']
            if 'db_id' in kwargs:
                d.db_id = kwargs['db_id']
            if 'prompt' in kwargs:
                d.connection_settings['PROMPT'] = kwargs['prompt']
            if 'timeout' in kwargs:
                d.connection_settings['TIMEOUT'] = kwargs['timeout']

        self.hm[host]['SETTINGS'] = d

    def add_command(self, host, command, output=None):
        '''
        Function to add command to host and timestamp of output retrieval.

        Args:
            output (basestring): Output as string
            command (basestring): Command as string
            host (basestring): Hostname or IP as referenced in HostManager

        '''

        if host not in self.hm:
            self.add_host(host)

        if 'COMMANDS' not in self.hm[host]:
            self.hm[host]['COMMANDS'] = {}

        self.hm[host]['COMMANDS'][command] = {
            'OUTPUT': output,
            'TIMESTAMP': str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
        }

    def write_to_json(self, filename):
        '''
        Output to JSON file as specified

        Args:
            filename (basestring): Path to JSON file for output
        '''
        logging.debug("Writing JSON output to {}...".format(filename))

        # Remove device object as it is not exportable to JSON
        json_out = {}
        for x in self.hm:
            json_out[x] = {}
            for y in self.hm[x]:
                if y == 'SETTINGS':
                    json_out[x]['SETTINGS'] = self.hm[x]['SETTINGS'].all_node_details()
                else:
                    json_out[x][y] = self.hm[x][y]

        write_dict_to_json_file(filename, json_out, indent=2)

    def write_to_txt_files(self, output_dir):
        '''
        Output to text files to path as specified

        Args:
            output_dir (basestring): Path to directory for output
        '''

        logging.debug("Writing files to {}...".format(output_dir))
        for host in self.hm:
            if 'COMMANDS' in self.hm[host]:
                for command in self.hm[host]['COMMANDS']:
                    self.create_file(host=host, command=command,
                                     output=self.hm[host]['COMMANDS'][command]['OUTPUT'],
                                     output_dir=output_dir)

    def write_to_db(self):
        '''
        Output to DataBase if database object is given.
        '''

        if isinstance(self.db, DatbaseManager):
            logging.debug("Writing output to database...")

            # Format for supported DataBase Object
            db_output = {}

            for host in self.hm:
                db_output[self.hm[host]['SETTINGS'].db_id] = {}

                if 'COMMANDS' in self.hm[host]:
                    for command in self.hm[host]['COMMANDS']:
                        db_output[self.hm[host]['SETTINGS'].db_id][command] = {
                            'OUTPUT': self.hm[host]['COMMANDS'][command]['OUTPUT'],
                            'NAME': host,
                            'TIMESTAMP': self.hm[host]['COMMANDS'][command]['TIMESTAMP']
                            }

            # Connect and send to database
            self.db.connect()
            self.db.save_command_output(db_output)
            self.db.disconnect()
        else:
            logging.error("Database object not loaded into HostManager! Did not save data to DB!")

    def create_file(self, host, output, output_dir, sep='_', command=None, timestamp=None):
        '''
        Function to create files in desired output directory with options. This will create a file for
        each host and each command.

        Args:
            timestamp (basestring): If given, timestamp will be embedded into filename
            command (basestring): Command-name that will be embedded in filename
            output_dir (basestring): String to path for output
            output (basestring): String for output in file
            host (basestring): Hostname or IP for reference in file

        '''

        # Setting up path
        s = sep
        filename = output_dir + host

        if command:
            command = command.replace(' ', '_')
            filename = filename + s + command

        if timestamp:
            filename = filename + s + timestamp

        if self.postfix:
            filename = filename + self.postfix

        # Write to file
        target = open(filename, 'w')
        target.writelines(output)
        target.close()

        logging.debug("Write output to: {}".format(filename))
