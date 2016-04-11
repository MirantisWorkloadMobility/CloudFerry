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

import logging
import copy
import random

from cloudferry.lib.base.action import action
from cloudferry.lib.base import exception
from cloudferry.lib.os.identity import keystone
from cloudferry.lib.os.network import network_utils
from cloudferry.lib.utils import utils


LOG = logging.getLogger(__name__)


CLOUD = 'cloud'
BACKEND = 'backend'
CEPH = 'ceph'
ISCSI = 'iscsi'
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


class DestinationCloudNotOperational(RuntimeError):
    pass


class TransportInstance(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        new_info = {
            utils.INSTANCES_TYPE: {
            }
        }

        # Get next one instance
        for instance_id, instance in info[utils.INSTANCES_TYPE].iteritems():
            instance = self._replace_user_ids(instance)
            src_instance = instance['instance']
            src_image_id = src_instance['image_id']
            dst_image = self.get_dst_image(src_image_id)

            if dst_image is None:
                LOG.warning("Image '%s' is not present in destination, "
                            "skipping migration of VM '%s' (%s).",
                            src_image_id, src_instance['name'],
                            src_instance['id'])
                continue

            if dst_image.id != src_image_id:
                LOG.info("Using image ID '%s' to boot VM '%s (%s)'",
                         dst_image.id, src_instance['name'],
                         src_instance['id'])
                src_instance['image_id'] = dst_image.id

            one_instance = {
                utils.INSTANCES_TYPE: {
                    instance_id: instance
                }
            }

            one_instance = self.deploy_instance(one_instance)

            new_info[utils.INSTANCES_TYPE].update(
                one_instance[utils.INSTANCES_TYPE])

        return {
            'info': new_info
        }

    def get_dst_image(self, src_image_id):
        """Returns active image for VM. If not found, tries to match image
        based on image name, tenant, checksum and size"""
        dst_glance = self.dst_cloud.resources[utils.IMAGE_RESOURCE]
        image = dst_glance.get_active_image_by_id(src_image_id)

        if image is None:
            src_glance = self.src_cloud.resources[utils.IMAGE_RESOURCE]
            src_image = src_glance.get_image_by_id(src_image_id)

            if src_image is None:
                # image does not exist in source cloud, will be recreated
                # from ephemeral
                return

            dst_tenant = keystone.get_dst_tenant_from_src_tenant_id(
                self.src_cloud.resources[utils.IDENTITY_RESOURCE],
                self.dst_cloud.resources[utils.IDENTITY_RESOURCE],
                src_image.owner)

            LOG.info("Image with ID '%s' was not found in destination cloud, "
                     "looking for images in tenant '%s' with checksum '%s', "
                     "name '%s' and size '%s'", src_image_id, dst_tenant.name,
                     src_image.checksum, src_image.name, src_image.size)
            image = dst_glance.get_active_image_with(
                dst_tenant.id,
                src_image.checksum,
                src_image.name,
                src_image.size)

        return image

    def deploy_instance(self, one_instance):
        one_instance = copy.deepcopy(one_instance)
        dst_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]

        _instance = one_instance[utils.INSTANCES_TYPE].values()[0]
        instance = _instance[utils.INSTANCE_BODY]
        new_ids = {}
        instance_az = dst_compute.get_instance_availability_zone(instance)
        try:
            new_id = dst_compute.deploy(
                instance, availability_zone=instance_az)
        except exception.TimeoutException:
            one_instance, new_id = self._deploy_instance_on_random_host(
                one_instance, instance_az)

        new_ids[new_id] = instance['id']

        new_info = dst_compute.read_info(search_opts={'id': new_ids.keys()})
        for i in new_ids.iterkeys():
            dst_compute.change_status('shutoff', instance_id=i)
        for new_id, old_id in new_ids.iteritems():
            new_instance = new_info['instances'][new_id]
            old_instance = one_instance['instances'][old_id]

            new_instance['old_id'] = old_id
            new_instance['meta'] = old_instance['meta']
            new_instance['meta']['source_status'] = \
                old_instance['instance']['status']
            new_instance[utils.INSTANCE_BODY]['key_name'] = \
                old_instance[utils.INSTANCE_BODY]['key_name']
        one_instance = self.prepare_ephemeral_drv(
            one_instance,
            new_info,
            new_ids
        )
        return one_instance

    def _deploy_instance_on_random_host(self, one_instance, availability_zone):
        one_instance = copy.deepcopy(one_instance)
        dst_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]

        _instance = one_instance[utils.INSTANCES_TYPE].values()[0]
        instance_body = _instance[utils.INSTANCE_BODY]
        hosts = dst_compute.get_compute_hosts(availability_zone)
        if not hosts:
            message = ("No hosts in availability zone '{az}' "
                       "found on destination.").format(az=availability_zone)
            raise DestinationCloudNotOperational(message)

        random.shuffle(hosts)

        while hosts:
            # Recreate ports and check floating ips
            one_instance = network_utils.prepare_networks(
                one_instance,
                self.cfg.migrate.keep_ip,
                self.dst_cloud.resources[utils.NETWORK_RESOURCE],
                self.dst_cloud.resources[utils.IDENTITY_RESOURCE]
            )

            # Associate floating ips with ports again
            if self.cfg.migrate.keep_floatingip:
                network_utils.associate_floatingip(
                    one_instance,
                    self.dst_cloud.resources[utils.NETWORK_RESOURCE]
                )

            next_host = hosts.pop()
            host_az = ':'.join([availability_zone, next_host])
            _updated_instance = one_instance[utils.INSTANCES_TYPE].values()[0]
            updated_instance_body = _updated_instance[utils.INSTANCE_BODY]

            try:
                new_id = dst_compute.deploy(
                    updated_instance_body, availability_zone=host_az)
                return one_instance, new_id
            except exception.TimeoutException:
                pass

        message = ("Unable to schedule VM '{vm}' on any of available compute "
                   "nodes.").format(vm=instance_body['name'])
        LOG.error(message)
        raise DestinationCloudNotOperational(message)

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
            self.src_cloud.resources[utils.IDENTITY_RESOURCE],
            self.dst_cloud.resources[utils.IDENTITY_RESOURCE],
            src_user_id
        )
        instance['instance']['user_id'] = dst_user.id
        return instance
