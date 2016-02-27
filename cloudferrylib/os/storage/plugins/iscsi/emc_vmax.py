# Copyright 2016 Mirantis Inc.
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
import random
import socket

import pywbem

from cloudferrylib.base import exception
from cloudferrylib.os.storage import cinder_db
from cloudferrylib.os.storage.plugins import base
from cloudferrylib.os.storage.plugins import copy_mechanisms
from cloudferrylib.os.storage.plugins.iscsi import iscsi
from cloudferrylib.utils import local
from cloudferrylib.utils import log
from cloudferrylib.utils import retrying
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)
EMC_ROOT = 'root/emc'


class BackendNotAvailable(exception.AbortMigrationError):
    pass


class VolumeBackendAPIException(exception.AbortMigrationError):
    pass


class ISCSIConnectionProperties(object):
    def __init__(self, iqn=None, target=None, lun=None):
        self.iqn = iqn
        self.target = target
        self.lun = lun

    def __repr__(self):
        return "iSCSIProps<target={target},iqn={iqn},lun={lun}>".format(
            target=self.target, iqn=self.iqn, lun=self.lun)


class EMCConnector(object):
    """
    Adds support for EMC VMAX-series appliances.

    Required configuration:
      - [[src|dst]_storage] vmax_ip
      - [[src|dst]_storage] vmax_port
      - [[src|dst]_storage] vmax_username
      - [[src|dst]_storage] vmax_password
      - [[src|dst]_storage] vmax_port_group
      - [[src|dst]_storage] vmax_fast_policy
    """

    def __init__(self, ip, port, user, password, port_groups, fast_policy,
                 pool_name, storage_backend_timeout, volume_name_template,
                 initiator_name):
        self.ip = ip
        self.port = port
        self.user = user
        self.password = password
        self.port_groups = port_groups
        self.fast_policy = fast_policy
        self.pool_name = pool_name
        self.volume_name_template = volume_name_template
        self.initiator_name = initiator_name
        self._storage_backend_timeout = storage_backend_timeout
        self._connection = None

    @property
    def connection(self):
        if self._connection is None:
            url = "http://{ip}:{port}".format(ip=self.ip, port=self.port)
            self._connection = pywbem.WBEMConnection(
                url, creds=(self.user, self.password),
                default_namespace=EMC_ROOT)
            if self._connection is None:
                msg = ("Cannot connect to EMC ECOM server at '{url}', check "
                       "your configuration and connectivity.".format(url=url))
                LOG.error(msg)
                raise BackendNotAvailable(msg)

        return self._connection

    def __repr__(self):
        return "EMC VMAX at {ip}".format(ip=self.ip)

    def _find_config_service(self, storage_system_name):
        configservices = self.connection.EnumerateInstanceNames(
            'EMC_ControllerConfigurationService', EMC_ROOT)
        for configservice in configservices:
            if storage_system_name == configservice['SystemName']:
                return configservice

    @staticmethod
    def _volume_name(volume):
        return 'volume-{}'.format(volume['id'])

    @staticmethod
    def _name(*args):
        return '-'.join(['CF-OS'] + list(args))[:64]

    def _storage_group_from_masking_view(self, view_name, system_name):
        masking_views = self.connection.EnumerateInstanceNames(
            'EMC_LunMaskingSCSIProtocolController')
        for view in masking_views:
            if system_name == view['SystemName']:
                instance = self.connection.GetInstance(view, LocalOnly=False)
                if view_name == instance['ElementName']:
                    groups = self.connection.AssociatorNames(
                        view,
                        ResultClass='CIM_DeviceMaskingGroup')
                    if groups[0] > 0:
                        return groups[0]

    def find_iscsi_connection_properties(self, masking):
        """Returns tuple (iqn, target, lun) for masking view created"""
        props = ISCSIConnectionProperties()
        unit_names = self.connection.ReferenceNames(
            masking['volumeInstance'],
            ResultClass='CIM_ProtocolControllerForUnit')
        tcp_endpoints = self.connection.EnumerateInstanceNames(
            'CIM_TCPProtocolEndpoint')

        for unit_name in unit_names:
            controller = unit_name['Antecedent']
            classname = controller['CreationClassName']
            if 'Symm_LunMaskingView' in classname:
                unit_instance = self.connection.GetInstance(unit_name,
                                                            LocalOnly=False)
                props.lun = int(unit_instance['DeviceNumber'], 16)
            elif 'Symm_MappingSCSIProtocolController' in classname:
                ctrlr = self.connection.GetInstance(controller,
                                                    LocalOnly=False)
                iqn = ctrlr['Name']
                for tcp_endpoint in tcp_endpoints:
                    if iqn == tcp_endpoint['Name']:
                        props.iqn = iqn
                        ep_instance = self.connection.GetInstance(tcp_endpoint)
                        host = ep_instance['ElementName']
                        port = str(ep_instance['PortNumber'])
                        props.target = ':'.join([host, port])
                        break

            if props.iqn is not None and props.lun is not None:
                break

        return props

    def populate_masking(self, volume):
        unique = volume.id
        pool = self.pool_name
        volume_name = self.volume_name_template % volume.id
        protocol = 'I'  # iSCSI

        volume_instance = self._get_volume_instance(volume)
        storage_system = volume_instance['SystemName']

        return {
            'controllerConfigService':
                self._find_config_service(storage_system),
            'sgGroupName': self._name(pool, protocol, unique, 'SG'),
            'maskingViewName': self._name(pool, protocol, unique, 'MV'),
            'igGroupName': self._name(protocol, unique, 'IG'),
            'pgGroupName': random.choice(self.port_groups),
            'volumeInstance': volume_instance,
            'volumeName': volume_name,
            'fastPolicy': self.fast_policy,
            'storageSystemName': storage_system
        }

    def find_masking_view(self, masking):
        volume_instance = masking['volumeInstance']
        masking_views = self.connection.EnumerateInstanceNames(
            'EMC_LunMaskingSCSIProtocolController')

        storage_name = volume_instance['SystemName']

        for masking_view_path in masking_views:
            if storage_name == masking_view_path['SystemName']:
                instance = self.connection.GetInstance(
                    masking_view_path, LocalOnly=False)
                if masking['maskingViewName'] == instance['ElementName']:
                    return masking_view_path

    def create_masking_view(self, masking):
        config_service = masking['controllerConfigService']
        masking_view_name = masking['maskingViewName']
        initiator_masking_group = self._find_or_create_initiator_group(masking)
        port_group = self._find_port_group(masking)
        masking_group = self._find_or_create_device_masking_group(masking)

        if port_group and masking_group and initiator_masking_group and \
                masking_view_name:
            rc, job = self.connection.InvokeMethod(
                'CreateMaskingView', config_service,
                ElementName=masking_view_name,
                InitiatorMaskingGroup=initiator_masking_group,
                DeviceMaskingGroup=masking_group,
                TargetMaskingGroup=port_group)
            self._wait_job_completion(rc, job)

            created_masking_view = self.connection.AssociatorNames(
                job['Job'], ResultClass='Symm_LunMaskingView')
            if created_masking_view:
                return created_masking_view[0]

    def _get_volume_instance(self, volume):
        try:
            pl = eval(volume.provider_location)
        except (SyntaxError, ValueError, TypeError):
            LOG.warning("Invalid provider location for volume '%s'",
                        volume.id)
            return None

        try:
            return pywbem.CIMInstanceName(
                classname=pl['classname'],
                namespace=EMC_ROOT,
                keybindings=pl['keybindings'])
        except NameError:
            LOG.warning("Unable to get volume instance from EMC ECOM")
            return None

    def _get_default_storage_group(self):
        return 'OS_default_' + self.fast_policy + '_SG'

    def delete_volume_from_default_sg(self, masking):
        volume_instance_name = masking['volumeInstance']

        default_storage_group = self._get_default_storage_group()

        sg_path = self.connection.AssociatorNames(
            volume_instance_name, ResultClass='CIM_DeviceMaskingGroup')

        if not sg_path:
            LOG.debug("Default storage group was already removed")
            return

        sg_path = sg_path[0]

        if sg_path['InstanceID'].split('+')[-1] == default_storage_group:
            rc, job_dict = self.connection.InvokeMethod(
                'RemoveMembers',
                masking['controllerConfigService'],
                MaskingGroup=sg_path,
                Members=[volume_instance_name])
            self._wait_job_completion(rc, job_dict)

    def _find_hardware_service(self, system_name):
        hw_services = self.connection.EnumerateInstanceNames(
            'EMC_StorageHardwareIDManagementService')
        for hw_service in hw_services:
            if system_name == hw_service['SystemName']:
                LOG.debug("Found Storage Hardware ID Management Service:"
                          "%(hw_service)s"
                          % {'hw_service': hw_service})
                return hw_service

    def _find_or_create_initiator_group(self, masking):
        system_name = masking['storageSystemName']
        hw_service = self._find_hardware_service(system_name)
        initiator_name = self.initiator_name

        initiator_group_ids = self.connection.AssociatorNames(
                masking['controllerConfigService'],
                ResultClass='CIM_InitiatorMaskingGroup')

        for initiator_group_id in initiator_group_ids:
            associators = self.connection.Associators(
                initiator_group_id, ResultClass='EMC_StorageHardwareID')
            for assoc in associators:
                # if EMC_StorageHardwareID matches the initiator,
                # we found the existing EMC_LunMaskingSCSIProtocolController
                # (Storage Group for VNX) we can use for masking a new LUN
                hardwareid = assoc['StorageID']
                if hardwareid.lower() == initiator_name.lower():
                    return initiator_group_id

        if not hw_service:
            LOG.warning("Hardware service for '%s' not found", system_name)
            return

        hardware_ids = self.connection.AssociatorNames(
            hw_service, ResultClass='SE_StorageHardwareID')

        for hw_instance_id in hardware_ids:
            hw_instance = self.connection.GetInstance(hw_instance_id)
            storage_id = hw_instance['StorageID']

            if storage_id.lower() == initiator_name.lower():
                break
        else:
            raise base.VolumeObjectNotFoundError('Initiator not found.')

        rc, create_group = self.connection.InvokeMethod(
            'CreateGroup',
            masking['controllerConfigService'],
            GroupName=masking['igGroupName'],
            Type=pywbem.Uint16(2),
            Members=[hw_instance_id])
        self._wait_job_completion(rc, create_group)

        return create_group['MaskingGroup']

    def _wait_job_completion(self, rc, job):
        # From ValueMap of JobState in CIM_ConcreteJob
        # 2L=New, 3L=Starting, 4L=Running, 32767L=Queue Pending
        # ValueMap("2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13..32767,
        # 32768..65535"),
        # Values("New, Starting, Running, Suspended, Shutting Down,
        # Completed, Terminated, Killed, Exception, Service,
        # Query Pending, DMTF Reserved, Vendor Reserved")]
        # NOTE(deva): string matching based on
        #             http://ipmitool.cvs.sourceforge.net/
        #             viewvc/ipmitool/ipmitool/lib/ipmi_chassis.c
        if rc == 0:
            return job

        retryer = retrying.retry(
            max_time=self._storage_backend_timeout,
            predicate_retval_as_arg=True,
            predicate=lambda j: j['JobState'] not in [2, 3, 4, 32767])
        job_name = job['Job']
        retryer.run(self.connection.GetInstance, job_name, LocalOnly=False)

    def _find_or_create_device_masking_group(self, masking):
        device_masking_groups = self.connection.AssociatorNames(
            masking['volumeInstance'],
            ResultClass='CIM_DeviceMaskingGroup')

        if device_masking_groups:
            return device_masking_groups[0]

        rc, create_group_job = self.connection.InvokeMethod(
            'CreateGroup',
            masking['controllerConfigService'],
            GroupName=masking['sgGroupName'],
            Type=pywbem.Uint16(4),
            Members=[masking['volumeInstance']])
        self._wait_job_completion(rc, create_group_job)
        return create_group_job.get('MaskingGroup')

    def _find_port_group(self, masking):
        port_group_name = masking['pgGroupName']
        config_service = masking['controllerConfigService']
        masking_group_names = self.connection.AssociatorNames(
            config_service, resultClass='CIM_TargetMaskingGroup')

        for masking_group_instance_name in masking_group_names:
            instance = self.connection.GetInstance(
                masking_group_instance_name, LocalOnly=False)
            if port_group_name == instance['ElementName']:
                return masking_group_instance_name

    def delete_masking_view(self, masking_view, volume):
        storage_system_name = masking_view['SystemName']
        config_service = self._find_config_service(storage_system_name)

        rc, delete_mv = self.connection.InvokeMethod(
            'DeleteMaskingView',
            config_service,
            ProtocolController=masking_view)
        self._wait_job_completion(rc, delete_mv)

        masking_groups = \
            self.connection.EnumerateInstanceNames('CIM_DeviceMaskingGroup',
                                                   EMC_ROOT)

        for masking_group in masking_groups:
            if volume.id in masking_group['InstanceID']:
                volume_instance = self._get_volume_instance(volume)
                rc, remove_members = self.connection.InvokeMethod(
                    'RemoveMembers',
                    config_service,
                    MaskingGroup=masking_group,
                    Members=[volume_instance])
                self._wait_job_completion(rc, remove_members)
                rc, delete_group = self.connection.InvokeMethod(
                    'DeleteGroup',
                    config_service,
                    MaskingGroup=masking_group)
                self._wait_job_completion(rc, delete_group)
                break


