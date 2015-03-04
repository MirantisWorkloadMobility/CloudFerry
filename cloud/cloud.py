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
from cloudferrylib.utils import utils
from cloudferrylib.utils import mysql_connector
from cloudferrylib.utils import rbd_util
from cloudferrylib.utils import qemu_img
from cloudferrylib.utils import ssh_util

SRC = "src"
DST = "dst"


class Cloud(object):
    def __init__(self, resources, position, config):
        self.resources = resources
        self.position = position
        self.config = config

        self.cloud_config = self.make_cloud_config(self.config, self.position)
        self.init_resources(self.cloud_config)

    def getIpSsh(self):
        return self.cloud_config.cloud.ssh_host \
            if self.cloud_config.cloud.ssh_host else self.cloud_config.cloud.host

    @staticmethod
    def make_cloud_config(config, position):
        cloud_config = utils.ext_dict(migrate=utils.ext_dict(),
                                      cloud=utils.ext_dict(),
                                      import_rules=utils.ext_dict(),
                                      mail=utils.ext_dict(),
                                      snapshot=utils.ext_dict(),
                                      mysql=utils.ext_dict())
        for k, v in config.migrate.iteritems():
            cloud_config['migrate'][k] = v

        for k, v in getattr(config, position).iteritems():
            cloud_config['cloud'][k] = v

        for k, v in config.import_rules.iteritems():
            cloud_config['import_rules'][k] = v

        for k, v in config.mail.iteritems():
            cloud_config['mail'][k] = v

        for k, v in getattr(config, position + '_mysql').iteritems():
            cloud_config['mysql'][k] = v

        cloud_config['snapshot'].update(config.snapshot)

        return cloud_config

    @staticmethod
    def make_resource_config(config, position, cloud_config, resource_name):
        resource_config = copy.deepcopy(cloud_config)
        resource_config[resource_name] = utils.ext_dict()
        for k, v in getattr(config,
                            '%s_%s' % (position, resource_name)).iteritems():
            resource_config[resource_name][k] = v

        return resource_config

    def init_resources(self, cloud_config):
        resources = self.resources
        self.resources = dict()
        self.mysql_connector = mysql_connector.MysqlConnector(getattr(self.config, "%s_mysql" % self.position), 'cinder')
        self.rbd_util = rbd_util.RbdUtil(getattr(self.config, "%s" % self.position), self.config.migrate)
        self.qemu_img = qemu_img.QemuImg(getattr(self.config, "%s" % self.position), self.config.migrate)
        self.ssh_util = ssh_util.SshUtil(getattr(self.config, "%s" % self.position), self.config.migrate)

        identity_conf = self.make_resource_config(self.config, self.position,
                                                  cloud_config, 'identity')
        identity = resources['identity'](
            identity_conf,
            self)
        self.resources['identity'] = identity

        for resource in resources:
            if resource != 'identity':
                resource_config = self.make_resource_config(self.config,
                                                            self.position,
                                                            cloud_config,
                                                            resource)
                self.resources[resource] = resources[resource](
                    resource_config, self)
