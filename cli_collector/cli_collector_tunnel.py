#!/usr/bin/env python -tt
"""
 _____  _     _____   _____       _ _           _
/  __ \| |   |_   _| /  __ \     | | |         | |
| /  \/| |     | |   | /  \/ ___ | | | ___  ___| |_ ___  _ __
| |    | |     | |   | |    / _ \| | |/ _ \/ __| __/ _ \| '__|
| \__/\| |_____| |_  | \__/\ (_) | | |  __/ (__| || (_) | |
 \____/\_____/\___/   \____/\___/|_|_|\___|\___|\__\___/|_|


Script that allows you to collect data from network via CLI.
There is an option to collect data via Jumpserver.
"""

import argparse
import logging
import os
import platform
import sys
from lib.DatabaseManager import DatbaseManager
from lib import ConnectionManager, HostManager, accountmgr, utils

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Arno Hommel"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


class CliClient(object):

    def __init__(self):
        """
        Constructor
        """
        self.build_parser()
        self.args = self.parser.parse_args()


    def build_parser(self):
        """
        Build the argparse parser based on the arguments given to the constructor
        """

        self.parser = argparse.ArgumentParser(
            description='''Script that allows you to collect data from network via CLI.''',
            epilog='Created by ' + __author__ + ', version ' + __version__ + ' ' + __copyright__)
        self.parser.add_argument("--reset", "-r", help="Option will reset all key ring password and ask for password always.",
                            dest='reset', action='store_true')
        self.parser.add_argument("--log-level", metavar='LEVEL', choices=['debug', 'info', 'error', 'critical'], default='error',
                            help='''
                            Prints out debug information about the device connection stage.
                            LEVEL is a string of DEBUG, INFO, ERROR, CRITICAL.
                            Default is ERROR.
                            ''')
        self.parser.add_argument("-o", "--output_dir", help="Output directory for export command output",
                            type=str, default=None, dest='output_dir')
        self.parser.add_argument("-j", "--json_output", help="Output JSON file",
                            type=str, default=None, dest='output_json')
        self.parser.add_argument("-c", "--connection", help="Connection Type (Default: SSH)",
                           type=str, default='SSH', dest='connection', choices=['SSH', 'TELNET'])
        self.parser.add_argument("--allow_other_than_show", help="CAUTION: This option allows you to execute other"
                                                            " commands then show-commands!",
                           default=False, dest='allow_no_show', action='store_true')
        self.parser.add_argument('setting_file', help="File containing connection settings",
                            type=str, metavar='SETTINGS_FILE')
        self.parser.add_argument('command_list', metavar='COMMAND_LIST', type=str,
                            help="Text file with list of commands to collect.")
        self.parser.add_argument('credentials', help="File containing credentials and/or references",
                            type=str, metavar='CREDENTIAL_FILE')
        db_file_exclusive = self.parser.add_mutually_exclusive_group(required=True)
        db_file_exclusive.add_argument("-db", "--database", help="Input/Output to database",
                           default=False, dest='output_db', action='store_true')
        db_file_exclusive.add_argument("-dl", "--device_list", help="Text file with list of devices to collect data from.",
                           type=str, default=None, dest='device_list')

    def execute(self):

        # Set logging level
        logging_format="[ %(levelname)-8s ][ %(asctime)s,%(msecs)03d ]:  %(message)s"
        datetime_format = "%H:%M:%S"

        if self.args.log_level == 'debug':
            level = level_paramiko_transport = logging.DEBUG
            logging_format = "[%(levelname)8s][%(asctime)s,%(msecs)03d]:" \
                             "%(name)s:%(funcName)s(){l.%(lineno)d}:  %(message)s"
            datetime_format = "%Y-%m-%d %H:%M:%S"
        elif self.args.log_level == 'info':
            level = logging.INFO
            level_paramiko_transport = logging.ERROR
        elif self.args.log_level == 'error':
            level = level_paramiko_transport = logging.ERROR
        else:
            level = level_paramiko_transport = logging.CRITICAL

        logging.basicConfig(stream=sys.stderr, level=level, format=logging_format, datefmt=datetime_format)
        logging.getLogger("paramiko.transport").setLevel(level_paramiko_transport)

        # Provide basic information if logging required
        logging.debug("Started")

        logging.info("Level of debugging: {}".format(self.args.log_level))
        logging.info("System running: {} ({})".format(platform.system(), os.name))
        logging.info("Output directory: {}".format(self.args.output_dir))
        logging.info("JSON output file: {}".format(self.args.output_json))
        logging.info("Database output: {}".format(self.args.output_db))
        logging.info("Allow other then 'show'-commands: {}".format(self.args.allow_no_show))
        logging.info("Credential file: {}".format(self.args.credentials))
        logging.info("Credential reset: {}".format(self.args.reset))
        logging.info("Settings file: {}".format(self.args.setting_file))
        logging.info("Device list file: {}".format(self.args.device_list))
        logging.info("Command list file: {}".format(self.args.command_list))

        logging.info("Initial setup loading...")

        s = utils.read_from_json_file(self.args.setting_file)
        d = None

        # Receiving device list if device file is given use that.
        devices = {}
        if self.args.device_list:
            source = 'file'
            with open(self.args.device_list) as device_file:
                hosts_list = device_file.read().splitlines()
                index = 0
                for host in hosts_list:
                    devices[index] = {
                        'NAME': host,
                        'IP': host,
                        'PROTOCOL': self.args.connection
                    }
                    index += 1
        elif self.args.output_db:

            # Setting up data base manager
            d = DatbaseManager(database=s['SETTINGS']['MYSQL_DATABASE'],
                               user=s['SETTINGS']['MYSQL_USER'],
                               password=s['SETTINGS']['MYSQL_PASSWORD'],
                               sql_server=s['SETTINGS']['MYSQL_SERVER'])

            source = 'database'
            d.connect()
            devices = d.get_device_list()
            d.disconnect()
        else:
            logging.critical("Must select in-/output method!")
            sys.exit(10)

        logging.info("Devices from {} loaded! (Total: {})".format(source, len(devices)))

        # Read commands from file:
        try:
            with open(self.args.command_list) as device_file:
                commands_list = device_file.read().splitlines()
        except IOError as e:
            logging.error("I/O error({0}): {1}".format(e.errno, e.strerror))
            raise

        # Connect SSH tunnel to jump node!
        logging.debug('Creating SSH tunnel connector...')
        j = ConnectionManager.JumpCollection(s['SETTINGS']['PATH'], s["JUMPSERVERS"])
        logging.info("Connected to Jumpservers!")

        # Setting up connection and output collector objects
        c = ConnectionManager.TunnelConnectionAgent(
            am=accountmgr.AccountManager(config_file=self.args.credentials, reset=self.args.reset),
            jumpservers=j,
            ssh_command=s['SETTINGS']['SSH_COMMAND'],
            telnet_command=s['SETTINGS']['TELNET_COMMAND'],
            timeout=s['SETTINGS']['TIMEOUT'])

        # Setup host manager (Output collector)
        h = HostManager.HostManagment(db=d)

        # Collection of data
        output = {}
        logging.info("Performing device captures...")
        for device in devices:
            # Add host to host manager
            h.add_host(devices[device]['NAME'], db_id=device, ipv4=devices[device]['IP'])

            # Connect to end device
            connection = c.connect(devices[device]['IP'], connection_protocol=devices[device]['PROTOCOL'])

            if connection:
                # Set unlimited terminal length
                c.terminal_lenth_cisco(devices[device]['NAME'])

                # Send commands and collect output
                output[device] = {}
                for command in commands_list:
                    if connection:
                        # Only show commands are allowed!
                        connection, out = c.send_command(devices[device]['NAME'],
                                             command, allow_more_show=self.args.allow_no_show)
                        if out:
                            h.add_command(devices[device]['NAME'], command, out)

                # Disconnect from end node gracefully
                if connection:
                    c.disconnect()
                logging.info("Finished data collection for {}!".format(devices[device]['NAME']))

        # Disconnect from jump nodes
        logging.debug('Terminating SSH tunnel to connector...')
        j.disconnect_jumpserver_chain()
        logging.info("Disconnected from jumpservers!")

        # Output options!

        # Output to files in output directory
        if self.args.output_dir:
            utils.dir_check(self.args.output_dir)
            h.write_to_txt_files(self.args.output_dir)
            logging.info("Saved output to text files in:{}!".format(self.args.output_dir))

        # Write to JSON output
        if self.args.output_json:
            h.write_to_json(self.args.output_json)
            logging.info("Saved output to JSON file:{}!".format(self.args.output_json))

        # Send output to SQL server
        if self.args.output_db:
            if not self.args.device_list:
                h.write_to_db()
                logging.info("Saved output to database!")
            else:
                logging.error("Not saving output to database! Can only save output to database"
                              " if devices are retreived from database!")

        logging.debug("Script ended")
        sys.exit()

def main():
    cli = CliClient()
    cli.execute()


if __name__ == '__main__':
    main()