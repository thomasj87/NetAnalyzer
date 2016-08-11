 _____  _     _____   _____       _ _           _
/  __ \| |   |_   _| /  __ \     | | |         | |
| /  \/| |     | |   | /  \/ ___ | | | ___  ___| |_ ___  _ __
| |    | |     | |   | |    / _ \| | |/ _ \/ __| __/ _ \| '__|
| \__/\| |_____| |_  | \__/\ (_) | | |  __/ (__| || (_) | |
 \____/\_____/\___/   \____/\___/|_|_|\___|\___|\__\___/|_|



Made by: Thomas Jongerius

# CLI Collector
The CLI collector is a library that allows you to collect CLI data
via the command line on a large scale.

The collector is specificly written to allow to connect via jumpnodes
(TCP forwarding sockets of SSH)in the network to the end destination.

## Options

TBD

## Help Menu

usage: cli_collector_tunnel.py [-h] [--reset] [--log-level LEVEL]
                               [-o OUTPUT_DIR] [-j OUTPUT_JSON]
                               [-c {SSH,TELNET}] [--allow_other_than_show]
                               (-db | -dl DEVICE_LIST)
                               SETTINGS_FILE COMMAND_LIST CREDENTIAL_FILE

Script that allows you to collect data from network via CLI.

positional arguments:
  SETTINGS_FILE         File containing connection settings
  COMMAND_LIST          Text file with list of commands to collect.
  CREDENTIAL_FILE       File containing credentials and/or references

optional arguments:
  -h, --help            show this help message and exit
  --reset, -r           Option will reset all key ring password and ask for
                        password always.
  --log-level LEVEL     Prints out debug information about the device
                        connection stage. LEVEL is a string of DEBUG, INFO,
                        ERROR, CRITICAL. Default is ERROR.
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Output directory for export command output
  -j OUTPUT_JSON, --json_output OUTPUT_JSON
                        Output JSON file
  -c {SSH,TELNET}, --connection {SSH,TELNET}
                        Connection Type (Default: SSH)
  --allow_other_than_show
                        CAUTION: This option allows you to execute other
                        commands then show-commands!
  -db, --database       Input/Output to database
  -dl DEVICE_LIST, --device_list DEVICE_LIST
                        Text file with list of devices to collect data from.

## Exit codes

To be updated

100 > Known error
101 > Unsupported feature
102 > Reoccuring node, might cause loop
103 > Cannot connect, connection required.
200 > Unknown error
201 > Setting missing

## Defaults

TBD

# Roadmap

- Collection via Jumpnode sessions (Telnet or SSH)
- Refined connection options
  * Terminate of single failure
  * Silent kill on failure
  * Continue execution on command retrieval if timed out