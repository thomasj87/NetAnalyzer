#!/usr/bin/env python -tt
#Script to search for IP's and display them.

__author__ = 'tjongeri'

import logging
import sys

try:
    import clipboard

except ImportError:
    raise "You have not install clipboard, please install it using PIP!"


def getip(searching):
    import re

    result = []
    ip_dig = re.findall('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', searching)

    for ip in ip_dig:
        valid = True

        for d in ip.split('.'):
            d = int(d)
            if d > 255:
                valid = False
            else:
                pass

        if valid:
            result.append(ip)

    return result

def main():

    if clipboard.paste is None:
        print "No content clipboard! Exiting!"
        sys.exit(10)

    data = "192.0.2.0/24, 198.51.100.0/24 en 203.0.113.0/24, 123.3.4.5, 256.1.2.3"
    clipboard.copy(data)

    res = []
    res = getip(clipboard.paste())

    ips = {}

    if len(res) > 0:
        for ip in res:
            if ip not in ips:
                ips[ip] = {}
                ips[ip]['COUNT'] = 1
            else:
                ips[ip]['COUNT'] += 1

        # for ip in ips:
        #     print ips[ip]['COUNT'], ip
    else:
        print "No IP's found!"

if __name__ == '__main__':

    # Production syntax for logging
    logging.basicConfig(stream=sys.stderr,
                level=logging.INFO,
                format="[%(levelname)8s]:%(name)s:  %(message)s")
    # Dev syntax for logging
    logging.debug("Starting script!")

    main()

