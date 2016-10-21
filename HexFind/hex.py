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

    if len(sys.argv) == 2:
        with open(sys.argv[1]) as input_file:
            hex = find_hex(input_file.read().splitlines())

        for l in hex:
            sys.stdout.write(l)
    else:
        sys.stdout.write('Not sufficient arguments!\n')
        sys.stdout.write('Help: hex.py <file>\n')
        sys.stdout.write('Send to PCAP: hex.py <file> | text2pcap -o dec - output.pcap\n')

    try:
        sys.stdout.close()
    except:
        pass
    try:
        sys.stderr.close()
    except:
        pass


if __name__ == '__main__':

    # Production syntax for logging
    logging.basicConfig(stream=sys.stderr,
                level=logging.INFO,
                format="[%(levelname)8s]:%(name)s:  %(message)s")
    # Dev syntax for logging
    logging.debug("Starting script!")

    main()



