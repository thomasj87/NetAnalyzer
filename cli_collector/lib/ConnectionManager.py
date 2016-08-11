#!/usr/bin/env python -tt
"""
Connection Manager library for managing connections to hosts.
"""

import logging
import pexpect
import accountmgr
import re
import os

import sys
from sshtunnel import SSHTunnelForwarder
from sshtunnel import BaseSSHTunnelForwarderError

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


class SSHTunnelingConnectionAgent(object):
    """
    Connection Agent to manage TCP port forwarding instances.
    """

    def __init__(self, server, username, remote_bind_address, remote_bind_port,
                 password=None, ssh_pkey=os.path.expanduser("~") + '/.ssh/id_rsa', port=22):
        """
        Connection Manager for SSH tunnels.

        Args:
            ssh_pkey (str): String to path with private key for SSH authentication (required) (Default: ~/.ssh/id_rsa)
            password (str): Optional password if required
            remote_bind_port (int): port to connect to over SSH tunnel
            remote_bind_address (str): Address to connect to over SSH tunnel
            port (int): Port number for SSH tunnel connection (Default 22)
            username (str): Username for SSH tunnel connection (required)
            server (str): Server name to connect to (str)
        """

        self.ssh_server = server
        self.username = username
        self.password = password
        self.ssh_port = port
        self.remote_bind_address = remote_bind_address
        self.remote_bind_port = remote_bind_port
        self.ssh_pkey = ssh_pkey
        self.local_port = None
        self.tunnel = SSHTunnelForwarder

        # Auto connect on initialization
        self.connect()

    def connect(self):
        """
        Method for creating connection to tunnel host and destination port.
        """

        # Try to setup connection, terminal program on failure!
        try:
            logging.debug('Connecting to ssh host %s:%d ...' % (self.ssh_server, self.ssh_port))
            # Setup tunnel handler
            if self.password:
                self.tunnel = SSHTunnelForwarder(self.ssh_server,
                                                 ssh_port=self.ssh_port,
                                                 ssh_username=self.username,
                                                 ssh_pkey=self.ssh_pkey,
                                                 ssh_private_key_password=self.password,
                                                 remote_bind_address=(self.remote_bind_address,
                                                                      self.remote_bind_port))
            else:
                self.tunnel = SSHTunnelForwarder(self.ssh_server,
                                                 ssh_port=self.ssh_port,
                                                 ssh_username=self.username,
                                                 ssh_pkey=self.ssh_pkey,
                                                 remote_bind_address=(self.remote_bind_address,
                                                                      self.remote_bind_port))

            # Start tunnel and return it to background!
            self.tunnel.start()

            self.local_port = self.tunnel.local_bind_port  # local assigned  port
            logging.debug('Now forwarding port {} to {}:{} ...'.format(self.local_port, self.remote_bind_address,
                                                                       self.remote_bind_port))


        except ValueError as e:
            logging.critical("Cannot create SSH tunnel! Check password or key file! ({})".format(e))
            raise ValueError(e)
        except BaseSSHTunnelForwarderError as e:
            logging.critical("Could not connect to {} due to connectivity issues! ({})".format(self.ssh_server, e))
            raise BaseSSHTunnelForwarderError(e)
        except Exception as e:
            logging.error('*** Failed to connect to %s:%d: %r' % (self.ssh_server, self.ssh_port, e))
            raise BaseException(e)

        logging.debug("Connected to {}!".format(self.ssh_server))

    def disconnect(self):
        """
        Method for terminating connection to tunnel host and destination port.
        """

        self.tunnel.stop()
        logging.debug("Connection to {} ({}) terminated!".format(self.ssh_server, self.tunnel._remote_binds))