class EmcISCSIPlugin(base.CinderMigrationPlugin):
    """Adds support for EMC VMAX cinder backend

    Required configuration:
      - [[src|dst]_storage] vmax_ip
      - [[src|dst]_storage] vmax_port
      - [[src|dst]_storage] vmax_username
      - [[src|dst]_storage] vmax_password
      - [[src|dst]_storage] vmax_port_group
      - [[src|dst]_storage] vmax_fast_policy
    """

    PLUGIN_NAME = "iscsi-vmax"

    def __init__(self, emc_connector, cinder_db, iscsi_connector, my_ip):
        self.connected_volume = None
        self.created_masking_view = None
        self.emc = emc_connector
        self.cinder_db = cinder_db
        self.iscsi = iscsi_connector
        self.my_ip = my_ip

    def get_volume_object(self, context, volume_id):
        volume = self.cinder_db.get_cinder_volume(volume_id)
        LOG.debug("Finding if LUN for volume '%s' already exists", volume_id)

        masking = self.emc.populate_masking(volume)
        masking_view = self.emc.find_masking_view(masking)
        if not masking_view:
            self.emc.delete_volume_from_default_sg(masking)
            self.created_masking_view = self.emc.create_masking_view(masking)
        else:
            self.created_masking_view = masking_view

        props = self.emc.find_iscsi_connection_properties(masking)

        try:
            LOG.debug("Connecting iSCSI volume")
            self.iscsi.discover(props.target)
            block_device = self.iscsi.connect_volume(props.target,
                                                     props.iqn,
                                                     props.lun)
            self.connected_volume = props

            LOG.debug("Block device connected at %s", block_device)
        except (local.LocalExecutionFailed, iscsi.CannotConnectISCSIVolume):
            msg = "Unable to connect iSCSI volume '{}'".format(volume_id)
            LOG.warning(msg)
            raise base.VolumeObjectNotFoundError(msg)

        # TODO implicit dependency
        host = socket.gethostbyname(socket.gethostname())
        return copy_mechanisms.CopyObject(host=host, path=block_device)

    def cleanup(self, context, volume_id):
        if self.connected_volume:
            self.iscsi.disconnect_volume(self.connected_volume.target,
                                         self.connected_volume.iqn,
                                         self.connected_volume.lun)
        if self.created_masking_view:
            volume = self.cinder_db.get_cinder_volume(volume_id)
            self.emc.delete_masking_view(self.created_masking_view, volume)

    @classmethod
    def from_context(cls, context):
        vmax_ip = context.cloud_config.storage.vmax_ip
        vmax_port = context.cloud_config.storage.vmax_port
        vmax_user = context.cloud_config.storage.vmax_user
        vmax_password = context.cloud_config.storage.vmax_password
        vmax_port_groups = context.cloud_config.storage.vmax_port_groups
        vmax_fast_policy = context.cloud_config.storage.vmax_fast_policy
        vmax_pool_name = context.cloud_config.storage.vmax_pool_name
        vmax_iscsi_my_ip = context.cloud_config.storage.iscsi_my_ip
        vmax_initiator_name = context.cloud_config.storage.initiator_name

        volume_name_template = context.cloud_config.storage.\
            volume_name_template
        backend_timeout = context.cloud_config.migrate.storage_backend_timeout

        vmax_config_opts = [opt for opt in locals().keys()
                            if opt.startswith('vmax_')]
        missing_opts = [opt for opt in vmax_config_opts if opt is None]
        if any(missing_opts):
            msg = ("Invalid configuration specified for EMC storage backend, "
                   "following options must be specified: {}")
            msg = msg.format(', '.join(missing_opts))
            LOG.error(msg)
            raise exception.InvalidConfigException(msg)

        cinder = context.resources[utils.STORAGE_RESOURCE]

        vmax_connector = EMCConnector(vmax_ip,
                                      vmax_port,
                                      vmax_user,
                                      vmax_password,
                                      vmax_port_groups,
                                      vmax_fast_policy,
                                      vmax_pool_name,
                                      backend_timeout,
                                      volume_name_template,
                                      vmax_initiator_name)

        num_retries = context.cloud_config.migrate.retry
        sudo_pass = context.cloud_config.migrate.local_sudo_password
        timeout = context.cloud_config.migrate.storage_backend_timeout

        iscsi_connector = iscsi.ISCSIConnector(num_retries=num_retries,
                                               local_sudo_password=sudo_pass,
                                               storage_backend_timeout=timeout)
        db = cinder_db.CinderDBBroker(cinder.mysql_connector)

        return cls(vmax_connector, db, iscsi_connector, vmax_iscsi_my_ip)
