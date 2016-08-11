#!/usr/bin/env python -tt
"""
 _____              __ _                           _
/  __ \            / _(_)                         | |
| /  \/ ___  _ __ | |_ _  __ _    __ _ _ __   __ _| |_   _ _______ _ __
| |    / _ \| '_ \|  _| |/ _` |  / _` | '_ \ / _` | | | | |_  / _ \ '__|
| \__/\ (_) | | | | | | | (_| | | (_| | | | | (_| | | |_| |/ /  __/ |
 \____/\___/|_| |_|_| |_|\__, |  \__,_|_| |_|\__,_|_|\__, /___\___|_|
                          __/ |                       __/ |
                         |___/                       |___/

Script that allows you to collect data from network via CLI.
There is an option to collect data via Jumpserver.
"""

from lib.utils import read_from_json_file
import argparse
import logging
import sys
import re

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


def interfaces(input):
    c = str(input).splitlines()
    interfaces = []
    output = ''
    current_int_flag = False

    for x in c:
        protocol = re.search('line protocol', x)
        if protocol:
            if current_int_flag:
                interfaces.append(output)
                current_int_flag = False
            else:
                current_int_flag = True
                output = x
        else:
            if current_int_flag:
                output += x

    return interfaces

def int_mac_ip(input):

    output = ''
    interface_details = {}

    for interface in input:
        interface_name = None
        ip_address = None
        mac_address = None
        mtu_size = None
        in_error = None
        out_error = None


        mac = re.search('\w\w\w\w\.\w\w\w\w\.\w\w\w\w', interface)
        if mac:
            mac_address = mac.group()

        mtu = re.search('(MTU\s)(\d+)(\sbytes)', interface)
        if mtu:
            mtu_size = mtu.group(2)

        iner = re.search('(\d+)(\sinput\serrors)', interface)
        if iner:
            in_error = iner.group(1)

        outer = re.search('(\d+)(\soutput\serrors)', interface)
        if outer:
            out_error = outer.group(1)

        int_re = re.search('\w*Ethernet\d/\d', interface)
        if int_re:
            interface_name = int_re.group()

        ip = re.search('\d+\.\d+\.\d+\.\d+', interface)
        if ip:
            ip_address = ip.group()

        interface_details[str(interface_name)] = {
            'IP' : str(ip_address),
            'MAC' : str(mac_address),
            'INERROR' : str(in_error),
            'OUTERROR' : str(out_error),
            'MTU' : str(mtu_size)
        }

    return interface_details


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
        self.parser.add_argument("--log-level", metavar='LEVEL', choices=['debug', 'info', 'error', 'critical'], default='debug',
                            help='''
                            Prints out debug information about the device connection stage.
                            LEVEL is a string of DEBUG, INFO, ERROR, CRITICAL.
                            Default is ERROR.
                            ''')
        self.parser.add_argument('input', metavar='INPUT_FILE', type=str,
                                 help="JSON file with input data from CLI collector.")

    def execute(self):

        # Set logging level
        logging_format = "[ %(levelname)-8s ][ %(asctime)s,%(msecs)03d ]:  %(message)s"
        datetime_format = "%H:%M:%S"

        if self.args.log_level == 'debug':
            level = logging.DEBUG
            logging_format = "[%(levelname)8s][%(asctime)s,%(msecs)03d]:" \
                             "%(name)s:%(funcName)s(){l.%(lineno)d}:  %(message)s"
            datetime_format = "%Y-%m-%d %H:%M:%S"
        elif self.args.log_level == 'info':
            level = logging.INFO
        elif self.args.log_level == 'error':
            level = logging.ERROR
        else:
            level = logging.CRITICAL

        logging.basicConfig(stream=sys.stderr, level=level, format=logging_format, datefmt=datetime_format)

        # Provide basic information if logging required
        logging.debug("Started")

        logging.info("Level of logging: {}".format(self.args.log_level))
        logging.info("Input file: {}".format(self.args.input))

        input_file = read_from_json_file(self.args.input)

        output_collector = 'HOST,INTERFACE,IP,MAC,MTU,IN_ERRORS,OUT_ERRORS\n'
        sep = ','
        for host in input_file:

            if 'COMMANDS' in input_file[host]:
                for command in input_file[host]['COMMANDS']:
                    if command == 'show interfaces':
                        inter = interfaces(input_file[host]['COMMANDS'][command]['OUTPUT'])
                        x = int_mac_ip(inter)
                        for y in x:
                            output_collector += host + sep + y + sep + x[y]['IP'] + sep + x[y]['MAC'] + sep + x[y]['MTU'] + sep + x[y]['INERROR'] + sep + x[y]['OUTERROR'] + '\n'


        # Print output to screen
        print output_collector

        logging.debug("Script ended")
        sys.exit()

def main():
    cli = CliClient()
    cli.execute()

if __name__ == '__main__':
    main()