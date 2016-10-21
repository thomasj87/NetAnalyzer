#!/usr/bin/env python -tt
#Script to search for HEX entries and prepp them for PCAP export.

__author__ = 'tjongeri'

import logging
import sys

def find_hex(input_data):

    import re
    output_data = []

    for x in input_data:
        offset = re.search(r'(\d\d\d\d):\s(.*)', x)

        if offset:
            if offset.group(1) == '0000':
                output_data.append('')
            output_data.append(offset.group(1) + ' ' + offset.group(2))

    return output_data

def main():

    import sys

    if len(sys.argv) == 2:
        with open(sys.argv[1]) as input_file:
            hex = find_hex(input_file.read().splitlines())

        for l in hex:
            print l
    else:
        print 'Not sufficient arguments!'
        print 'Help: hex.py <file>'
        print 'Send to PCAP: hex.py <file> | text2pcap -o dec - output.pcap'

if __name__ == '__main__':

    # Production syntax for logging
    logging.basicConfig(stream=sys.stderr,
                level=logging.INFO,
                format="[%(levelname)8s]:%(name)s:  %(message)s")
    # Dev syntax for logging
    logging.debug("Starting script!")

    main()



