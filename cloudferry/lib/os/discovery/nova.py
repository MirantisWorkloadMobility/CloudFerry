# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from novaclient import exceptions

from cloudferry import discover
from cloudferry import model
from cloudferry.model import compute
from cloudferry.model import identity
from cloudferry.model import image
from cloudferry.model import storage
from cloudferry.lib.utils import qemu_img
from cloudferry.lib.utils import remote
from cloudferry.lib.os import clients

EXT_ATTR_INSTANCE_NAME = 'OS-EXT-SRV-ATTR:instance_name'
EXT_ATTR_HYPER_HOST = 'OS-EXT-SRV-ATTR:hypervisor_hostname'
EXT_ATTR_AZ = 'OS-EXT-AZ:availability_zone'
EXT_ATTR_HOST = 'OS-EXT-SRV-ATTR:host'
EXT_ATTR_VOL_ATTACHMENTS = 'os-extended-volumes:volumes_attached'

LOG = logging.getLogger(__name__)


class FlavorDiscoverer(discover.Discoverer):
    discovered_class = compute.Flavor

    def discover_all(self):
        # TODO: implement
        return

    def discover_one(self, uuid):
        compute_client = clients.compute_client(self.cloud)
        raw_flavor = compute_client.flavors.get(uuid)
        # TODO: implement
        return compute.Flavor.load({
            'object_id': self.make_id(raw_flavor.id),
        })

    def load_from_cloud(self, data):
        return compute.Flavor.load(data)


class ServerDiscoverer(discover.Discoverer):
    discovered_class = compute.Server

    def discover_all(self):
        compute_client = clients.compute_client(self.cloud)
        avail_hosts = _list_available_compute_hosts(compute_client)
        servers = {}

        # Go through each tenant since nova don't return more items than
        # specified in osapi_max_limit configuration option (1000 by default)
        # in single API call
        for tenant in self._get_tenants():
            LOG.debug('Discovering servers from cloud "%s" tenant "%s"',
                      self.cloud.name, tenant.name)
            tenant_id = tenant.id
            raw_server_list = compute_client.servers.list(
                search_opts={
                    'all_tenants': True,
                    'tenant_id': tenant_id,
                })
            for raw_server in raw_server_list:
                host = getattr(raw_server, EXT_ATTR_HOST)
                if host not in avail_hosts:
                    LOG.warning('Skipping server %s in tenant %s, host not '
                                'available.', host, tenant.name)
                    continue
                # Convert server data to model conforming format
                server = self.load_from_cloud(raw_server)
                hyper_host = getattr(raw_server, EXT_ATTR_HYPER_HOST)
                servers.setdefault(hyper_host, []).append(server)

        # Collect information about ephemeral disks
        # TODO: work with different servers in parallel
        for host, host_servers in servers.items():
            LOG.debug('Getting ephemeral disks information from cloud %s '
                      'host %s', self.cloud.name, host)
            with remote.RemoteExecutor(self.cloud, host) as remote_executor:
                for server in host_servers:
                    _populate_ephemeral_disks(remote_executor, server)

        # Store data to local database
        with model.Session() as session:
            for host_servers in servers.values():
                for server in host_servers:
                    session.store(server)
                    if _need_image_membership(server):
                        image_member_uuid = image.ImageMember.make_uuid(
                            server.image, server.tenant)
                        server.image_membership = self.find_obj(
                            image.ImageMember, image_member_uuid)

    def discover_one(self, uuid):
        compute_client = clients.compute_client(self.cloud)
        try:
            raw_server = compute_client.servers.get(uuid)
        except exceptions.NotFound:
            raise discover.NotFound()

        # Check if server host is available
        avail_hosts = _list_available_compute_hosts(compute_client)
        host = getattr(raw_server, EXT_ATTR_HOST)
        if host not in avail_hosts:
            LOG.warning('Skipping server %s, host not available.',
                        host)
            return None

        # Convert server data to model conforming format
        server = self.load_from_cloud(raw_server)
        with remote.RemoteExecutor(
                self.cloud, server.hypervisor_host) as remote_executor:
            _populate_ephemeral_disks(remote_executor, server)

        # Store server
        with model.Session() as session:
            session.store(server)
            if _need_image_membership(server):
                image_member_uuid = image.ImageMember.make_uuid(
                    server.image, server.tenant)
                server.image_membership = self.find_obj(
                    image.ImageMember, image_member_uuid)
        return server

    def load_from_cloud(self, data):
        compute_client = clients.compute_client(self.cloud)
        # Workaround for grizzly lacking EXT_ATTR_VOL_ATTACHMENTS
        if hasattr(data, EXT_ATTR_VOL_ATTACHMENTS):
            raw_attachments = [
                '{0}:{1}'.format(data.id, attachment['id'])
                for attachment in
                getattr(data, EXT_ATTR_VOL_ATTACHMENTS)]
        else:
            raw_attachments = [
                '{0}:{1}'.format(attachment.serverId, attachment.volumeId)
                for attachment in
                compute_client.volumes.get_server_volumes(data.id)]
        server_image = None
        if data.image:
            server_image = data.image['id']
        server_dict = {
            'object_id': self.make_id(data.id),
            'security_groups': [],  # TODO: implement security groups
            'tenant': self.find_ref(identity.Tenant, data.tenant_id),
            'image': self.find_ref(image.Image, server_image),
            'image_membership': None,
            'flavor': self.find_ref(compute.Flavor, data.flavor['id']),
            'availability_zone': getattr(data, EXT_ATTR_AZ),
            'host': getattr(data, EXT_ATTR_HOST),
            'hypervisor_hostname': getattr(data, EXT_ATTR_HYPER_HOST),
            'instance_name': getattr(data, EXT_ATTR_INSTANCE_NAME),
            'attached_volumes': [self.find_ref(storage.Attachment, attachment)
                                 for attachment in raw_attachments],
            'ephemeral_disks': [],  # Ephemeral disks will be filled later
        }
        for attr_name in ('name', 'status', 'user_id', 'key_name',
                          'config_drive', 'metadata'):
            if hasattr(data, attr_name):
                server_dict[attr_name] = getattr(data, attr_name)
        return compute.Server.load(server_dict)

    def _get_tenants(self):
        identity_client = clients.identity_client(self.cloud)
        return identity_client.tenants.list()


