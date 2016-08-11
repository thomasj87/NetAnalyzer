#!/usr/bin/env python -tt
#Script to search for IP's and display them.

__author__ = 'tjongeri'

import logging
import sys


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

    else:
        print "No IP's found!"
        sys.exit(20)

    count_sort = {}
    print "Unique IP addresses: (count of them)"
    for ip in ips:
        print ip, str(ips[ip]['COUNT'])
        count_sort[ip] = ips[ip]['COUNT']

    print ''
    print ''
    print ''
    print ''

    for w in sorted(count_sort, key=count_sort.get, reverse=True):
      print w, count_sort[w]

if __name__ == '__main__':

    try:
        import clipboard

    except ImportError:
        raise "You have not install clipboard, please install it using PIP!"

    # Production syntax for logging
    logging.basicConfig(stream=sys.stderr,
                level=logging.INFO,
                format="[%(levelname)8s]:%(name)s:  %(message)s")
    # Dev syntax for logging
    logging.debug("Starting script!")

    main()

