# Copyright (c) 2014 Mirantis Inc.
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


import copy

from cloudferrylib.utils import log
from cloudferrylib.utils import utils
from cloudferrylib.utils import mysql_connector
from cloudferrylib.utils import rbd_util
from cloudferrylib.utils import qemu_img
from cloudferrylib.utils import ssh_util

SRC = "src"
DST = "dst"
LOG = log.getLogger(__name__)


class Cloud(object):
    def __init__(self, resources, position, config):
        self.resources = resources
        self.position = position
        self.config = config

        self.cloud_config = self.make_cloud_config(self.config, self.position)
        self.init_resources(self.cloud_config)
        self.hosts_with_bbcp = set()

    @staticmethod
    def make_cloud_config(config, position):
        cloud_config = utils.ext_dict(migrate=utils.ext_dict(),
                                      cloud=utils.ext_dict(),
                                      import_rules=utils.ext_dict(),
                                      mail=utils.ext_dict(),
                                      snapshot=utils.ext_dict(),
                                      mysql=utils.ext_dict(),
                                      rabbit=utils.ext_dict(),
                                      storage=utils.ext_dict(),
                                      initial_check=utils.ext_dict())

        cloud_config['migrate'].update(config.migrate)
        cloud_config['cloud'].update(getattr(config, position))
        cloud_config['import_rules'].update(config.import_rules)
        cloud_config['mail'].update(config.mail)
        cloud_config['mysql'].update(getattr(config, position + '_mysql'))
        cloud_config['rabbit'].update(getattr(config, position + '_rabbit'))
        cloud_config['snapshot'].update(config.snapshot)
        cloud_config['storage'].update(getattr(config, position + '_storage'))
        cloud_config['initial_check'].update(config.initial_check)

        return cloud_config

    @staticmethod
    def make_resource_config(config, position, cloud_config, resource_name):
        resource_config = copy.deepcopy(cloud_config)
        resource_config[resource_name] = utils.ext_dict()
        for k, v in getattr(config,
                            '%s_%s' % (position, resource_name)).iteritems():
            resource_config[resource_name][k] = v

        return resource_config

    @staticmethod
    def get_db_method_create_connection(resource, config):
        def get_db_connection(db_name):
            conf_res = getattr(config, resource)
            conf = {
                k: getattr(conf_res, k, None) if getattr(conf_res, k, None)
                else config.mysql[k]
                for k in config.mysql.keys()}
            db_name_use = getattr(conf_res, 'db_name')\
                if getattr(conf_res, 'db_name', None) else db_name
            return mysql_connector.MysqlConnector(conf, db_name_use)
        return get_db_connection

    def init_resources(self, cloud_config):
        resources = self.resources
        self.resources = dict()
        self.rbd_util = rbd_util.RbdUtil(getattr(self.config,
                                                 "%s" % self.position),
                                         self.config.migrate)
        self.qemu_img = qemu_img.QemuImg(getattr(self.config,
                                                 "%s" % self.position),
                                         self.config.migrate)
        self.ssh_util = ssh_util.SshUtil(getattr(self.config,
                                                 "%s" % self.position),
                                         self.config.migrate)

        ident_conf = self.make_resource_config(self.config,
                                               self.position,
                                               cloud_config,
                                               'identity')
        self.mysql_connector = self.get_db_method_create_connection('identity',
                                                                    ident_conf)
        identity = resources['identity'](
            ident_conf,
            self)
        self.resources['identity'] = identity

        skip_initialization = ['identity']
        if not self.config.src_objstorage.service:
            skip_initialization.append('objstorage')
        for resource in resources:
            if resource not in skip_initialization:
                resource_config = self.make_resource_config(self.config,
                                                            self.position,
                                                            cloud_config,
                                                            resource)
                self.mysql_connector = \
                    self.get_db_method_create_connection(resource,
                                                         resource_config)
                self.resources[resource] = resources[resource](
                    resource_config, self)
