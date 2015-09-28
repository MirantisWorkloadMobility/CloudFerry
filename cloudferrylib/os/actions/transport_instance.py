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

from cloudferrylib.base.action import action
from cloudferrylib.os.identity import keystone
from cloudferrylib.utils import utils as utl


CLOUD = 'cloud'
BACKEND = 'backend'
CEPH = 'ceph'
ISCSI = 'iscsi'
COMPUTE = 'compute'
INSTANCES = 'instances'
INSTANCE_BODY = 'instance'
INSTANCE = 'instance'
DIFF = 'diff'
EPHEMERAL = 'ephemeral'
DIFF_OLD = 'diff_old'
EPHEMERAL_OLD = 'ephemeral_old'

PATH_DST = 'path_dst'
HOST_DST = 'host_dst'
PATH_SRC = 'path_src'
HOST_SRC = 'host_src'

TEMP = 'temp'
FLAVORS = 'flavors'


TRANSPORTER_MAP = {CEPH: {CEPH: 'ssh_ceph_to_ceph',
                          ISCSI: 'ssh_ceph_to_file'},
                   ISCSI: {CEPH: 'ssh_file_to_ceph',
                           ISCSI: 'ssh_file_to_file'}}


class TransportInstance(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        new_info = {
            utl.INSTANCES_TYPE: {
            }
        }

        # Get next one instance
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            instance = self._replace_user_ids(instance)

            one_instance = {
                utl.INSTANCES_TYPE: {
                    instance_id: instance
                }
            }
            one_instance = self.deploy_instance(self.dst_cloud, one_instance)

            new_info[utl.INSTANCES_TYPE].update(
                one_instance[utl.INSTANCES_TYPE])

        return {
            'info': new_info
        }

    def deploy_instance(self, dst_cloud, info):
        info = copy.deepcopy(info)
        dst_compute = dst_cloud.resources[COMPUTE]

        new_ids = dst_compute.deploy(info)
        new_info = dst_compute.read_info(search_opts={'id': new_ids.keys()})
        for i in new_ids.iterkeys():
            dst_compute.change_status('shutoff', instance_id=i)
        for new_id, old_id in new_ids.iteritems():
            new_instance = new_info['instances'][new_id]
            old_instance = info['instances'][old_id]

            new_instance['old_id'] = old_id
            new_instance['meta'] = old_instance['meta']
            new_instance['meta']['source_status'] = \
                old_instance['instance']['status']
            new_instance[utl.INSTANCE_BODY]['key_name'] = \
                old_instance[utl.INSTANCE_BODY]['key_name']
        info = self.prepare_ephemeral_drv(info, new_info, new_ids)
        return info

    def prepare_ephemeral_drv(self, info, new_info, map_new_to_old_ids):
        info = copy.deepcopy(info)
        new_info = copy.deepcopy(new_info)
        for new_id, old_id in map_new_to_old_ids.iteritems():
            instance_old = info[INSTANCES][old_id]
            instance_new = new_info[INSTANCES][new_id]

            ephemeral_path_dst = instance_new[EPHEMERAL][PATH_SRC]
            instance_new[EPHEMERAL][PATH_DST] = ephemeral_path_dst
            ephemeral_host_dst = instance_new[EPHEMERAL][HOST_SRC]
            instance_new[EPHEMERAL][HOST_DST] = ephemeral_host_dst

            diff_path_dst = instance_new[DIFF][PATH_SRC]
            instance_new[DIFF][PATH_DST] = diff_path_dst
            diff_host_dst = instance_new[DIFF][HOST_SRC]
            instance_new[DIFF][HOST_DST] = diff_host_dst

            ephemeral_path_src = instance_old[EPHEMERAL][PATH_SRC]
            instance_new[EPHEMERAL][PATH_SRC] = ephemeral_path_src
            ephemeral_host_src = instance_old[EPHEMERAL][HOST_SRC]
            instance_new[EPHEMERAL][HOST_SRC] = ephemeral_host_src

            diff_path_src = instance_old[DIFF][PATH_SRC]
            instance_new[DIFF][PATH_SRC] = diff_path_src
            diff_host_src = instance_old[DIFF][HOST_SRC]
            instance_new[DIFF][HOST_SRC] = diff_host_src

        return new_info

    def _replace_user_ids(self, instance):
        """User IDs for VMs on DST by default is set to admin's ID. This
        replaces admin user IDs with correct user IDs"""

        src_user_id = instance['instance']['user_id']
        dst_user = keystone.get_dst_user_from_src_user_id(
            self.src_cloud.resources[utl.IDENTITY_RESOURCE],
            self.dst_cloud.resources[utl.IDENTITY_RESOURCE],
            src_user_id
        )
        instance['instance']['user_id'] = dst_user.id
        return instance