class JumpCollection(object):
    """
    Jumpserver object to maintain SSH tunnels to series of jumpservers via TCP port forwarding.
    """

    def __init__(self, path, jumpserver_settings):
        """
        Class to maintain jumpserver collection for chaining multiple SSH server jumps
        over TCP forwarding sockets.

        Args:
            path (lst): List of strings to order of destination of jumpservers.
            Each destination must represent the next hop as of that node.

            jumpserver_settings (dict): Dictionary of jumpserver settings.
            Each jumphost in the path list must be within the jumpserver settings.
            Key value indicates the settings for a destination (key).
            - Destination (key)
                - CONNECTION_TYPE: 'SSH_TUNNEL' (Only setting supported, not used)
                Roadmap: Session management via SSH or Telnet
                - USERNAME: Basestring for username
                - PASSWORD: Basestring keyphrase for private key
                - RSA_KEY_FILE: Basestring to location path for private key for SSH authentication. (Mandatory)
                - PORT: Port to connect to for SSH connection.
        """

        # Initial variables
        self.jumpserver_collection = []
        # List for SSHTunnelingConnectionAgent instances maintaining connectivity to jumpserver.

        self.path = path
        self.jump_settings = jumpserver_settings
        self.loopback_address = '127.0.0.1'
        self.local_port = None
        self.final_connection = None # SSHTunnelingConnectionAgent instances maintaining connectivity to last host.

        # Validate if all connection settings are there
        required_settings = ['CONNECTION_TYPE', 'USERNAME', 'PASSWORD', 'RSA_KEY_FILE', 'PORT']
        for jumpserver in path:
            if jumpserver not in self.jump_settings:
                logging.error("Not all jumpserver-data ({}) in setting file!".format(jumpserver))
                raise
            for jumpserver_in_settings in self.jump_settings:
                for setting in self.jump_settings[jumpserver_in_settings]:
                    if setting not in required_settings:
                        logging.error("Not all jumpserver-data ({} - {}) in setting file!".format(jumpserver, setting))
                        raise

                        # Validate Jumpserver path
        if len(self.path) > 1:  # If more then 1 jumpserver, connect chain and return local port for final connection.
            logging.debug("Found {} jumpservers in pathsettings, connecting to {} of them.".format(
                len(self.path), len(self.path) - 1))
            self.local_port = self.connect_jumpserver_chain()
        elif len(self.path) == 1:  # If only 1 jumpserver, do not connect but setup final connection on demand.
            logging.debug("Found only 1 jumpserver, will connect on request.")
        else:  # Must have jumpserver connection for this program!
            logging.critical("Cannot proceed without jumpservers!")
            raise

    def connect_jumpserver_chain(self):
        """
        Method required to open connection to jumpservers in a chain except for the last one.

        Jumpservers will be connected by initilized settings. These will create a chain of TCP sockets
        allowing to SSH > SSH > +n connectivity -1. The final connection varies based on the services that
        is requested to the final host.
        """

        index = 0  # Index key required to loop over path list and call next jumpnode.
        current_connection = None

        # Loop over jumpserver path except the last one.
        for jumpserver in self.path[:-1]:
            logging.debug("Connecting to {}...".format(jumpserver))

            # If password available, set password.
            password = None
            if 'PASSWORD' in self.jump_settings[jumpserver]:
                password = self.jump_settings[jumpserver]['PASSWORD']

            if current_connection is None:
                # First connection to direct host
                current_connection = \
                    SSHTunnelingConnectionAgent(server=jumpserver,
                                                username=self.jump_settings[jumpserver]['USERNAME'],
                                                remote_bind_address=self.path[index + 1],
                                                remote_bind_port=self.jump_settings[self.path[index + 1]][
                                                    'PORT'],
                                                ssh_pkey=self.jump_settings[jumpserver]['RSA_KEY_FILE'],
                                                port=self.jump_settings[jumpserver]['PORT'],
                                                password=password)
                self.jumpserver_collection.append(current_connection)
            else:
                # Next hops via local loopback
                current_connection = \
                    SSHTunnelingConnectionAgent(server=self.loopback_address,
                                                username=self.jump_settings[jumpserver]['USERNAME'],
                                                remote_bind_address=self.path[index + 1],
                                                remote_bind_port=self.jump_settings[self.path[index + 1]][
                                                    'PORT'],
                                                ssh_pkey=self.jump_settings[jumpserver]['RSA_KEY_FILE'],
                                                port=current_connection.local_port,
                                                password=password)
                self.jumpserver_collection.append(current_connection)

            index += 1

        # Set local port for last connection
        self.local_port = current_connection.local_port

        return current_connection.local_port

    def connect_jumpserver_final(self, destination, port):
        """
        Method required to open connection via final jumpserver to host.

        Args:
            port (int): Port for end destination (TCP only)
            destination (basestring): String to destination address.
        """

        # Validate if there is still a connection, drop it if there is.
        if self.final_connection:
            logging.warn("Still connected to final jump node, forcing disconnect!")
            self.disconnect_jumpserver_final()

        # Connect to last jumpserver in the path
        jumpserver = self.path[-1]

        # Final connection note
        logging.debug("Connecting to final jump node {}...".format(jumpserver))

        # If password available, set password.
        password = None
        if 'PASSWORD' in self.jump_settings[jumpserver]:
            password = self.jump_settings[jumpserver]['PASSWORD']

        if len(self.jumpserver_collection) < 1:
            # First connection to direct host
            current_connection = \
                SSHTunnelingConnectionAgent(server=jumpserver,
                                            username=self.jump_settings[jumpserver]['USERNAME'],
                                            remote_bind_address=destination,
                                            remote_bind_port=port,
                                            ssh_pkey=self.jump_settings[jumpserver]['RSA_KEY_FILE'],
                                            port=self.jump_settings[jumpserver]['PORT'],
                                            password=password)
        else:
            # Next hops via local loopback
            current_connection = \
                SSHTunnelingConnectionAgent(server=self.loopback_address,
                                            username=self.jump_settings[jumpserver]['USERNAME'],
                                            remote_bind_address=destination,
                                            remote_bind_port=port,
                                            ssh_pkey=self.jump_settings[jumpserver]['RSA_KEY_FILE'],
                                            port=self.local_port,
                                            password=password)

        # Set final connectivity instance!
        self.final_connection = current_connection

        return self.final_connection.local_port

    def disconnect_jumpserver_final(self):
        """
        Method terminate open connection to jumpservers.
        """

        if isinstance(self.final_connection, SSHTunnelingConnectionAgent):
            logging.debug("Terminating SSH tunnel to final host!")
            self.final_connection.disconnect()
            self.final_connection = None
        else:
            logging.debug("Already disconnected from end node.")

    def disconnect_jumpserver_chain(self):
        """
        Method terminate open connection to jumpservers.
        """

        if isinstance(self.final_connection, SSHTunnelingConnectionAgent):
            logging.warn("Still connected to final host!")
            self.disconnect_jumpserver_final()

        logging.debug("Terminating jumpserver connection chain!")
        for jumpserver in reversed(self.jumpserver_collection):
            jumpserver.disconnect()


class ConnectionHandler(object):
    """
    ConnectionHandler for universal connection responses for pExpect in this module.
    """

    def __init__(self):
        self.handlers = [pexpect.TIMEOUT, pexpect.EOF,
                         '[U|u]sername: ',
                         '[P|p]assword: ',
                         '\w+#',
                         '\w+>',
                         'Permission denied',
                         '.*Connection refused.*',
                         '.*Offending RSA key.*']

    def get_handlers(self, added_value=None):
        # type: (str) -> lst
        """
        Function to return handler and allow user to add first handler.

        Args:
            added_value: String that can be used as re.compile

        Returns:
            list: List of re.compile strings.
        """
        return_value = [added_value]

        for v in self.handlers:
            return_value.append(v)

        return return_value