def _populate_ephemeral_disks(rmt_exec, server):
    try:
        output = rmt_exec.sudo('virsh domblklist {instance}',
                               instance=server.instance_name)
    except remote.RemoteFailure:
        LOG.error('Unable to get ephemeral disks for server %s, skipping.',
                  server, exc_info=True)
        return

    volume_targets = set()
    for attachment in server.attached_volumes:
        volume_targets.add(attachment.device.replace('/dev/', ''))

    for line in output.splitlines():
        split = line.split(None, 1)
        if len(split) != 2:
            continue
        target, path = split
        if target in volume_targets or not path.startswith('/'):
            continue

        size, base_path, format = _get_disk_info(rmt_exec, path)
        if base_path is not None:
            base_size, _, base_format = _get_disk_info(rmt_exec, base_path)
        else:
            base_size = base_format = None
        if size is not None:
            eph_disk = compute.EphemeralDisk.load({
                'path': path,
                'size': size,
                'format': format,
                'base_path': base_path,
                'base_size': base_size,
                'base_format': base_format,
            })
            server.ephemeral_disks.append(eph_disk)


def _need_image_membership(srv):
    img = srv.image
    if img is None:
        return False
    if img.is_public:
        return False
    return img.tenant != srv.tenant


def _list_available_compute_hosts(compute_client):
    return set(c.host
               for c in compute_client.services.list(binary='nova-compute')
               if c.state == 'up' and c.status == 'enabled')


def _get_disk_info(remote_executor, path):
    try:
        size_str = remote_executor.sudo('stat -c %s {path}', path=path)
    except remote.RemoteFailure:
        LOG.error('Unable to get size of "%s", skipping disk.', path,
                  exc_info=True)
        return None, None, None
    disk_info = qemu_img.get_disk_info(remote_executor, path)
    return int(size_str.strip()), disk_info.backing_filename, disk_info.format
