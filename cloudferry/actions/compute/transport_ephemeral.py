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
import hashlib
import logging
import os

from oslo_config import cfg

from cloudferry.actions.helper import task_transfer
from cloudferry.lib.base.action import action
from cloudferry.lib.copy_engines import base
from cloudferry.lib.migration import notifiers
from cloudferry.lib.migration import objects
from cloudferry.lib.utils import qemu_img as qemu_img_util
from cloudferry.lib.utils import utils

CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class TransportEphemeral(action.Action):
    def __init__(self, init, cloud=None):
        super(TransportEphemeral, self).__init__(init, cloud)
        self.migration_status = notifiers.MigrationStateNotifier()

        for observer in self.init['migration_observers']:
            self.migration_status.add_observer(observer)

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        new_info = {
            utils.INSTANCES_TYPE: {
            }
        }

        for instance_id, instance in info[utils.INSTANCES_TYPE].items():
            is_ephemeral = instance[utils.INSTANCE_BODY]['is_ephemeral']
            one_instance = {
                utils.INSTANCES_TYPE: {
                    instance_id: instance
                }
            }
            if is_ephemeral:
                try:
                    self.copy_ephemeral(self.dst_cloud, one_instance)
                except (base.NotEnoughSpace, base.FileCopyError) as e:
                    msg = ("Failed to copy ephemeral of VM '%s', error: "
                           "%s" % (instance_id, e))
                    LOG.warning(msg)
                    self.migration_status.fail(
                        objects.MigrationObjectType.VM,
                        instance[utils.INSTANCE_BODY],
                        message=msg)

            new_info[utils.INSTANCES_TYPE].update(
                one_instance[utils.INSTANCES_TYPE])

        return {
            'info': new_info
        }

    def copy_data_via_ssh(self, info, body, types):
        transporter = task_transfer.TaskTransfer(
            self.init,
            CONF.migrate.copy_backend,
            resource_name=types,
            resource_root_name=body)
        transporter.run(info=info)

    def copy_ephemeral(self, dst_cloud, info):
        self.copy_data_via_ssh(info,
                               utils.EPHEMERAL_BODY,
                               utils.INSTANCES_TYPE)
        self.rebase_diff(dst_cloud, info)

    @staticmethod
    def rebase_diff(dst_cloud, info):
        for obj in info[utils.INSTANCES_TYPE].values():
            image_id = obj['instance']['image_id']
            new_backing_file = hashlib.sha1(image_id).hexdigest()
            diff = obj['diff']
            host = diff['host_dst']
            qemu_img = qemu_img_util.QemuImg(dst_cloud.config.dst,
                                             dst_cloud.config.migrate,
                                             host)
            diff_path = diff['path_dst']
            backing_path = qemu_img.detect_backing_file(diff_path, None)

            if backing_path is None:
                # Ignore missing ephemeral backing file
                continue

            LOG.debug('Transport Ephemeral rebase diff: diff_path=%s, '
                      'backing_path=%s', diff_path, backing_path)
            backing_dir = os.path.dirname(backing_path)
            new_backing_path = os.path.join(backing_dir, new_backing_file)
            qemu_img.diff_rebase(new_backing_path, diff_path)
