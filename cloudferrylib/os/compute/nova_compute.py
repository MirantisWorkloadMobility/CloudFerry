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
import random
import pprint

from novaclient.v1_1 import client as nova_client
from novaclient import exceptions as nova_exc

from cloudferrylib.base import compute
from cloudferrylib.os.compute import instances
from cloudferrylib.os.compute import cold_evacuate
from cloudferrylib.os.compute import server_groups
from cloudferrylib.os.identity import keystone
from cloudferrylib.utils import mysql_connector
from cloudferrylib.utils import timeout_exception
from cloudferrylib.utils import utils as utl


LOG = utl.get_log(__name__)


DISK = "disk"
LOCAL = ".local"
LEN_UUID_INSTANCE = 36
INTERFACES = "interfaces"
DEFAULT_QUOTA_VALUE = -1

INSTANCE_HOST_ATTRIBUTE = 'OS-EXT-SRV-ATTR:host'
INSTANCE_LIBVIRT_NAME_ATTRIBUTE = 'OS-EXT-SRV-ATTR:instance_name'
INSTANCE_AZ_ATTRIBUTE = 'OS-EXT-AZ:availability_zone'

ACTIVE = 'ACTIVE'
STOPPED = 'STOPPED'
SHUTOFF = 'SHUTOFF'
VERIFY_RESIZE = 'VERIFY_RESIZE'
RESIZED = 'RESIZED'
SUSPENDED = 'SUSPENDED'
PAUSED = 'PAUSED'
SHELVED = 'SHELVED'
SHELVED_OFFLOADED = 'SHELVED_OFFLOADED'
ERROR = 'ERROR'

ALLOWED_VM_STATUSES = [ACTIVE, STOPPED, SHUTOFF, RESIZED, SUSPENDED,
                       PAUSED, SHELVED, SHELVED_OFFLOADED, VERIFY_RESIZE]

# Describe final VM status on destination based on source VM status
# dict( <source VM status> , <destination VM status> )
STATUSES_AFTER_MIGRATION = {ACTIVE: ACTIVE,
                            STOPPED: SHUTOFF,
                            SHUTOFF: SHUTOFF,
                            RESIZED: ACTIVE,
                            SUSPENDED: SHUTOFF,
                            PAUSED: SHUTOFF,
                            SHELVED: SHUTOFF,
                            SHELVED_OFFLOADED: SHUTOFF,
                            VERIFY_RESIZE: ACTIVE}

CORRECT_STATUSES_AFTER_MIGRATION = {STATUSES_AFTER_MIGRATION[status]
                                    for status in ALLOWED_VM_STATUSES}


class DestinationCloudNotOperational(RuntimeError):
    pass


class RandomSchedulerVmDeployer(object):
    """Creates VM on destination. Tries to create VM on random compute host if
    failed with the one picked by nova scheduler"""

    def __init__(self, nova_compute_obj):
        self.nc = nova_compute_obj

    def deploy(self, instance, create_params, client_conf):
        LOG.info("Deploying instance '%s'", instance['name'])

        try:
            return self.nc.deploy_instance(create_params, client_conf)
        except timeout_exception.TimeoutException:
            hosts = self.nc.get_compute_hosts()
            random.seed()
            random.shuffle(hosts)

            while hosts:
                create_params['availability_zone'] = ':'.join([
                    instance['availability_zone'], hosts.pop()])
                LOG.info("Trying to deploy instance '%s' in '%s'",
                         create_params['name'],
                         create_params.get('availability_zone', 'UNKNOWN'))
                try:
                    return self.nc.deploy_instance(create_params, client_conf)
                except timeout_exception.TimeoutException:
                    pass

        message = ("Unable to schedule VM '{vm}' on any of available compute "
                   "nodes.").format(vm=instance['name'])
        LOG.error(message)
        raise DestinationCloudNotOperational(message)


