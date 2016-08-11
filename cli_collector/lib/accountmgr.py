# =============================================================================
# accountmgr.py
#
# # Author: Thomas Jongerius
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================

import ConfigParser
import getpass
import fnmatch
import logging
import sys

try:
    import keyring
except ImportError:
    logging.error("No keyring library installed. Password must be provided in mannualy.")
except Exception as e:
    logging.error('Unknown error! {}'.format(e))
    sys.exit(200)

def make_realm(name):
    """
    Function for realm creation
    """
    return "Accelerated Upgrade@{}".format(name)

class AccountManager(object):
    """
    Account manager object.
    """
    def __init__(self,
                 config_file,
                 username_cb=None,
                 password_cb=None,
                 reset=False):
        if config_file is None:
            logging.error("No account details set!")
            sys.exit(201)

        self.config_file = config_file
        self.config = ConfigParser.SafeConfigParser({'username': '', 'password_type': ''})
        self.config.read(self.config_file)
        self.config.write(open(self.config_file, 'w'))
        self.allowed_password_types=['Fixed', 'PublicKey', 'NoPassword']
        self.reset = reset
        self.already_reset = []

        if self.reset:
            logging.warn('Password reset flag set, passwords will be prompted!')

        self.username_cb = username_cb \
            if callable(username_cb) else self._prompt_for_username
        self.password_cb = password_cb \
            if callable(password_cb) else self._prompt_for_password

    def _prompt_for_username(self, prompt):
        # Not sure needed
        return None

    def _prompt_for_password(self, prompt):
        return getpass.getpass(prompt)

    def _find_section(self, realm):
        for section in iter(self.config.sections()):
            if fnmatch.fnmatch(realm, section):
                break
        else:
            section = 'DEFAULT'
        return section

    def _get_username(self, section):
        username = self.config.get(section, 'username')
        if username == '':
            return None
        return username

    def get_username(self, realm):
        username = self._get_username(self._find_section(realm))
        if not username:
            username = getpass.getuser()
        return username


    def _get_password_type(self, section):
        password_type = self.config.get(section, 'password_type')
        if password_type == '':
            return None
        return password_type

    def get_password_type(self, realm):
        password_type = self._get_password_type(self._find_section(realm))
        if password_type:
            if password_type not in self.allowed_password_types:
                logging.error('Password type not allowed! Fall back to fixed.')
                password_type = None
        if not password_type:
            password_type = 'Fixed'
        return password_type

    def get_password(self, realm, username=None, interact=True, reset=False):
        section = self._find_section(realm)
        config_user_name = self._get_username(section)
        if not config_user_name or username != config_user_name:
                return Noner
        if not username:
            username = config_user_name

        try:
            if self.reset or reset:
                if username not in self.already_reset or reset:
                    keyring.delete_password(make_realm(section), username)
                    self.already_reset.append(username)
            password = keyring.get_password(make_realm(section), username)
        except:
            password = None

        if password is None and interact:
            prompt = "{}@{} Password: ".format(username, realm)
            password = self.password_cb(prompt)
            self.set_password(
                make_realm(section),
                username,
                password)

        return password

    def set_password(self, realm, username, password):
        try:
            keyring.set_password(
                realm,
                username,
                password
            )
        except:
            pass

    def get_login(self, realm):
        username = self.get_username(realm)
        password = self.get_password(realm, username)
        return (username, password)