class TunnelConnectionAgent(object):
    """
    Connection Agent to manage connection to the hosts.

    Module is written to allow jumpserver chaining based on the JumpCollection class instance.

    Roadmap: Allow session management on VTY sessions over SSH or Telnet. Pre-build class: ConnectionAgent (Alpha)
    """

    def __init__(self, am=accountmgr.AccountManager,
                 ssh_command='ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no USER@HOST -p PORT',
                 telnet_command='telnet HOST PORT',
                 client_connection_type='SSH',
                 timeout=10,
                 shell='/bin/bash',
                 jumpservers=None):
        """
        Connection Manager for managing connections. (Via Jumpnode (Tunnel mode))

        Tracking connectivity status and disconnect on failure.

        Status:
            500 : Starting value, no connection.
            200 : Not connected status. For connection method.
            101 : Privilage mode
            100 : Enable mode

        Args:
            am (object): Account Manager Object to obtain security credentials securely.
            ssh_command (basestring): Variable for current SSH command
            telnet_command (basestring): Variable for current Telnet command
            timeout (int): Variable for current timeout value (seconds)
            client_connection_type (basestring): Default connection type [SSH or TELNET]
            shell (basestring): Shell command (future use)
            jumpservers (object): Jumpserver instance
        """

        self.prompt = pexpect.spawn  # PEXPECT Class definition for prompt.
        self.am = am

        # Jump settings
        self.jumpservers = JumpCollection

        if isinstance(jumpservers, JumpCollection):
            self.jumpservers = jumpservers
        else:
            logging.error("Wrong Jumpserver type! (should be "
                          "lib.ConnectionManager.JumpCollection or None)")
            raise

        # Environmental settings
        self.shell = shell
        self.ssh_command = ssh_command
        self.telnet_command = telnet_command
        self.timeout = timeout

        # Connection types
        self.allowed_connection_types = ['SSH', 'TELNET']
        if client_connection_type not in self.allowed_connection_types:
            logging.error("{} is not a allowed connection type!".format(client_connection_type))
            raise
        else:
            self.conn_type = client_connection_type

        # Connected state
        self.connected = False
        self.connected_host = None

    def connect(self, host, connection_protocol=None, port=None):
        """
        Connection method to connect to end node.

        Args:
            port (int): Port number (TCP)
            connection_protocol (basestring): Protocol for connectivity to end host. (SSH or Telnet) (Default on init)
            host (basestring): Hostname for documentation purposes (logging)

        Returns:
            bool: Connection status
        """

        logging.debug("Trying to connect to end node ({})...".format(host))

        # Check for current connectivity and disconnect if connected.
        if self.connected:
            logging.warn("Still connected to end node, disconnecting first!")
            logging.warn("Check your programming, disconnect for each end node!")
            self.disconnect()

        # Set values if given or use initial value and check allowed values.
        if connection_protocol is None:
            connection_protocol = self.conn_type
        elif connection_protocol not in self.allowed_connection_types:
            logging.error("{} not a allowed connection type. Falling back to: {}".
                          format(connection_protocol, self.conn_type))
            connection_protocol = self.conn_type

        # Default status set.
        status = 500
        logging.debug("Trying to connect to {}...".format(host))

        # Setting up connection per type selected.
        if connection_protocol == 'SSH':
            # Port settings, fallback to default (22) if not set.
            if port is None:
                port = 22

            # First setup final SSH tunnel connection.
            self.jumpservers.connect_jumpserver_final(host, port)

            # Create PEXPECT instance after login with SSH.
            status = self.ssh_connection(self.jumpservers.loopback_address,
                                         port=self.jumpservers.final_connection.local_port,
                                         am_host_ref=host)

        elif connection_protocol == 'TELNET':
            # Port settings, fallback to default (23) if not set.
            if port is None:
                port = 23

            # First setup final SSH tunnel connection.
            self.jumpservers.connect_jumpserver_final(host, port)

            # Create PEXPECT instance after login with TELNET.
            status = self.telnet_connection(self.jumpservers.loopback_address,
                                            port=self.jumpservers.final_connection.local_port,
                                            am_host_ref=host)

        # No other connection type yet.
        else:
            logging.error("Other connection types not yet supported ({})!".format(connection_protocol))

        # If any other connecting value, disconnect otherwise accept connection.
        if status > 101:
            self.disconnect()
        else:
            self.connected = True
            self.connected_host = host

        return self.connected

    def disconnect(self):
        """
        Disconnect function to terminate connection to a host.
        """

        self.prompt.close() # Close PEXPECT first
        self.jumpservers.disconnect_jumpserver_final() # Close SSH tunnel
        # Reset connected state
        self.connected = False
        self.connected_host = None

    def telnet_connection(self, host, port=23, am_host_ref=None):
        """
        Function to setup Telnet connection.

        Args:
            port (int): Integer for connecting to port. (May vary due to TCP port forwarding)
            host (basestring): String for host connection address. (May vary due to TCP port forwarding to loopback)
            am_host_ref (basestring): Hostname reference for logging and credential selection in AccountManager.
        """

        # Original command for replacement.
        s = self.telnet_command

        # Collection user credentials
        user = self.am.get_username(am_host_ref)
        password = self.am.get_password(am_host_ref, user)

        # Default port detection.
        if port != 23:
            logging.debug("Alternative Telnet port detected ({}). Using this port.".format(port))

        # Setup connection command for PEXPECT
        conn = s.replace("HOST", host)
        conn = conn.replace("PORT", str(port))

        logging.debug("Connecting using '{}' command...".format(conn))

        # Not connected status. For connection method.
        status = 200

        # Create spawn instance for PEXPECT.
        prompt = pexpect.spawn(conn, timeout=self.timeout)

        # Possible prompt returns
        prompts = [
            '[U|u]sername:',
            '[P|p]assword:',
            '\n\w+#',
            '\n\w+>',
            pexpect.TIMEOUT,
            pexpect.EOF
        ]

        # User prompt handeling
        logging.debug("Pending user prompt...")
        response = prompt.expect(prompts, timeout=self.timeout);
        if response == 0:
            logging.debug("Sending username! ({})".format(user))
            prompt.sendline(user);
            status = 100
        else:
            logging.warn("No user prompt, exiting for this node. (Line:{} {})".format(
                prompt.before, prompt.after))
            status = 200

        # Password handeling, only continue on user send.
        if status == 100:
            logging.debug("Pending password prompt!")
            response = prompt.expect(prompts, timeout=self.timeout);
            if response == 1 and status == 100:
                logging.debug("Sending password!")
                prompt.sendline(password);
                status = 100
            else:
                logging.warn("No password prompt, exiting for this node. (Line:{} {})".format(
                    prompt.before, prompt.after))
                status = 200

        # Prompt handeling, only continue on password send.
        if status == 100:
            logging.debug("Pending Prompt!")
            response = prompt.expect(prompts, timeout=self.timeout);
            if response == 2 and status == 100:
                logging.debug("Prompt detected!")
                status = 100
            else:
                logging.warn("No prompt, exiting for this node. (Line:{})".format(prompt.before))
                status = 200

        self.prompt = prompt

        return status

    def ssh_connection(self, host, port=22, am_host_ref=None):
        """
        Function to setup SSH connection.

        Args:
            port (int): Integer for connecting to port. (May vary due to TCP port forwarding)
            host (basestring): String for host connection address. (May vary due to TCP port forwarding to loopback)
            am_host_ref (basestring): Hostname reference for logging and credential selection in AccountManager.
        """

        # Original command for replacement.
        s = self.ssh_command

        # Collection user credentials
        user = self.am.get_username(am_host_ref)
        password = self.am.get_password(am_host_ref, user)

        # Default port detection.
        if port != 22:
            logging.debug("Alternative SSH port detected ({}). Using this port.".format(port))

        # Setup connection command for PEXPECT
        conn = s.replace("HOST", host)
        conn = conn.replace("PORT", str(port))
        conn = conn.replace("USER", str(user))

        logging.debug("Connecting using '{}' command...".format(conn))

        # Not connected status. For connection method.
        status = 200

        # Create spawn instance for PEXPECT.
        prompt = pexpect.spawn(conn, timeout=self.timeout)

        # Possible prompt returns
        prompts = [
            '[U|u]sername:',
            '[P|p]assword:',
            '\n\w+#',
            '\n\w+>',
            pexpect.TIMEOUT,
            pexpect.EOF
        ]

        # Password handeling.
        logging.debug("Pending password prompt!")
        response = prompt.expect(prompts, timeout=self.timeout);
        if response == 1:
            logging.debug("Sending password!")
            prompt.sendline(password);
            status = 100
        else:
            logging.warn("No password prompt, exiting for this node. (Line:{} {})".format(
                prompt.before, prompt.after))
            status = 200

        # Prompt handeling, only continue on password send.
        if status == 100:
            logging.debug("Pending Prompt!")
            response = prompt.expect(prompts, timeout=self.timeout);
            if response == 2 and status == 100:
                logging.debug("Prompt detected!")
                status = 100
            else:
                logging.warn("No prompt, exiting for this node. (Line:{})".format(prompt.before))
                status = 200

        self.prompt = prompt

        return status

    def terminal_lenth_cisco(self, host):
        """
        Function to set unlimit terminal lenth for Cisco devices.

        Args:
            host (basestring): Hostname for documentation
        """

        logging.debug('Setting unlimit Terminal length!')
        self.send_command(host, 'terminal length 0', allow_more_show=True)

    def send_command(self, host, command, allow_more_show=False):
        """
        Function to send command. Validation for 'show'-commands prior to execution.

        Args:
            host (basestring): Hostname for documentation
            command (basestring): Command to send to node
            allow_more_show (bool): Validation for 'show'-commands only.
        """

        # RegEx searcher for "show"-commands.
        search_show = re.search(r'show\s\w*', command)

        # Possible prompt returns
        prompts = [
            '\n\w+#',
            '\n\w+>',
            pexpect.TIMEOUT,
            pexpect.EOF
        ]

        # Check for valid 'show'-command and overwrite if allowed
        # Check if correct prompt is pending for command!
        if (allow_more_show or search_show) and self.connected:

            self.prompt.sendline(command)
            logging.debug("Executing \"{}\" on {}... ".format(command, self.connected_host))
            logging.debug("Pending for prompt...")

            response = self.prompt.expect(prompts, timeout=self.timeout)

            if response == 0 or response == 1:
                logging.debug("Command executed! Return output!")
                return self.connected, self.prompt.before
            else:
                if response == 2:
                    logging.warning("Response timed out, consider increasing time out value in setting file!")
                logging.critical("Undesired response! Disconnecting from host ({})!".format(self.connected_host))
                self.disconnect()
                # Return error value for analyses.
                return self.connected, "Error: Disconnected from host by response error. " \
                       "(No prompt)\nLast output:\n{}\nPexpect status:\n{}".format(self.prompt.before, self.prompt)
        else:
            # Correct warning displays
            if not self.connected:
                logging.debug("Not connected ({})! Skipping command ({}) check!".format(host,
                                                                                        command))
            if not search_show and not allow_more_show:
                warning = "Command \"{}\" has not been executed! This is no \"show\"-command." \
                          "Make sure you execute fully typed show commands.".format(command)
                logging.warn(warning)
            return self.connected, None