class NovaCompute(compute.Compute):
    """The main class for working with Openstack Nova Compute Service. """

    def __init__(self, config, cloud):
        super(NovaCompute, self).__init__()
        self.config = config
        self.cloud = cloud
        self.filter_tenant_id = None
        self.identity = cloud.resources['identity']
        self.mysql_connector = cloud.mysql_connector('nova')
        # List of instance IDs which failed to create
        self._failed_instances = []

    @property
    def nova_client(self):
        return self.proxy(self.get_client(), self.config)

    @property
    def failed_instances(self):
        return [vm_id for vm_id in self._failed_instances
                if self.instance_exists(vm_id) and
                self.get_status(vm_id) not in CORRECT_STATUSES_AFTER_MIGRATION]

    def get_client(self, params=None):
        """Getting nova client. """

        params = self.config if not params else params

        client_args = [params.cloud.user, params.cloud.password,
                       params.cloud.tenant, params.cloud.auth_url]

        client_kwargs = {"cacert": params.cloud.cacert,
                         "insecure": params.cloud.insecure}
        if params.cloud.region:
            client_kwargs["region_name"] = params.cloud.region

        client = nova_client.Client(*client_args, **client_kwargs)
        LOG.debug("Authenticating as '%s' in tenant '%s' for Nova client "
                  "authorization...",
                  params.cloud.user, params.cloud.tenant)
        client.authenticate()
        return client

    def get_db_connection(self):
        if not hasattr(self.cloud.config, self.cloud.position + '_compute'):
            LOG.debug('Running on default mysql settings')
            return mysql_connector.MysqlConnector(self.config.mysql, 'nova')
        else:
            LOG.debug('Running on custom mysql settings')
            my_settings = getattr(self.cloud.config,
                                  self.cloud.position + '_compute')
            return mysql_connector.MysqlConnector(my_settings,
                                                  my_settings.db_name)

    def _read_info_quotas(self):
        admin_tenant_id = self.identity.get_tenant_id_by_name(
            self.config.cloud.tenant)
        service_tenant_id = self.identity.get_tenant_id_by_name(
            self.config.cloud.service_tenant)
        if self.cloud.position == 'src' and self.filter_tenant_id:
            tmp_list = \
                [admin_tenant_id, service_tenant_id, self.filter_tenant_id]
            tenant_ids = \
                [tenant.id for tenant in self.identity.get_tenants_list()
                    if tenant.id in tmp_list]
        else:
            tenant_ids = \
                [tenant.id for tenant in self.identity.get_tenants_list()
                    if tenant.id != service_tenant_id]
        user_ids = [user.id for user in self.identity.get_users_list()]
        project_quotas = list()
        user_quotas = list()

        for tenant_id in tenant_ids:
            project_quota = self.get_quotas(tenant_id=tenant_id)
            project_quota_info = self.convert_resources(project_quota,
                                                        None)
            project_quota_info['tenant_id'] = tenant_id
            project_quotas.append(project_quota_info)
            if self.config.migrate.migrate_user_quotas:
                for user_id in user_ids:
                    if self.identity.roles_for_user(user_id, tenant_id):
                        user_quota = self.get_quotas(tenant_id=tenant_id,
                                                     user_id=user_id)
                        user_quota_info = self.convert_resources(
                            user_quota, None)
                        user_quota_info['tenant_id'] = tenant_id
                        user_quota_info['user_id'] = user_id
                        user_quotas.append(user_quota_info)

        return project_quotas, user_quotas

    def _read_info_resources(self):
        """
        Read info about compute resources except instances from the cloud.
        """

        info = {'flavors': {},
                'default_quotas': {},
                'user_quotas': [],
                'project_quotas': []}

        for flavor in self.get_flavor_list(is_public=None):
            try:
                internal_flavor = self.convert(flavor, cloud=self.cloud)
                if internal_flavor is None:
                    continue
                info['flavors'][flavor.id] = internal_flavor
                LOG.info("Got flavor '%s'", flavor.name)
                LOG.debug("%s", pprint.pformat(internal_flavor))
            except nova_exc.NotFound:
                # In case Nova failed with flavor-access-list obtaining
                # particular flavor it crashes with NotFound exception
                LOG.warning('Skipping invalid flavor %s', flavor.name)

        if self.config.migrate.migrate_quotas:
            info['default_quotas'] = self.get_default_quotas()
            info['project_quotas'], info['user_quotas'] = \
                self._read_info_quotas()

        return info

    def read_info(self, target='instances', **kwargs):
        """
        Read info from cloud.

        :param target: Target objects to get info about. Possible values:
                       "instances" or "resources",
        :param search_opts: Search options to filter out servers (optional).
        """

        if kwargs.get('tenant_id'):
            self.filter_tenant_id = kwargs['tenant_id'][0]

        if target == 'resources':
            return self._read_info_resources()

        if target != 'instances':
            raise ValueError('Only "resources" or "instances" values allowed')

        search_opts = kwargs.get('search_opts')

        search_opts = search_opts if search_opts else {}
        search_opts.update(all_tenants=True)

        info = {'instances': {}}

        for instance in self.get_instances_list(search_opts=search_opts):
            if instance.status in ALLOWED_VM_STATUSES:
                if (self.cloud.position == 'dst' or
                        (self.cloud.position == 'src' and
                            self.filter_tenant_id is not None and
                            self.filter_tenant_id == instance.tenant_id) or
                        (self.cloud.position == 'src' and
                            self.filter_tenant_id is None)):
                    converted = self.convert(instance, self.config, self.cloud)
                    if converted is None:
                        continue
                    info['instances'][instance.id] = converted

        return info

    @staticmethod
    def convert_instance(instance, cfg, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        compute_res = cloud.resources[utl.COMPUTE_RESOURCE]
        sg_res = server_groups.ServerGroupsHandler(cloud)

        instance_name = instance_libvirt_name(instance)
        instance_node = instance_host(instance)

        get_tenant_name = identity_res.get_tenants_func()

        security_groups = []
        for security_group in getattr(instance, 'security_groups', []):
            security_groups.append(security_group['name'])

        interfaces = compute_res.get_networks(instance)

        volumes = [{'id': v.id,
                    'num_device': i,
                    'device': v.device} for i, v in enumerate(
                        compute_res.nova_client.volumes.get_server_volumes(
                            instance.id))]

        is_ephemeral = compute_res.get_flavor_from_id(
            instance.flavor['id'], include_deleted=True).ephemeral > 0

        is_ceph = cfg.compute.backend.lower() == utl.CEPH
        direct_transfer = cfg.migrate.direct_compute_transfer

        ssh_user = cfg.cloud.ssh_user

        if direct_transfer:
            ext_cidr = cfg.cloud.ext_cidr
            host = utl.get_ext_ip(ext_cidr,
                                  cloud.getIpSsh(),
                                  instance_node,
                                  ssh_user)
        elif is_ceph:
            host = cfg.compute.host_eph_drv
        else:
            host = instance_node

        if not utl.libvirt_instance_exists(instance_name,
                                           cloud.getIpSsh(),
                                           instance_node,
                                           ssh_user,
                                           cfg.cloud.ssh_sudo_password):
            LOG.warning('Instance %s (%s) not found on %s, skipping migration',
                        instance_name, instance.id, instance_node)
            return None

        instance_block_info = utl.get_libvirt_block_info(
            instance_name,
            cloud.getIpSsh(),
            instance_node,
            ssh_user,
            cfg.cloud.ssh_sudo_password)

        ephemeral_path = {
            'path_src': None,
            'path_dst': None,
            'host_src': host,
            'host_dst': None
        }

        if is_ephemeral:
            ephemeral_path['path_src'] = utl.get_disk_path(
                instance,
                instance_block_info,
                is_ceph_ephemeral=is_ceph,
                disk=DISK + LOCAL)

        diff = {
            'path_src': None,
            'path_dst': None,
            'host_src': host,
            'host_dst': None
        }

        if instance.image:
            diff['path_src'] = utl.get_disk_path(
                instance,
                instance_block_info,
                is_ceph_ephemeral=is_ceph)
        flav_details = instances.get_flav_details(compute_res.mysql_connector,
                                                  instance.id)
        flav_name = compute_res.get_flavor_from_id(instance.flavor['id'],
                                                   include_deleted=True).name
        flav_details.update({'name': flav_name})

        tenant_name = get_tenant_name(instance.tenant_id)

        if cfg.migrate.keep_affinity_settings:
            server_group = sg_res.get_server_group_id_by_vm(instance.id,
                                                            tenant_name)
        else:
            server_group = None

        inst = {'instance': {'name': instance.name,
                             'instance_name': instance_name,
                             'id': instance.id,
                             'tenant_id': instance.tenant_id,
                             'tenant_name': tenant_name,
                             'status': instance.status,
                             'flavor_id': instance.flavor['id'],
                             'flav_details': flav_details,
                             'image_id': instance.image[
                                 'id'] if instance.image else None,
                             'boot_mode': (utl.BOOT_FROM_IMAGE
                                           if instance.image
                                           else utl.BOOT_FROM_VOLUME),
                             'key_name': instance.key_name,
                             'availability_zone': getattr(
                                 instance,
                                 'OS-EXT-AZ:availability_zone'),
                             'security_groups': security_groups,
                             'boot_volume': copy.deepcopy(
                                 volumes[0]) if volumes else None,
                             'interfaces': interfaces,
                             'host': instance_node,
                             'is_ephemeral': is_ephemeral,
                             'volumes': volumes,
                             'user_id': instance.user_id,
                             'server_group': server_group
                             },
                'ephemeral': ephemeral_path,
                'diff': diff,
                'meta': {'old_id': instance.id},
                }

        return inst

    @staticmethod
    def convert_resources(compute_obj, cloud):

        if isinstance(compute_obj, nova_client.flavors.Flavor):

            compute_res = cloud.resources[utl.COMPUTE_RESOURCE]
            tenants = []

            if not compute_obj.is_public:
                flavor_access_list = compute_res.get_flavor_access_list(
                    compute_obj.id)
                tenants = [flv_acc.tenant_id for flv_acc in flavor_access_list]

                filter_enabled = compute_res.filter_tenant_id is not None
                if (filter_enabled and
                        compute_res.filter_tenant_id not in tenants):
                    return None

            return {'flavor': {'name': compute_obj.name,
                               'ram': compute_obj.ram,
                               'vcpus': compute_obj.vcpus,
                               'disk': compute_obj.disk,
                               'ephemeral': compute_obj.ephemeral,
                               'swap': compute_obj.swap,
                               'rxtx_factor': compute_obj.rxtx_factor,
                               'is_public': compute_obj.is_public,
                               'tenants': tenants},
                    'meta': {}}

        elif isinstance(compute_obj,
                        (nova_client.quotas.QuotaSet,
                         nova_client.quota_classes.QuotaClassSet)):
            return {'quota': {'cores': compute_obj.cores,
                              'fixed_ips': compute_obj.fixed_ips,
                              'floating_ips': compute_obj.floating_ips,
                              'instances': compute_obj.instances,
                              'key_pairs': compute_obj.key_pairs,
                              'ram': compute_obj.ram,
                              'security_group_rules':
                                  compute_obj.security_group_rules,
                              'security_groups': compute_obj.security_groups,
                              'injected_file_content_bytes':
                                  compute_obj.injected_file_content_bytes,
                              'injected_file_path_bytes':
                                  compute_obj.injected_file_path_bytes,
                              'injected_files': compute_obj.injected_files,
                              'metadata_items': compute_obj.metadata_items},
                    'meta': {}}

    @staticmethod
    def convert(obj, cfg=None, cloud=None):
        if isinstance(obj, nova_client.servers.Server):
            return NovaCompute.convert_instance(obj, cfg, cloud)
        elif isinstance(obj, nova_client.flavors.Flavor):
            return NovaCompute.convert_resources(obj, cloud)

        LOG.error('NovaCompute converter has received incorrect value. Please '
                  'pass to it only instance or flavor objects.')
        return None

    def _deploy_resources(self, info, **kwargs):
        """
        Deploy compute resources except instances to the cloud.

        :param info: Info about compute resources to deploy,
        :param identity_info: Identity info.
        """

        identity_info = kwargs.get('identity_info')

        tenant_map = {tenant['tenant']['id']: tenant['meta']['new_id'] for
                      tenant in identity_info['tenants']}
        user_map = {user['user']['id']: user['meta']['new_id'] for user in
                    identity_info['users']}

        self._deploy_flavors(info['flavors'], tenant_map)
        if self.config['migrate']['migrate_quotas']:
            self.update_default_quotas(info['default_quotas'])
            self._deploy_quotas(info['project_quotas'], tenant_map)
            self._deploy_quotas(info['user_quotas'], tenant_map, user_map)

        new_info = self.read_info(target='resources')

        return new_info

    def deploy(self, info, target='instances', **kwargs):
        """
        Deploy compute resources to the cloud.

        :param target: Target objects to deploy. Possible values:
                       "instances" or "resources",
        :param identity_info: Identity info.
        """

        info = copy.deepcopy(info)

        if target == 'resources':
            info = self._deploy_resources(info, **kwargs)
        elif target == 'instances':
            info = self._deploy_instances(info)
        else:
            raise ValueError('Only "resources" or "instances" values allowed')

        return info

    def _add_flavor_access_for_tenants(self, flavor_id, tenant_ids):
        for t in tenant_ids:
            LOG.debug("Adding access for tenant '%s' to flavor '%s'", t,
                      flavor_id)
            try:
                self.add_flavor_access(flavor_id, t)
            except nova_exc.Conflict:
                LOG.debug("Tenant '%s' already has access to flavor '%s'", t,
                          flavor_id)

    def _create_flavor_if_not_exists(self, flavor, flavor_id):
        """If flavor exists on destination:
              1. If it's the same as on source - do nothing;
              2. If it's different - delete flavor from destination, and create
                 new.
        """
        dest_flavor = None
        try:
            dest_flavor = self.get_flavor_from_id(flavor_id)
        except nova_exc.NotFound:
            LOG.info("Flavor %s does not exist", flavor['name'])
        if dest_flavor is not None:
            identical = (flavor_id == dest_flavor.id and
                         flavor['name'].lower() == dest_flavor.name.lower() and
                         flavor['vcpus'] == dest_flavor.vcpus and
                         flavor['ram'] == dest_flavor.ram and
                         flavor['disk'] == dest_flavor.disk and
                         flavor['ephemeral'] == dest_flavor.ephemeral and
                         flavor['is_public'] == dest_flavor.is_public and
                         flavor['rxtx_factor'] == dest_flavor.rxtx_factor and
                         flavor['swap'] == dest_flavor.swap)
            if identical:
                LOG.debug("Identical flavor '%s' already exists, skipping.",
                          flavor['name'])
                return dest_flavor
            else:
                LOG.info("Flavor with the same ID exists ('%s'), but it "
                         "differs from source. Deleting flavor '%s' from "
                         "destination.", flavor_id, flavor_id)
                self.delete_flavor(flavor_id)
        else:
            dest_flavor_list = self.get_flavor_list()
            for flv in dest_flavor_list:
                if flavor['name'].lower() == flv.name.lower():
                    LOG.info("Flavor with the same name exists ('%s'). "
                             "Deleting it from destination.", flavor['name'])
                    self.delete_flavor(flv.id)

        LOG.info("Creating flavor '%s'", flavor['name'])
        return self.create_flavor(
            name=flavor['name'],
            flavorid=flavor_id,
            ram=flavor['ram'],
            vcpus=flavor['vcpus'],
            disk=flavor['disk'],
            ephemeral=flavor['ephemeral'],
            swap=int(flavor['swap']) if flavor['swap'] else 0,
            rxtx_factor=flavor['rxtx_factor'],
            is_public=flavor['is_public'])

    def _deploy_flavors(self, flavors, tenant_map):
        dest_flavors = {flavor.name: flavor.id
                        for flavor in self.get_flavor_list(is_public=None)}
        for flavor_id in flavors:
            flavor = flavors[flavor_id]['flavor']
            dest_flavor_id = (dest_flavors.get(flavor['name']) or
                              self._create_flavor_if_not_exists(
                                  flavor, flavor_id).id)
            flavors[flavor_id]['meta']['id'] = dest_flavor_id
            if not flavor['is_public']:
                # user can specify tenant name instead of ID, which is ignored
                # by nova
                tenant_ids = [tenant_map[t] for t in flavor['tenants']
                              if tenant_map.get(t)]
                self._add_flavor_access_for_tenants(dest_flavor_id, tenant_ids)

    def _deploy_quotas(self, quotas, tenant_map, user_map=None):
        for _quota in quotas:
            old_tenant_id = _quota['tenant_id']
            tenant_id = tenant_map[old_tenant_id]
            user_id = None
            if user_map:
                old_user_id = _quota['user_id']
                user_id = user_map[old_user_id]
            quota = _quota['quota']
            quota_info = dict()

            for quota_name, quota_value in quota.iteritems():
                if quota_value != DEFAULT_QUOTA_VALUE:
                    quota_info[quota_name] = quota_value

            quota_info['force'] = True

            self.update_quota(tenant_id=tenant_id, user_id=user_id,
                              **quota_info)

    def deploy_instance(self, create_params, conf):
        with keystone.AddAdminUserToNonAdminTenant(
                self.identity.keystone_client,
                conf.cloud.user,
                conf.cloud.tenant):
            nclient = self.get_client(conf)
            new_id = self.create_instance(nclient, **create_params)
            try:
                self.wait_for_status(new_id, self.get_status, 'active',
                                     timeout=conf.migrate.boot_timeout,
                                     stop_statuses=[ERROR])
            except timeout_exception.TimeoutException:
                LOG.warning("Failed to create instance '%s'", new_id)
                self._failed_instances.append(new_id)
                raise

        return new_id

    def _deploy_instances(self, info_compute):
        new_ids = {}

        client_conf = copy.deepcopy(self.config)

        for _instance in info_compute['instances'].itervalues():
            instance = _instance['instance']
            LOG.debug("creating instance %s", instance['name'])
            create_params = {'name': instance['name'],
                             'flavor': instance['flavor_id'],
                             'key_name': instance['key_name'],
                             'nics': instance['nics'],
                             'image': instance['image_id'],
                             # user_id matches user_id on source
                             'user_id': instance.get('user_id')}
            if instance['boot_mode'] == utl.BOOT_FROM_VOLUME:
                volume_id = instance['volumes'][0]['id']
                create_params["block_device_mapping_v2"] = [{
                    "source_type": "volume",
                    "uuid": volume_id,
                    "destination_type": "volume",
                    "delete_on_termination": True,
                    "boot_index": 0
                }]
                create_params['image'] = None

            if (self.config.migrate.keep_affinity_settings and
                    instance['server_group'] is not None):
                create_params['scheduler_hints'] = {
                    'group': instance['server_group']}

            client_conf.cloud.tenant = instance['tenant_name']

            new_id = RandomSchedulerVmDeployer(self).deploy(instance,
                                                            create_params,
                                                            client_conf)

            new_ids[new_id] = instance['id']
        return new_ids

    def create_instance(self, nclient, **kwargs):
        # do not provide key pair as boot argument, it will be updated with the
        # low level SQL update. See
        # `cloudferrylib.os.actions.transport_compute_resources` for more
        # information
        ignored_instance_args = ['key_name', 'user_id']

        boot_args = {k: v for k, v in kwargs.items()
                     if k not in ignored_instance_args}
        LOG.debug("Creating instance with args '%s'",
                  pprint.pformat(boot_args))
        created_instance = nclient.servers.create(**boot_args)

        instances.update_user_ids_for_instance(self.mysql_connector,
                                               created_instance.id,
                                               kwargs['user_id'])

        LOG.debug("Created instance '%s'", created_instance.id)

        return created_instance.id

    def get_instances_list(self, detailed=True, search_opts=None, marker=None,
                           limit=None):
        """
        Get a list of servers.

        :param detailed: Whether to return detailed server info (optional).
        :param search_opts: Search options to filter out servers (optional).
        :param marker: Begin returning servers that appear later in the server
                       list than that represented by this server id (optional).
        :param limit: Maximum number of servers to return (optional).

        :rtype: list of :class:`Server`
        """
        ids = search_opts.get('id', None) if search_opts else None
        if not ids:
            servers = self.nova_client.servers.list(
                detailed=detailed, search_opts=search_opts, marker=marker,
                limit=limit)
        else:
            ids = ids if isinstance(ids, list) else [ids]
            servers = []
            for i in ids:
                try:
                    servers.append(self.nova_client.servers.get(i))
                except nova_exc.NotFound:
                    LOG.warning("No server with ID of '%s' exists.", i)

        active_computes = self.get_compute_hosts()
        servers = [i for i in servers
                   if getattr(i, INSTANCE_HOST_ATTRIBUTE) in active_computes]

        return servers

    def is_nova_instance(self, object_id):
        """
        Define OpenStack Nova Server instance by id.

        :param object_id: ID of supposed Nova Server instance
        :return: True - if it is Nova Server instance, False - if it is not
        """
        try:
            self.get_instance(object_id)
        except nova_exc.NotFound:
            LOG.error("%s is not a Nova Server instance", object_id)
            return False
        return True

    def get_instance(self, instance_id):
        return self.get_instances_list(search_opts={'id': instance_id})[0]

    def instance_exists(self, instance_id):
        """
        Define the instance exists.

        :param instance_id: ID of instance
        :return: True - if instance exists, False - if not
        """
        return bool(self.get_instances_list(search_opts={'id': instance_id}))

    def change_status_if_needed(self, instance):
        """
        Take VM status on source. Calculate result status on destination
        according STATUSES_AFTER_MIGRATION map. And try to change it.
        """
        needed_status = STATUSES_AFTER_MIGRATION[
            instance['meta']['source_status']]
        self.change_status(needed_status,
                           instance_id=instance['instance']['id'])

    def change_status(self, status, instance=None, instance_id=None):
        if instance_id:
            instance = self.nova_client.servers.get(instance_id)
        curr = self.get_status(instance.id).lower()
        will = status.lower()
        func_restore = {
            'start': lambda instance: instance.start(),
            'stop': lambda instance: instance.stop(),
            'resume': lambda instance: instance.resume(),
            'paused': lambda instance: instance.pause(),
            'unpaused': lambda instance: instance.unpause(),
            'suspended': lambda instance: instance.suspend(),
            'confirm_resize': lambda instance: instance.confirm_resize(),
            'status': lambda status: lambda instance: self.wait_for_status(
                instance_id,
                self.get_status,
                status)
        }
        map_status = {
            'paused': {
                'active': (func_restore['unpaused'],
                           func_restore['status']('active')),
                'shutoff': (func_restore['unpaused'],
                            func_restore['status']('active'),
                            func_restore['stop'],
                            func_restore['status']('shutoff')),
                'suspended': (func_restore['unpaused'],
                              func_restore['status']('active'),
                              func_restore['suspended'],
                              func_restore['status']('suspended'))
            },
            'suspended': {
                'active': (func_restore['resume'],
                           func_restore['status']('active')),
                'shutoff': (func_restore['resume'],
                            func_restore['status']('active'),
                            func_restore['stop'],
                            func_restore['status']('shutoff')),
                'paused': (func_restore['resume'],
                           func_restore['status']('active'),
                           func_restore['paused'],
                           func_restore['status']('paused'))
            },
            'active': {
                'paused': (func_restore['paused'],
                           func_restore['status']('paused')),
                'suspended': (func_restore['suspended'],
                              func_restore['status']('suspended')),
                'shutoff': (func_restore['stop'],
                            func_restore['status']('shutoff'))
            },
            'shutoff': {
                'active': (func_restore['start'],
                           func_restore['status']('active')),
                'paused': (func_restore['start'],
                           func_restore['status']('active'),
                           func_restore['paused'],
                           func_restore['status']('paused')),
                'suspended': (func_restore['start'],
                              func_restore['status']('active'),
                              func_restore['suspended'],
                              func_restore['status']('suspended')),
                'verify_resize': (func_restore['start'],
                                  func_restore['status']('active'))
            },
            'verify_resize': {
                'shutoff': (func_restore['confirm_resize'],
                            func_restore['status']('active'),
                            func_restore['stop'],
                            func_restore['status']('shutoff'))
            }
        }
        if curr != will:
            try:
                reduce(lambda res, f: f(instance), map_status[curr][will],
                       None)
            except timeout_exception.TimeoutException:
                LOG.warning("Failed to change state from '%s' to '%s' for VM "
                            "'%s'", curr, will, instance.name)

    def get_flavor_from_id(self, flavor_id, include_deleted=False):
        if include_deleted:
            return self.nova_client.flavors.get(flavor_id)
        else:
            return self.nova_client.flavors.find(id=flavor_id)

    def get_flavor_list(self, is_public=None, **kwargs):
        return self.nova_client.flavors.list(is_public=is_public, **kwargs)

    def create_flavor(self, **kwargs):
        return self.nova_client.flavors.create(**kwargs)

    def delete_flavor(self, flavor_id):
        self.nova_client.flavors.delete(flavor_id)

    def get_flavor_access_list(self, flavor_id):
        return self.nova_client.flavor_access.list(flavor=flavor_id)

    def add_flavor_access(self, flavor_id, tenant_id):
        self.nova_client.flavor_access.add_tenant_access(flavor_id, tenant_id)

    def get_quotas(self, tenant_id, user_id=None):
        return self.nova_client.quotas.get(tenant_id, user_id)

    def update_quota(self, tenant_id, user_id=None, **quota_items):
        return self.nova_client.quotas.update(tenant_id=tenant_id,
                                              user_id=user_id, **quota_items)

    def get_default_quotas(self):
        default_quotas = self.nova_client.quota_classes.get('default')
        default_quotas_info = self.convert_resources(default_quotas, None)
        return default_quotas_info['quota']

    def update_default_quotas(self, quota_items):
        existing_default_quotas = self.get_default_quotas()

        # To avoid redundant records in database
        for i in existing_default_quotas:
            if quota_items[i] == existing_default_quotas[i]:
                quota_items.pop(i)

        return self.nova_client.quota_classes.update('default', **quota_items)

    def get_interface_list(self, server_id):
        return self.nova_client.servers.interface_list(server_id)

    def interface_attach(self, server_id, port_id, net_id, fixed_ip):
        return self.nova_client.servers.interface_attach(server_id, port_id,
                                                         net_id, fixed_ip)

    def get_status(self, res_id):
        return self.nova_client.servers.get(res_id).status

    def get_networks(self, instance):
        network_resource = self.cloud.resources.get('network')
        if network_resource is not None:
            return network_resource.get_instance_network_info(instance.id)
        raise RuntimeError("Can't get network interface info without "
                           "network resource")

    def attach_volume_to_instance(self, instance, volume):
        self.nova_client.volumes.create_server_volume(
            instance['instance']['id'],
            volume['volume']['id'],
            volume['volume']['device'])

    def detach_volume(self, instance_id, volume_id):
        self.nova_client.volumes.delete_server_volume(instance_id, volume_id)

    def associate_floatingip(self, instance_id, floatingip):
        self.nova_client.servers.add_floating_ip(instance_id, floatingip)

    def dissociate_floatingip(self, instance_id, floatingip):
        self.nova_client.servers.remove_floating_ip(instance_id, floatingip)

    def get_hypervisor_statistics(self):
        return self.nova_client.hypervisors.statistics()

    def get_compute_hosts(self):
        computes = self.nova_client.services.list(binary='nova-compute')
        return [c.host for c in computes if host_available(c)]

    def get_free_vcpus(self):
        hypervisor_statistics = self.get_hypervisor_statistics()
        return (hypervisor_statistics.vcpus *
                self.config.compute.cpu_allocation_ratio -
                hypervisor_statistics.vcpus_used)

    def get_free_ram(self):
        hypervisor_statistics = self.get_hypervisor_statistics()
        return (hypervisor_statistics.memory_mb *
                self.config.compute.ram_allocation_ratio -
                hypervisor_statistics.memory_mb_used)

    def get_free_disk(self):
        hypervisor_statistics = self.get_hypervisor_statistics()
        return (hypervisor_statistics.local_gb *
                self.config.compute.disk_allocation_ratio -
                hypervisor_statistics.local_gb_used)

    def force_delete_vm_by_id(self, vm_id):
        """
        Reset state of VM and delete it.

        :param vm_id: ID of instance
        """
        self.reset_state(vm_id)
        self.delete_vm_by_id(vm_id)

    def delete_vm_by_id(self, vm_id):
        self.nova_client.servers.delete(vm_id)

    def live_migrate_vm(self, vm_id, destination_host):
        migration_type = self.config.migrate.incloud_live_migration
        if migration_type == 'cold':
            cold_evacuate.cold_evacuate(self.config, self.nova_client, vm_id,
                                        destination_host)
        else:
            # VM source host is taken from VM properties
            instances.incloud_live_migrate(self.nova_client, self.config,
                                           vm_id, destination_host)

    def get_instance_sql_id_by_uuid(self, uuid):
        sql = "select id from instances where uuid='%s'" % uuid
        libvirt_instance_id = self.mysql_connector.execute(sql).fetchone()[0]

        LOG.debug("Libvirt instance ID of VM '%s' is '%s'", uuid,
                  libvirt_instance_id)

        return libvirt_instance_id

    def update_instance_auto_increment(self, mysql_id):
        LOG.debug("Updating nova.instances auto_increment value to %s",
                  mysql_id)
        sql = ("alter table instances change id id INT (11) not null default "
               "{libvirt_id}").format(libvirt_id=mysql_id)

        self.mysql_connector.execute(sql)

    def reset_state(self, vm_id):
        self.get_instance(vm_id).reset_state()


def host_available(compute_host):
    """:returns: `True` if compute host is enabled in nova, `False`
    otherwise"""

    return compute_host.state == 'up' and compute_host.status == 'enabled'


# TODO: move these to a Instance class, which would represent internal instance
# data in cloudferry regardless of the backend used (openstack, vmware,
# cloudstack, etc)
def instance_libvirt_name(instance):
    return getattr(instance, INSTANCE_LIBVIRT_NAME_ATTRIBUTE)


def instance_host(instance):
    return getattr(instance, INSTANCE_HOST_ATTRIBUTE)
