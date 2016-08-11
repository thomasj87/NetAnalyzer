#!/usr/bin/env python -tt
"""
Utility library.
"""

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"

import socket
import time
import json
import os
import logging

def delegate(attribute_name, method_names):
    """Passes the call to the attribute called attribute_name for
    every method listed in method_names.
    """
    # hack for python 2.7 as nonlocal is not available
    d = {
        'attribute': attribute_name,
        'methods': method_names
    }

    def decorator(cls):
        attribute = d['attribute']
        if attribute.startswith("__"):
            attribute = "_" + cls.__name__ + attribute
        for name in d['methods']:
            setattr(cls, name, eval("lambda self, *a, **kw: "
                                    "self.{0}.{1}(*a, **kw)".format(
                                    attribute, name)))
        return cls
    return decorator


def to_list(item):
    """
    If the given item is iterable, this function returns the given item.
    If the item is not iterable, this function returns a list with only the
    item in it.

    @type  item: object
    @param item: Any object.
    @rtype:  list
    @return: A list with the item in it.
    """
    if hasattr(item, '__iter__'):
        return item
    return [item]


def is_reachable(host, port=23):
    """
    This function check reachability for specified hostname/port
    It tries to open TCP socket.
    It supports IPv6.
    :param host string: hostname or ip address string
    :rtype: str
    :param port number: tcp port number
    :rtype: bool
    :return: True if host is reachable else false
    """

    try:
        addresses = socket.getaddrinfo(
            host, port, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
    except socket.gaierror:
        return False

    for family, socktype, proto, cannonname, sockaddr in addresses:
        sock = socket.socket(family, socket.SOCK_STREAM)
        #sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        sock.settimeout(5)
        try:
            sock.connect(sockaddr)
        except IOError as e:
            continue

        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        # Wait 2 sec for socket to shutdown
        time.sleep(2)
        break
    else:
        return False
    return True


def read_from_json_file(filename):
    '''Read JSON file and send back dict.'''
    try:
        with open(filename) as file_load:
            json_data = json.load(file_load)
            file_load.close()

        return json_data

    except IOError as e:
        logging.error("I/O error({0}): {1}".format(e.errno, e.strerror))
        logging.warn("JSON file could not be loaded!")


def write_dict_to_json_file(filename, dict, indent=2):
    '''Write dict to JSON file.'''
    if os.path.exists(filename):
        logging.warn("File {} already exists. Will be overwritten!".format(filename))
    with open(filename, 'w') as outfile:
        json.dump(dict, outfile, indent=indent)
        outfile.close()


def dir_check(directory):
    '''Function to check directory existence'''

    if os.path.exists(directory):
        logging.debug('Path {} already exists.'.format(directory))
    else:
        logging.warn('Path {} does not yet exist. Will be created!'.format(directory))
        os.mkdir(directory)

def arp_parser(input_data):
    'Check ARP output'

    import re

    arp = {}

    for x in str(input_data).splitlines():
        mac = re.search('\w\w\w\w.\w\w\w\w.\w\w\w\w', x)
        interface = re.search('\w+Ethernet\d/\d', x)
        ip = re.search('\d+.\d+.\d+.\d+', x)
        if mac:
            arp[mac.group()] = {}
            if interface and ip:
                arp[mac.group()] = {'INTERFACE': interface.group(), 'IP': ip.group()}

    return arp
