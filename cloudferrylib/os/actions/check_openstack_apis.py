# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cloudferrylib.base.action import action
from cloudferrylib.base import exception
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl
from neutronclient.common import exceptions as neutron_exc
from glanceclient import exc as glance_exc
from keystoneclient.openstack.common.apiclient import exceptions as ks_exc
from cinderclient import exceptions as cinder_exc
from novaclient import exceptions as nova_exc

LOG = log.getLogger(__name__)


def check(os_api_call,
          os_api_type,
          position,
          *os_api_call_args,
          **os_api_call_kwargs):
    try:
        LOG.info("Checking %s APIs availability on %s.",
                 os_api_type, position.upper())
        os_api_call(*os_api_call_args, **os_api_call_kwargs)
    except (neutron_exc.NeutronException,
            glance_exc.BaseException,
            glance_exc.ClientException,
            ks_exc.ClientException,
            cinder_exc.ClientException,
            nova_exc.ClientException) as e:
        message = ('{os_api_type} APIs on {position} check failed with: '
                   '"{msg}". Check your configuration.').format(
            os_api_type=os_api_type, msg=e.message, position=position.upper())
        LOG.error(message)
        raise exception.AbortMigrationError(message)


class CheckIdentBackend(action.Action):
    def run(self, **kwargs):
        """Check identity backend by getting list of tenants."""
        ident_resource = self.cloud.resources[utl.IDENTITY_RESOURCE]
        check(ident_resource.keystone_client.tenants.list, 'Keystone tenants',
              self.cloud.position)


class CheckImageBackend(action.Action):
    def run(self, **kwargs):
        """Check image backend by getting list of images."""
        image_resource = self.cloud.resources[utl.IMAGE_RESOURCE]
        check(image_resource.glance_client.images.list, 'Glance images',
              self.cloud.position)


class CheckComputeBackend(action.Action):
    def run(self, **kwargs):
        """Check compute backend by getting instances/flavors/quotas lists."""
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        check(compute_resource.nova_client.servers.list, 'Nova instances',
              self.cloud.position)
        check(compute_resource.nova_client.flavors.list, 'Nova flavors',
              self.cloud.position)
        check(compute_resource.nova_client.quotas.get, 'Nova quotas',
              self.cloud.position, self.cloud.cloud_config.cloud.tenant)


class CheckStorageBackend(action.Action):
    def run(self, **kwargs):
        """Check storage backend by getting volumes/snapshots lists."""
        storage_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        check(storage_resource.cinder_client.volumes.list, 'Cinder volumes',
              self.cloud.position)
        check(storage_resource.cinder_client.volume_snapshots.list,
              'Cinder snapshots',
              self.cloud.position)


class CheckNetworkingAPIs(action.Action):
    def run(self, **kwargs):
        """Check networking backend
         by getting network/subnets/routers lists."""
        neutron = self.cloud.resources[utl.NETWORK_RESOURCE]
        check(neutron.neutron_client.list_networks, 'Neutron networks',
              self.cloud.position)
        check(neutron.neutron_client.list_subnets, 'Neutron subnets',
              self.cloud.position)
        check(neutron.neutron_client.list_routers, 'Neutron routers',
              self.cloud.position)
