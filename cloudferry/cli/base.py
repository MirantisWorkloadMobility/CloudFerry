# Copyright (c) 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

import yaml

from cloudferry import cfglib
from cloudferry.lib import config
from cloudferry.lib.utils import log


class ConfigMixin(object):
    def __init__(self, app, app_args, cmd_name=None):
        super(ConfigMixin, self).__init__(app, app_args, cmd_name)
        self.config = None

    def get_parser(self, prog_name):
        parser = super(ConfigMixin, self).get_parser(prog_name)
        parser.add_argument('config_path',
                            help='Configuration file')
        return parser

    def run(self, parsed_args):
        self.config = self.init_config(parsed_args.config_path)
        self.configure_logging()
        return super(ConfigMixin, self).run(parsed_args)

    def configure_logging(self, log_config=None, forward_stdout=None):
        if self.app.interactive_mode:
            forward_stdout = False
        log.configure_logging(log_config, self.app.options.debug,
                              forward_stdout)

    def init_config(self, config_path):
        conf = cfglib.init_config(config_path)
        if self.app.options.debug:
            conf.set_override('debug', self.app.options.debug, 'migrate')
        return conf


class YamlConfigMixin(ConfigMixin):
    def configure_logging(self, log_config=None, forward_stdout=None):
        super(YamlConfigMixin, self).configure_logging(
            log_config=log_config or 'configs/logging_config.yaml',
            forward_stdout=forward_stdout or False)

    def init_config(self, config_path):
        def import_legacy(cloud, cfg):
            cred = cloud.setdefault('credential', {})
            cred['auth_url'] = cfg.auth_url
            cred['username'] = cfg.user
            cred['password'] = cfg.password
            cred['region_name'] = cfg.region
            cred['https_insecure'] = cfg.insecure
            cred['https_cacert'] = cfg.cacert
            scope = cloud.setdefault('scope', {})
            scope['project_name'] = cfg.tenant
            ssh = cloud.setdefault('ssh', {})
            ssh['gateway'] = cfg.ssh_host
            ssh['username'] = cfg.ssh_user
            ssh['sudo_password'] = cfg.ssh_sudo_password
            ssh['connection_attempts'] = \
                cfglib.CONF.migrate.ssh_connection_attempts

        prev_legacy_config_path = None
        with open(config_path, 'r') as config_file:
            conf = yaml.load(config_file)
            clouds = conf.setdefault('clouds', {})
            for value in clouds.values():
                if 'legacy' not in value:
                    continue
                legacy_config_path, section = value.pop('legacy').split(':')
                if prev_legacy_config_path != legacy_config_path:
                    super(YamlConfigMixin, self).init_config(
                        legacy_config_path)
                import_legacy(value, getattr(cfglib.CONF, section))
            return config.load(conf)