# noinspection PyArgumentList,PyCallByClass,PyTypeChecker,PyUnresolvedReferences
class ConnectionAgent(object):
    """
    Connection Agent to manage connection to the hosts.
    May invoke JumphostAgent to connect to multiple jumphosts
    """

    def __init__(self, am=accountmgr.AccountManager,
                 client_connection_type='SSH',
                 ssh_command='ssh USER@HOST -p PORT',
                 telnet_command='telnet HOST:PORT',
                 timeout=10,
                 shell='/bin/bash',
                 jumpservers=None,
                 max_retry=5):
        # type: (obj, str, str, str, int, str, lst, int) -> obj
        """
        Connection Manager for managing connections. (Via Jumpnode)

        Args:
            am: Account Manager Object to obtain security credentials securely. (obj)
            client_connection_type: Connection type [SSH || TELNET] (str)
            ssh_command: Variable for current SSH command (str)
            telnet_command: Variable for current Telnet command (str)
            timeout: Variable for current timeout value (int)
            shell: Shell command (future use) (str)
            jumpservers: List of Device objects (lst -> obj)
            max_retry: Maximum retry attempts for connections (int)

        Returns:
            object: Connection Object for maintaining connection to hosts.
        """

        self.prompt = pexpect.spawn  # PEXPECT Class definition for prompt.
        self.ch = ConnectionHandler()  # Connection handler object (obj)
        self.am = am

        # Connection settings
        self.ssh_command = ssh_command
        self.telnet_command = telnet_command
        self.timeout = timeout
        self.max_retry = max_retry
        self.jumpservers = jumpservers
        self.conn_type = client_connection_type

        self.initial_values = {'CONNECTION_TYPE': client_connection_type,
                               'SSH_COMMAND': ssh_command,
                               'TELNET_COMMAND': telnet_command,
                               'TIMEOUT': timeout}  # Initial settings for fallback

        # Prompt settings
        self.current_prompt = None  # Current prompt (str)
        self.fallback_prompt = None  # Current fallback prompt (Last Jumpserver) (str)
        self.fallback_jumpserver_name = 'localhost'  # Current fallback prompt (Last Jumpserver) (str)
        self.current_connected_host = None  # Name of host currently connected to (str)

        # TODO
        self.shell = shell

        # TODO Initial setup without jumpserver support
        if len(self.jumpservers) > 0:
            self.connect_jumpserver(self.jumpservers)
        else:
            logging.error("For now connection can only be build through a jumpserver.")
            logging.error("Direct connection feature will be build in the near future.")
            logging.error("Script will exit now.")
            sys.exit(101)

    @staticmethod
    def _get_status():
        """
        Function to return status code. Documentation purposes.
        """

        status_pool = {100: 'SUCCESSFUL',
                       101: 'PRIVILEGE_MODE',
                       102: 'ENABLE_MODE',
                       103: 'CONFIG_MODE',
                       150: 'USERNAME_PROMPT_DETECTED',
                       151: 'PASSWORD_PROMPT_DETECTED',
                       200: 'FAILED',
                       201: 'FALLBACK',
                       202: 'AUTHENTICATION_ISSUE',
                       300: 'UNKNOWN'}

        return status_pool

    def _jumpconnect_check(self, host):
        # type: (str) -> bool
        """
        Function to check if hostname or ip is part of jumpserver list.

        Args:
            host (str): hostname or ip

        Returns:
            bool: Boolean > jumpserver in list
        """
        for j in self.jumpservers:
            if host == j.name:
                return True

        return False

    def _check_prompt(self, host):
        # type: (str) -> bool
        """
        Function to check if current prompt is there.

        Args:
            host (str): hostname or ip

        Returns:
            bool: Boolean > connected to prompt
        """

        response_bool = False

        if host == self.current_connected_host:

            self.prompt.sendline()
            response = self.prompt.expect(self.current_prompt, timeout=self.timeout)

            if response == 0:
                response_bool = True
                logging.debug("Correct prompt detected! ({})".format(self.current_prompt))
            else:
                logging.debug("Other prompt detected! ({})".format(self.prompt.before))
        else:
            logging.warn("Not current host! ({} vs {})".format(host, self.current_connected_host))
            return response_bool

    @staticmethod
    def _special_escape(string):
        # type: (str) -> str
        """
        Function to fix special characters.

        Args:
            string (str): sting for fix

        Returns:
            return_string:  string with escape characters
        """
        special_lst = ["$"]
        return_string = []

        for x in string:
            if x in special_lst:
                return_string.append(u'\\\\')
            return_string.append(x)

        return ''.join(return_string)

    def host_connect(self, host, connection_type=None,
                     timeout=None, expected_prompt=None,
                     port=None):
        # type: (str, str, int, str, int) -> int
        """
        Function to connect to host. And return status.

        Args:
            host: Host as a string (IP or hostname)
            connection_type: Connection type, options: SSH or TELNET
            timeout: Timeout setting before connection times out.
            expected_prompt: String for re unicode to detect prompt.
            port: Port to connect to.

        Returns:
            status: Status code of connection status
        """

        # Set values if given or use initial value.
        if connection_type is None:
            connection_type = self.conn_type
        if timeout is None:
            timeout = self.timeout
        if expected_prompt is None:
            expected_prompt = str(host) + "#"

        logging.debug("Trying to connect to {}...".format(host))

        # Setting up connection per type selected.
        if connection_type == 'SSH':
            # Port settings, fallback to default if not set.
            if port is None:
                port = 22

            status = self.ssh_connection(host, timeout=timeout,
                                         expected_prompt=expected_prompt,
                                         port=port)
        elif connection_type == 'TELNET':
            # Port settings, fallback to default if not set.
            if port is None:
                port = 23

            status = self.telnet_connection(host, timeout=timeout,
                                            expected_prompt=expected_prompt,
                                            port=port)
        # No other connection type yet.
        else:
            logging.error("Other connection types not yet supported ({})!".format(connection_type))
            sys.exit(101)

        # Detecting and validating prompt if connected
        if status == 100:
            status = self.prompt_detect(host, expected_prompt=expected_prompt)

        # Acting on connection status
        # When not correctly connected. Try to fallback if connected to jumpserver.
        # Except when trying to connect to jumpserver
        if status >= 102:
            logging.error('Could not detect prompt for {}. Trying to fall back! Status: {}'.format(host, status))
            status = self.disconnect_host(host)
            if status == 100:
                status = 201

        # Setting current hosts and status reaction for user to display.
        if status == 100:
            logging.debug('Successfully connected to {}!'.format(host))
            self.current_connected_host = host
        elif status == 101:
            logging.warn('Successfully connected to {} (privilege mode)!'.format(host))
            self.current_connected_host = host
        elif status == 200 or status == 201:
            logging.error('Could not connect to {}!'.format(host))
        else:
            logging.critical('Unknown error ({}) for {}!'.format(status, host))
            status = 300

        return status

    # noinspection PyUnusedLocal
    def password_handler(self, host, user,
                         expected_prompt=None,
                         password=None, password_type='Fixed',
                         timeout=None, max_retry_count=5,
                         ad=False):
        # type: (str, str, str, str, str, int, int, bool) -> int
        """
        Password prompt handler. When expecting password prompt. Call this function to
        handle this prompt and return the status code. An active prompt is expected.

        Basic error handling to return specific error codes has been build in.

        Args:
            host: Host as a string (IP or hostname)
            user: Username as ustring.
            expected_prompt: String for expected prompt as re ustring
            password: Password as ustring.
            password_type: Password type (Fixed only) Roadmap: RSA
            timeout: Timeout for connection as integer
            max_retry_count: Max attempts for connection as integer
            ad: Password prompt already detected flag

        Returns:
            status: Connection status.
        """

        # Connection handler list
        connection_handler = self.ch.get_handlers(expected_prompt)

        # Setup variables
        prompt_detected = False
        retry_count = 0
        status = 0

        if password is None:
            password = self.am.get_password(host, username=user)
        if timeout is None:
            timeout = self.timeout

        # If password is already detected, send password directly.
        if ad:
            logging.debug("Function called with prompt already detected. Sending password...")
            self.prompt.sendline(password)

        # Loop until prompt detection.
        while not prompt_detected and retry_count <= max_retry_count:

            response = self.prompt.expect(connection_handler, timeout=timeout)

            if not prompt_detected and retry_count > 0:
                logging.debug("Password detection for {} ({} out of {})...".format(host, retry_count,
                                                                                   max_retry_count))

            if response == 0:
                logging.debug("Seems prompt has returned! (Expected)")
                prompt_detected = True
                status = 100
            elif response == 1:
                logging.error("Connection timed out! Reading current buffer...")
                logging.error("Dumping due to development...")
                logging.error(self.prompt)
                status = 300
            elif response == 3:
                logging.warn("Seems like falling back to username. Re-entry username!")
                self.user_handler(host, user=user, expected_prompt=expected_prompt,
                                  timeout=timeout, ad=True)
                status = 150
            elif response == 4:
                logging.debug("Password line detected!")
                logging.debug("Sending password...")
                self.prompt.sendline(password)
                status = 151
            elif response == 5 or response == 6:
                logging.info("Seems prompt has returned! (Not expected)")
                prompt_detected = True
                status = 100
            elif response == 7:
                logging.error("Authentication issue for {}".format(host))
                password = self.am.get_password(host, username=user, reset=True)
                status = 202
            elif response == 8:
                logging.error("Connection issues, cannot connect!")
                prompt_detected = True
                status = 200
            elif response == 9:
                logging.error("Connection issues, cannot connect!")
                logging.error("RSA Key seems not matching, "
                              "make sure the correct key is on {} for {}!".
                              format(self.fallback_jumpserver_name, host))
                prompt_detected = True
                status = 202
            else:
                raise

            retry_count += 1

        return status

    def user_handler(self, host, user=None,
                     expected_prompt=None,
                     timeout=None, max_retry_count=5, ad=False):
        # type: (str, str, str, str, str, int, int, bool) -> int
        """
        User prompt handler. When expecting user prompt. Call this function to
        handle this prompt and return the status code. An password prompt is expected.

        Basic error handling to return specific error codes has been build in.

        Args:
            host: Host as a string (IP or hostname)
            user: Username as ustring.
            expected_prompt: String for expected prompt as re ustring
            timeout: Timeout for connection as integer
            max_retry_count: Max attempts for connection as integer
            ad: Password prompt already detected flag

        Returns:
            object:
        """

        # Connection handler list
        if expected_prompt is None:
            expected_prompt = '\w+[#|>]'

        connection_handler = self.ch.get_handlers(expected_prompt)

        # Setup variables
        prompt_detected = False
        retry_count = 0
        status = 0

        if user is None:
            user = self.am.get_username(host)
        if timeout is None:
            timeout = self.timeout

        # If username prompt is already detected, send username directly.
        if ad:
            logging.debug("Function called with prompt already detected. Sending username...")
            self.prompt.sendline(user)

        # Loop until prompt detection.
        while not prompt_detected and retry_count <= max_retry_count:

            response = self.prompt.expect(connection_handler, timeout=timeout)

            if not prompt_detected and retry_count > 0:
                logging.debug("Retry for username for {}... "
                              "({} out of {})...".format(host, retry_count, max_retry_count))

            if response == 0 or response == 5 or response == 6:
                logging.warn("Seems prompt has returned and no password is required!")
                prompt_detected = True
                status = 100
            elif response == 1:
                logging.error("Connection timed out! Reading current buffer...")
                logging.error("Dumping due to development...")
                logging.error(self.prompt)
                status = 200
            elif response == 3:
                logging.debug("Username line detected!")
                logging.debug("Sending username...")
                self.prompt.sendline(user)
                status = 150
            elif response == 4:
                logging.debug("Password line detected!")
                prompt_detected = True
                status = 151
            else:
                logging.critical("Unknown response!")
                logging.error(self.prompt)
                raise

            retry_count += 1

        return status

    def prompt_detect(self, host, expected_prompt=None):
        """
        Prompt detector.
        """

        # Connection handler list
        connection_handler = self.ch.get_handlers(expected_prompt)

        detected = False
        detect_count = 1
        max_detect_count = 3
        status = 0

        logging.debug("Trying to receive prompt on {} ({})...".format(host, expected_prompt))
        self.prompt.sendline()

        while not detected and detect_count < max_detect_count:
            response = self.prompt.expect(connection_handler, timeout=self.timeout)

            if response == 0:
                logging.debug("Expected prompt received!")
                detected = True
                status = 100
            elif response == 5 and expected_prompt is not None:
                logging.debug("Enable mode prompt received!")
                detected = True
                status = 100
            elif response == 6 and expected_prompt is not None:
                logging.warn("Privilege mode prompt received!")
                detected = True
                status = 101
            elif response == 0:
                logging.debug("Action timed out, retry ({} out of {}).".format(detect_count, max_detect_count))
                self.prompt.sendline()
            else:
                logging.critical("Error!")
                raise

            detect_count += 1

        try:
            r_line = self.prompt.after.splitlines()
            actual_prompt = r_line[-1]
            logging.debug("Detected prompt '{}'!".format(actual_prompt))
            self.current_prompt = actual_prompt
        except:
            logging.critical("Could not detect prompt! "
                             "Do not know where we are!")
            raise

        return status

    def telnet_connection(self, host, timeout=10, port=23, expected_prompt=None):
        """
        Function to setup Telnet connection.
        """

        # Original command for replacement.
        s = self.telnet_command

        # Collection user credentials
        user = self.am.get_username(host)
        password = self.am.get_password(host, user)

        # Default port detection.
        if port != 23:
            logging.info("Alternative Telnet port detected ({}). Using this port.".format(port))

        # Setup connection cmd
        conn = s.replace("HOST", host)
        conn = conn.replace("PORT", str(port))
        # TODO Option parser to be added

        logging.debug("Connecting using '{}' command...".format(conn))

        # If no spawn instance exists. Create one.
        if isinstance(self.prompt, pexpect.spawn):
            self.prompt.sendline(conn)
        else:
            self.prompt = pexpect.spawn(conn, timeout=timeout)

        # User handling
        status = self.user_handler(host, user=user,
                                   expected_prompt=expected_prompt,
                                   timeout=timeout, max_retry_count=self.max_retry)

        # Password handling
        if status == 100:
            status = self.password_handler(host, user,
                                           expected_prompt=expected_prompt,
                                           password=password, timeout=timeout)
        elif status == 151:
            status = self.password_handler(host, user,
                                           expected_prompt=expected_prompt,
                                           password=password, timeout=timeout,
                                           ad=True)

        return status

    def ssh_connection(self, host, timeout=10, port=22, expected_prompt=None):
        """
        Function to setup SSH connection.
        """

        # Original command for replacement.
        s = self.ssh_command

        # Collection user credentials
        user = self.am.get_username(host)
        password = self.am.get_password(host, user)
        password_type = self.am.get_password_type(host)

        # Default port detection.
        if port != 22:
            logging.info("Alternative SSH port detected ({}). Using this port.".format(port))

        # Setup connection cmd
        cmd = s.replace("USER", user)
        cmd = cmd.replace("HOST", host)
        cmd = cmd.replace("PORT", str(port))
        # TODO Option parser to be added

        logging.debug("Connecting using '{}' command...".format(cmd))

        # If no spawn instance exists. Create one.
        if isinstance(self.prompt, pexpect.spawn):
            self.prompt.sendline(cmd)
        else:
            self.prompt = pexpect.spawn(cmd, timeout=timeout)

        status = self.password_handler(host, user,
                                       expected_prompt=expected_prompt,
                                       password=password, password_type=password_type,
                                       timeout=timeout)

        return status

    def connect_jumpserver(self, path):
        """
        Function to connection to Jumpserver Path and return pexpect with active prompt.

        Args:
            path: Pa
        """

        # Check for reoccurring jumpservers in existing path list.
        j_list = []
        for j in path:
            if j.name in j_list:
                logging.warn("Jumpserver {} more then once in jump path. "
                             "Delay in collection is expected!".format(j.name))
            j_list.append(j.name)

        current_jumpserver = self.fallback_jumpserver_name

        # Hop to current jumpserver and connect to the following
        logging.debug("Trying to connect to jumpservers!")

        for jumpserver in path:

            jumpserver_hostname = jumpserver.name

            if current_jumpserver != jumpserver_hostname:
                # Connect to jumphost
                status = self.host_connect(jumpserver_hostname,
                                           connection_type=jumpserver.connection_settings['CONNECTION_TYPE'],
                                           timeout=jumpserver.connection_settings['TIMEOUT'],
                                           port=jumpserver.connection_settings['CONNECTION_PORT'],
                                           expected_prompt=jumpserver.connection_settings['PROMPT'])

                self.ssh_command = jumpserver.connection_settings['SSH_COMMAND']
                self.telnet_command = jumpserver.connection_settings['TELNET_COMMAND']

                if status != 100:
                    logging.critical('Jumpserver connection unsuccessful! '
                                     'Connection required!')
                    sys.exit(103)
                    # else:
                    #     for cmd in jumpserver.connection_settings['POST_COMMANDS']:
                    #         self.send_command(jumpserver_hostname, cmd, allow_more_show=True)
            else:
                logging.debug("Already connected to: {}".format(current_jumpserver))

            current_jumpserver = jumpserver_hostname
            self.fallback_jumpserver_name = current_jumpserver
            self.fallback_prompt = jumpserver.connection_settings['PROMPT']

        logging.debug("Connected to all jumpservers!")

    def cisco_term_len(self, host):
        # type: (str) -> None
        """
        Function to set terminal length for Cisco devices and disconnect if response is unknown.

        Args:
            host: Hostname or IP
        """

        # Terminal lenght commands for Cisco devices
        term = 'terminal length 0'

        self.send_command(host, term, allow_more_show=True)

    def send_command(self, host, command, allow_more_show=False):
        # type: (str, str, bool) -> str
        """
        Function to send command. Validation for 'show'-commands prior to execution.

        Args:
            command: Command to send to node
            host: Hostname or IP
            allow_more_show: Validation for 'show'-commands only.

        Returns:
            str: Return response on return of current prompt.
        """

        search_show = re.search(r'show\s\w*', command)

        # Check for valid 'show'-command and overwrite if allowed
        # Check if correct prompt is pending for command!
        if self._check_prompt(host):
            if allow_more_show or search_show:

                self.prompt.sendline(command)
                logging.info("Executing \"{}\"... and expecting: {}".format(command, self.current_prompt))
                response = self.prompt.expect([self.current_prompt, pexpect.TIMEOUT], timeout=self.timeout)

                if response == 0:
                    logging.debug("Command executed! Return output!")
                    return self.prompt.before
                else:
                    logging.critical("Undesired response! Disconnecting from host!")
                    self.disconnect_host(host)
                    return "Error: Disconnected from host."
            else:
                warning = "Command \"{}\" has not been executed! This is no \"show\"-command." \
                          "Make sure you execute fully typed show commands.".format(command)
                logging.warn(warning)
                return warning
        else:
            error = "Not connected to {}, will not execute command!".format(host)
            logging.error(error)
            return error

    # noinspection PyUnusedLocal
    def disconnect_host(self, host):
        # type: (init) -> int
        """
        Function to fallback to original prompt or disconnect self.prompt

        Args:
            host: Host to disconnection from.

        Returns:
            int: Status code for disconnect
        """

        break_fallback = False
        count = 1
        max_count = 7
        timeout = 3
        status = None

        # Base check
        if self.current_connected_host != host:
            if host == self.fallback_jumpserver_name:
                logging.error("Do not need to disconnect from jumphost! Cancel disconnect!")
            elif self.current_connected_host == self.fallback_jumpserver_name:
                logging.error('Currently not connected to {}! '
                              'Connected to jumphost!'.format(host))
                status = 201
            else:
                logging.error('Currently not connected to {}! '
                              'Still connected to {}!'.format(host, self.current_connected_host))
                status = 200
        elif self.jumpservers is None:
            logging.debug("Disconnected from prompt!")
            self.prompt = None
            status = 100
        else:

            logging.debug('Trying to disconnect from {}...'.format(host))

            # Continue to try and fallback.
            while break_fallback is False:

                logging.debug('Trying to fall back ({} out of {})...'.format(count, max_count))

                if count > 3:
                    logging.info('Trying more aggressive fallback method!')
                    logging.debug('Current buffer: {}'.format(self.prompt.buffer))

                response = self.prompt.expect([self.fallback_prompt, pexpect.TIMEOUT], timeout=self.timeout)

                if response == 0:
                    logging.debug('Disconnected from {}!'.format(self.current_connected_host))
                    self.current_connected_host = self.fallback_jumpserver_name
                    self.current_prompt = self.fallback_prompt
                    if self._check_prompt(self.fallback_jumpserver_name):
                        logging.debug('Connected to {}!'.format(self.fallback_jumpserver_name))
                        status = 100
                    else:
                        status = 200
                    break_fallback = True
                elif response == 1 and count > 3:
                    self.prompt.sendline()
                    self.prompt.sendline('q')
                elif response == 1:
                    self.prompt.sendline()
                    self.prompt.sendline('exit')
                else:
                    logging.critical("Unknown error!")
                    raise

                if count > max_count:
                    logging.critical('Could not fall back to {}'.format(self.fallback_prompt))
                    break_fallback = True
                    status = 200

                count += 1

        return status
