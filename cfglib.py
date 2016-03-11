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


from oslo_config import cfg


src = cfg.OptGroup(name='src',
                   title='Credentials and general config for source cloud')

src_opts = [
    cfg.StrOpt('type', default='os',
               help='os - OpenStack Cloud'),
    cfg.StrOpt('auth_url', default='-',
               help='Keystone service endpoint for authorization'),
    cfg.StrOpt('host', default='-',
               help='ip-address controller for cloud'),
    cfg.StrOpt('ssh_host', default=None,
               help='ip-address of cloud node for ssh connect'),
    cfg.ListOpt('ext_cidr', default=[], help='external network CIDR'),
    cfg.StrOpt('user', default='-',
               help='user for access to API'),
    cfg.StrOpt('password', default='-',
               help='password for access to API'),
    cfg.StrOpt('tenant', default='-',
               help='tenant for access to API'),
    cfg.StrOpt('region', default=None,
               help='Openstack region name'),
    cfg.StrOpt('service_tenant', default='service',
               help='Tenant name for services'),
    cfg.StrOpt('ssh_user', default='root',
               help='user to connect via ssh'),
    cfg.StrOpt('ssh_sudo_password', default='',
               help='sudo password to connect via ssh, if any'),
    cfg.StrOpt('cacert', default='', help='SSL certificate'),
    cfg.BoolOpt('insecure', default=False,
                help='Allow to access servers without checking SSL certs')
]

dst = cfg.OptGroup(name='dst',
                   title='Credentials and general '
                         'config for destination cloud')

dst_opts = [
    cfg.StrOpt('type', default='os',
               help='os - OpenStack Cloud'),
    cfg.StrOpt('auth_url', default='-',
               help='Keystone service endpoint for authorization'),
    cfg.StrOpt('host', default='-',
               help='ip-address controller for cloud'),
    cfg.StrOpt('ssh_host', default=None,
               help='ip-address of cloud node for ssh connect'),
    cfg.ListOpt('ext_cidr', default=[], help='external network CIDR'),
    cfg.StrOpt('user', default='-',
               help='user for access to API'),
    cfg.StrOpt('password', default='-',
               help='password for access to API'),
    cfg.StrOpt('tenant', default='-',
               help='tenant for access to API'),
    cfg.StrOpt('region', default=None,
               help='Openstack region name'),
    cfg.StrOpt('service_tenant', default='service',
               help='Tenant name for services'),
    cfg.StrOpt('ssh_user', default='root',
               help='user to connect via ssh'),
    cfg.StrOpt('ssh_sudo_password', default='',
               help='sudo password to connect via ssh, if any'),
    cfg.StrOpt('cacert', default='', help='SSL certificate'),
    cfg.BoolOpt('insecure', default=False,
                help='Allow to access servers without checking SSL certs')
]

migrate = cfg.OptGroup(name='migrate',
                       title='General config for migration process')

migrate_opts = [
    cfg.BoolOpt('keep_user_passwords', default=True,
                help='True - keep user passwords, '
                     'False - not keep user passwords'),
    cfg.ListOpt('key_filename', default=['id_rsa'],
                help='private key(s) for interaction with clouds via ssh'),
    cfg.BoolOpt('keep_ip', default=False,
                help='yes - keep ip, no - not keep ip'),
    cfg.BoolOpt('migrate_extnets', default=False,
                help='yes - migrate external networks, '
                     'no - do not migrate external networks'),
    cfg.StrOpt('ext_net_map', default='configs/ext_net_map.yaml',
               help='path to the map of external networks, which contains '
                    'references between old and new ids'),
    cfg.BoolOpt('keep_floatingip', default=False,
                help='yes - keep floatingip, no - not keep floatingip'),
    cfg.BoolOpt('change_router_ips', default=False,
                help='change router external ip on dst cloud to '
                     'avoid ip collision by making additional floatingip '
                     'on dst as stub'),
    cfg.BoolOpt('clean_router_ips_stub', default=False,
                help='delete floating ip stub on dst after router migration'),
    cfg.StrOpt('router_ips_stub_tenant', default=None,
               help='tenant for creation router ip stubs, if it "None" as '
                    'default stub creates in router tenant'),
    cfg.BoolOpt('keep_lbaas', default=False,
                help='yes - keep lbaas settings, '
                     'no - not keep lbaas settings'),
    cfg.BoolOpt('keep_volume_snapshots', default=False,
                help='yes - keep volume snapshots, '
                     'no - not keep volume snapshots'),
    cfg.BoolOpt('keep_volume_storage', default=False,
                help='True - keep volume_storage, '
                     'False - not keep volume_storage'),
    cfg.StrOpt('speed_limit', default='off',
               help='speed limit for glance to glance'),
    cfg.StrOpt('file_compression', default='dd',
               help='gzip - use GZIP when file transferring via ssh, '
                    ' - no compression, directly via dd'),
    cfg.IntOpt('level_compression', default='7',
               help='level compression for gzip'),
    cfg.StrOpt('ssh_transfer_port', default='9990',
               help='interval ports for ssh tunnel'),
    cfg.StrOpt('port', default='9990',
               help='interval ports for ssh tunnel'),
    cfg.BoolOpt('overwrite_user_passwords', default=False,
                help='Overwrite password for exists users on destination'),
    cfg.BoolOpt('migrate_quotas', default=False,
                help='Migrate tenant quotas'),
    cfg.StrOpt('disk_format', default='qcow2',
               help='format when covert volume to image'),
    cfg.StrOpt('container_format', default='bare',
               help='container format when covert volume to image'),
    cfg.BoolOpt('direct_compute_transfer', default=False,
                help='Direct data transmission between compute nodes '
                     'via external network'),
    cfg.StrOpt('filter_path', default='configs/filter.yaml',
               help='path to the filter yaml file with options '
                    'for search resources'),
    cfg.IntOpt('retry', default='7',
               help='Number retry if except Performing error'),
    cfg.IntOpt('time_wait', default=5,
               help='Time wait if except Performing error'),
    cfg.IntOpt('ssh_chunk_size', default=100,
               help='Size of one chunk to transfer via SSH'),
    cfg.StrOpt('group_file_path', default="vm_groups.yaml",
               help='Path to file with the groups of VMs'),
    cfg.StrOpt('scenario', default='scenario/migrate.yaml',
               help='Path to a scenario file, which holds the whole migration '
                    'procedure. Must be YAML format'),
    cfg.StrOpt('tasks_mapping', default='scenario/tasks.yaml',
               help='Path to a file which holds CloudFerry python code tasks '
                    'mapped to migration scenario items. Items defined in '
                    'this file must be used in the migration scenario.'),
    cfg.BoolOpt('migrate_users', default=True,
                help='Migrate users'),
    cfg.BoolOpt('migrate_user_quotas', default=True,
                help='Migrate user quotas. If it set in "false" only tenant '
                     'quotas will be migrated. Use this in case when '
                     'OpenStack does not support user quotas (e.g. Grizzly)'),
    cfg.StrOpt('incloud_live_migration', default='nova',
               help='Live migration type used for in-cloud live migration. '
                    'Possible values: "nova", "cobalt".'),
    cfg.StrOpt('mysqldump_host',
               help='IP or hostname used for creating MySQL dump for rollback.'
                    'If not set uses `[dst] db_host` config option.'),
    cfg.BoolOpt('optimize_user_role_fetch', default=True,
                help="Uses low-level DB requests if set to True, "
                "may be incompatible with more recent versions of "
                "Keystone. Tested on grizzly, icehouse and juno."),
    cfg.IntOpt('ssh_connection_attempts', default=3,
               help='Number of times CloudFerry will attempt to connect when '
                    'connecting to a new server via SSH.'),
    cfg.BoolOpt('ignore_empty_images',
                help='Ignore images with size 0 and exclude them from '
                     'migration process', default=False),
    cfg.BoolOpt('hide_ssl_warnings', default=False,
                help="Don't show ssl warnings"),
    cfg.BoolOpt('keep_affinity_settings', default=False,
                help="Keep affinity/anti-affinity settings"),
    cfg.IntOpt('boot_timeout', default=300,
               help="Timeout booting of instance"),
    cfg.StrOpt('ssh_cipher', default=None, help='SSH cipher to use for SCP'),
    cfg.StrOpt('copy_backend', default="rsync",
               help="Allows to choose how ephemeral storage and cinder "
                    "volumes are copied over from source to destination. "
                    "Possible values: 'rsync' (default), 'scp' and 'bbcp'. "
                    "scp seem to be faster, while rsync is more reliable, "
                    "but bbcp works in multithreading mode."),
    cfg.BoolOpt('copy_with_md5_verification', default=True,
                help="Calculate md5 checksum for source and copied files and "
                     "verify them."),
    cfg.StrOpt('log_config', default='configs/logging_config.yaml',
               help='The path of a logging configuration file.'),
    cfg.BoolOpt('forward_stdout', default=True,
                help="Forward messages from stdout to log."),
    cfg.BoolOpt('debug', default=False,
                help="Print debugging output (set logging level to DEBUG "
                     "instead of default INFO level)."),
    cfg.BoolOpt('keep_network_interfaces_order', default=True,
                help="Keep the order of network interfaces of instances."),
    cfg.IntOpt('num_processes_for_volume_migration', default=5,
               help="Defines number of parallel processes for cinder volume "
                    "migration process. Does not parallelize migration of "
                    "other resources."),
    cfg.StrOpt('local_sudo_password', default=None,
               help='Password to be used for sudo command if needed on the '
                    'local host'),
    cfg.IntOpt('storage_backend_timeout', default=300,
               help='Time to wait for cinder volume backend to complete '
                    'typical action, like create or delete simple volume. '
                    'Value is in seconds.'),
    cfg.BoolOpt('keep_usage_quotas_inst', default=True,
                help="Keep the usage quotas for instances."),
    cfg.BoolOpt('skip_orphaned_keypairs', default=True,
                help="If it is set to False - key pairs belonging to deleted "
                     "tenant or to deleted user on SRC will be assigned to "
                     "the admin on DST, otherwise skipped."),
    cfg.StrOpt('override_rules', default=None,
               help='Server creation parameter (e.g. server group) override '
                    'rules file path.'),
]

mail = cfg.OptGroup(name='mail',
                    title='Mail credentials for notifications')

mail_opts = [
    cfg.StrOpt('server', default='-',
               help='name mail server'),
    cfg.StrOpt('username', default='-',
               help='name username for mail'),
    cfg.StrOpt('password', default='-',
               help='password for mail'),
    cfg.StrOpt('from_addr', default='-',
               help='field FROM in letter')
]

src_mysql = cfg.OptGroup(name='src_mysql',
                         title='Config mysql for source cloud')

src_mysql_opts = [
    cfg.StrOpt('db_user', default='-',
               help='user for mysql'),
    cfg.StrOpt('db_password', default='-',
               help='password for mysql'),
    cfg.StrOpt('db_host', default='-',
               help='host of mysql'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_connection', default='mysql+pymysql',
               help='driver for connection'),
]


src_rabbit = cfg.OptGroup(name='src_rabbit',
                          title='Config RabbitMQ for source cloud')

src_rabbit_opts = [
    cfg.StrOpt('user', default='guest',
               help='user for RabbitMQ'),
    cfg.StrOpt('password', default='guest',
               help='password for RabbitMQ'),
    cfg.StrOpt('hosts', default='-',
               help='comma separated RabbitMQ hosts')
]

src_compute = cfg.OptGroup(name='src_compute',
                           title='Config service for compute')

src_compute_opts = [
    cfg.StrOpt('service', default='nova',
               help='name service for compute'),
    cfg.StrOpt('backend', default='ceph',
               help='backend for ephemeral drives'),
    cfg.BoolOpt('disk_overcommit', default=False,
                help='live-migration allow disk overcommit'),
    cfg.BoolOpt('block_migration', default=False,
                help='live-migration without shared_storage'),
    cfg.StrOpt('host_eph_drv', default='-',
               help='host ephemeral drive'),
    cfg.StrOpt('db_connection', default='mysql+pymysql',
               help='driver for db connection'),
    cfg.StrOpt('db_host', default=None,
               help='compute mysql node ip address'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_name', default=None,
               help='compute database name'),
    cfg.StrOpt('db_user', default=None,
               help='user for db access'),
    cfg.StrOpt('db_password', default=None,
               help='password for db access'),
]


src_storage = cfg.OptGroup(name='src_storage',
                           title='Config service for storage')

src_storage_opts = [
    cfg.StrOpt('service', default='cinder',
               help='name service for storage'),
    cfg.StrOpt('backend', default='nfs',
               help='Cinder volume backend. Possible values: nfs, iscsi-vmax'),
    cfg.StrOpt('host', default=None,
               help='storage node ip address'),
    cfg.StrOpt('db_host', default=None,
               help='storage service db ip address'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_user', default=None,
               help='user for db access (if backend == db)'),
    cfg.StrOpt('db_password', default=None,
               help='password for db access (if backend == db)'),
    cfg.StrOpt('db_name', default=None,
               help='cinder_database name (if backend == db)'),
    cfg.StrOpt('db_connection', default=None,
               help='driver for connection'),
    cfg.StrOpt('protocol_transfer', default='GLANCE',
               help='mode transporting volumes GLANCE or SSH'),
    cfg.StrOpt('disk_format', default='qcow2',
               help='convert volume'),
    cfg.StrOpt('rbd_pool', default='volumes',
               help='name of pool for volumes in Ceph RBD storage'),
    cfg.StrOpt('snapshot_name_template', default='snapshot-',
               help='template for creating names of snapshots '
                    'on storage backend'),
    cfg.StrOpt('conf', default='/etc/cinder/cinder.conf',
               help="Path to cinder config file"),
    cfg.StrOpt('vmax_ip', default=None,
               help='IP address or hostname of EMC VMAX storage. Used with '
                    '"vmax" backend'),
    cfg.StrOpt('vmax_port', default=None,
               help='IP port of EMC VMAX storage. Used with "vmax" backend'),
    cfg.StrOpt('vmax_user', default=None,
               help='Username to access EMC VMAX APIs. Used with "vmax" '
                    'backend'),
    cfg.StrOpt('vmax_password', default=None,
               help='Pasword required to access EMC VMAX APIs. Used with '
                    '"vmax" backend'),
    cfg.ListOpt('vmax_port_groups', default=None,
                help='Port group used for EMC VMAX'),
    cfg.StrOpt('vmax_fast_policy', default=None,
               help='Fast policy for EMC VMAX'),
    cfg.StrOpt('vmax_pool_name', default=None,
               help='Pool name for EMC VMAX'),
    cfg.StrOpt('volume_name_template', default='volume-%s',
               help="Represents volume_name_template cinder config value. "
                    "Volume files will be stored following the pattern."),
    cfg.StrOpt('iscsi_my_ip', default=None,
               help="Local host IP address which is used to connect to iSCSI "
                    "target"),
    cfg.ListOpt('nfs_mount_point_bases', default=['/var/lib/cinder'],
                help="Represents nfs_mount_point_base cinder config option. "
                     "Defines list of paths where volume files are created."),
    cfg.StrOpt('initiator_name', default=None,
               help="InitiatorName from /etc/iscsi/initiatorname.iscsi")
]

src_image = cfg.OptGroup(name='src_image',
                         title='Config service for images')

src_image_opts = [
    cfg.StrOpt('service', default='glance',
               help='name service for images'),
    cfg.StrOpt('db_user', default=None,
               help='user for db access (if backend == db)'),
    cfg.StrOpt('db_host', default=None,
               help='glance mysql node ip address'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_password', default=None,
               help='password for db access (if backend == db)'),
    cfg.StrOpt('db_name', default=None,
               help='glance_database name (if backend == db)'),
    cfg.StrOpt('db_connection', default=None,
               help='driver for connection'),
    cfg.StrOpt('backend', default='file',
               help='backend for images')
]

src_identity = cfg.OptGroup(name='src_identity',
                            title='Config service for identity')

src_identity_opts = [
    cfg.StrOpt('db_user', default=None,
               help='user for mysql'),
    cfg.StrOpt('db_password', default=None,
               help='password for mysql'),
    cfg.StrOpt('db_host', default=None,
               help='host of mysql'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_connection', default=None,
               help='driver for connection'),
    cfg.StrOpt('service', default='keystone',
               help='name service for keystone'),
    cfg.StrOpt('db_name', default='',
               help='database name')

]


src_network = cfg.OptGroup(name='src_network',
                           title='Config service for network')

src_network_opts = [
    cfg.StrOpt('service', default='auto',
               help='name service for network, '
                    'auto - detect avaiable service'),
    cfg.StrOpt('db_host', default=None,
               help='Neutron DB node host'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_password', default=None,
               help='Neutron DB password'),
    cfg.StrOpt('db_name', default=None,
               help='Neutron database name'),
    cfg.StrOpt('db_connection', default=None,
               help='Neutron DB connection type'),
    cfg.StrOpt('db_user', default=None,
               help="DB user for the networking backend"),
    cfg.StrOpt('get_all_quota', default=False,
               help="If False, then qoutas will be taken only customs,"
                    " else All quotas including default and custom")

]

src_objstorage = cfg.OptGroup(name='src_objstorage',
                              title='Config service for object storage')

src_objstorage_opts = [
    cfg.StrOpt('service', default='swift',
               help='service name for object storage'),
    cfg.StrOpt('db_name', default='',
               help='database name'),
]

dst_mysql = cfg.OptGroup(name='dst_mysql',
                         title='Config mysql for destination cloud')

dst_mysql_opts = [
    cfg.StrOpt('db_user', default='-',
               help='user for mysql'),
    cfg.StrOpt('db_password', default='-',
               help='password for mysql'),
    cfg.StrOpt('db_host', default='-',
               help='host of mysql'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_connection', default='mysql+pymysql',
               help='driver for connection'),
]

dst_rabbit = cfg.OptGroup(name='dst_rabbit',
                          title='Config RabbitMQ for source cloud')

dst_rabbit_opts = [
    cfg.StrOpt('user', default='guest',
               help='user for RabbitMQ'),
    cfg.StrOpt('password', default='guest',
               help='password for RabbitMQ'),
    cfg.StrOpt('hosts', default='-',
               help='comma separated RabbitMQ hosts'),
    cfg.StrOpt('db_name', default=None,
               help='database name'),
]


dst_compute = cfg.OptGroup(name='dst_compute',
                           title='Config service for compute')

dst_compute_opts = [
    cfg.StrOpt('service', default='nova',
               help='name service for compute'),
    cfg.StrOpt('backend', default='ceph',
               help='backend for ephemeral drives'),
    cfg.BoolOpt('disk_overcommit', default=False,
                help='live-migration allow disk overcommit'),
    cfg.BoolOpt('block_migration', default=False,
                help='live-migration without shared_storage'),
    cfg.StrOpt('host_eph_drv', default='-',
               help='host ephemeral drive'),
    cfg.FloatOpt('cpu_allocation_ratio', default='16',
                 help='cpu allocation ratio'),
    cfg.FloatOpt('ram_allocation_ratio', default='1',
                 help='ram allocation ratio'),
    cfg.FloatOpt('disk_allocation_ratio', default='0.9',
                 help='disk allocation ratio'),
    cfg.StrOpt('db_connection', default=None,
               help='driver for db connection'),
    cfg.StrOpt('db_host', default=None,
               help='compute mysql node ip address'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_name', default=None,
               help='compute database name'),
    cfg.StrOpt('db_user', default=None,
               help='user for db access'),
    cfg.StrOpt('db_password', default=None,
               help='password for db access'),
]


dst_storage = cfg.OptGroup(name='dst_storage',
                           title='Config service for storage')

dst_storage_opts = [
    cfg.StrOpt('service', default='cinder',
               help='name service for storage'),
    cfg.StrOpt('backend', default='nfs',
               help='Cinder volume backend. Possible values: nfs, iscsi-vmax'),
    cfg.StrOpt('host', default=None,
               help='storage node ip address'),
    cfg.StrOpt('db_host', default=None,
               help='storage service db ip address'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_user', default=None,
               help='user for db access (if backend == db)'),
    cfg.StrOpt('db_password', default=None,
               help='password for db access (if backend == db)'),
    cfg.StrOpt('db_name', default=None,
               help='cinder_database name (if backend == db)'),
    cfg.StrOpt('db_connection', default=None,
               help='driver for connection'),
    cfg.StrOpt('protocol_transfer', default='GLANCE',
               help='mode transporting volumes GLANCE or SSH'),
    cfg.StrOpt('disk_format', default='qcow2',
               help='convert volume'),
    cfg.StrOpt('rbd_pool', default='volumes',
               help='name of pool for volumes in Ceph RBD storage'),
    cfg.StrOpt('snapshot_name_template', default='snapshot-',
               help='template for creating names of snapshots '
                    'on storage backend'),
    cfg.StrOpt('conf', default='/etc/cinder/cinder.conf',
               help="Path to cinder config file"),
    cfg.StrOpt('vmax_ip', default=None,
               help='IP address or hostname of EMC VMAX storage. Used with '
                    '"vmax" backend'),
    cfg.StrOpt('vmax_port', default=None,
               help='IP port of EMC VMAX storage. Used with "vmax" backend'),
    cfg.StrOpt('vmax_user', default=None,
               help='Username to access EMC VMAX APIs. Used with "vmax" '
                    'backend'),
    cfg.StrOpt('vmax_password', default=None,
               help='Pasword required to access EMC VMAX APIs. Used with '
                    '"vmax" backend'),
    cfg.ListOpt('vmax_port_groups', default=None,
                help='Port group used for EMC VMAX'),
    cfg.StrOpt('vmax_fast_policy', default=None,
               help='Fast policy for EMC VMAX'),
    cfg.StrOpt('vmax_pool_name', default=None,
               help='Pool name for EMC VMAX'),
    cfg.StrOpt('volume_name_template', default='volume-%s',
               help="Represents volume_name_template cinder config value. "
                    "Volume files will be stored following the pattern."),
    cfg.StrOpt('iscsi_my_ip', default=None,
               help="Local host IP address which is used to connect to iSCSI "
                    "target"),
    cfg.ListOpt('nfs_mount_point_bases', default=['/var/lib/cinder'],
                help="Represents nfs_mount_point_base cinder config option. "
                     "Defines list of paths where volume files are created."),
    cfg.StrOpt('initiator_name', default=None,
               help="InitiatorName from /etc/iscsi/initiatorname.iscsi")
]

dst_image = cfg.OptGroup(name='dst_image',
                         title='Config service for images')

dst_image_opts = [
    cfg.StrOpt('service', default='glance',
               help='name service for images'),
    cfg.BoolOpt('convert_to_raw', default='True',
                help='convert to raw images'),
    cfg.StrOpt('db_host', default=None,
               help='glance mysql node ip address'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_user', default=None,
               help='user for db access (if backend == db)'),
    cfg.StrOpt('db_password', default=None,
               help='password for db access (if backend == db)'),
    cfg.StrOpt('db_name', default=None,
               help='glance_database name (if backend == db)'),
    cfg.StrOpt('db_connection', default=None,
               help='driver for connection'),
    cfg.StrOpt('backend', default='file',
               help='backend for images')
]

dst_identity = cfg.OptGroup(name='dst_identity',
                            title='Config service for identity')

dst_identity_opts = [
    cfg.StrOpt('db_user', default=None,
               help='user for mysql'),
    cfg.StrOpt('db_password', default=None,
               help='password for mysql'),
    cfg.StrOpt('db_host', default=None,
               help='host of mysql'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_connection', default=None,
               help='driver for connection'),
    cfg.StrOpt('service', default='keystone',
               help='name service for keystone'),
    cfg.StrOpt('db_name', default=None,
               help='database name')
]


dst_network = cfg.OptGroup(name='dst_network',
                           title='Config service for network')

dst_network_opts = [
    cfg.StrOpt('service', default='auto',
               help='name service for network, '
                    'auto - detect available service'),
    cfg.StrOpt('db_host', default=None,
               help='Neutron DB node host'),
    cfg.IntOpt('db_port', default=3306,
               help='port for mysql connection'),
    cfg.StrOpt('db_password', default=None,
               help='Neutron DB password'),
    cfg.StrOpt('db_name', default=None,
               help='Neutron database name'),
    cfg.StrOpt('db_connection', default=None,
               help='Neutron DB connection type'),
    cfg.StrOpt('db_user', default=None,
               help="DB user for the networking backend"),
    cfg.StrOpt('get_all_quota', default=False,
               help="If False, then qoutas will be taken only customs, "
                    "else All quotas including default and custom")
]

dst_objstorage = cfg.OptGroup(name='dst_objstorage',
                              title='Config service for object storage')

dst_objstorage_opts = [
    cfg.StrOpt('service', default='swift',
               help='service name for object storage'),
    cfg.StrOpt('db_name', default=None,
               help='database name')
]

import_rules = cfg.OptGroup(name='import_rules',
                            title='Import Rules for '
                                  'overwrite something fields')

import_rules_opts = [
    cfg.StrOpt('key', default='',
               help=''),
]

snapshot = cfg.OptGroup(name='snapshot',
                        title="Rules for snapshot")

snapshot_opts = [
    cfg.StrOpt('snapshot_path', default="dump.sql")]

initial_check = cfg.OptGroup(name='initial_check',
                             title='Some configuration to initial checks')

initial_check_opts = [
    cfg.IntOpt('claimed_bandwidth', default=100,
               help='Claimed bandwidth of network (Mb/s).'),
    cfg.FloatOpt('factor', default=0.5,
                 help='The percentage of the allowable loss of network speed'),
    cfg.IntOpt('test_file_size', default=100,
               help='Size of testing file to send/receive via network (MB).'),
]

condense = cfg.OptGroup(name='condense',
                        title="options for condensation")

condense_opts = [
    cfg.FloatOpt('ram_reduction_coef', default=1),
    cfg.FloatOpt('core_reduction_coef', default=4),
    cfg.StrOpt('flavors_file', default='flavors.json'),
    cfg.StrOpt('nodes_file', default='nodes.json'),
    cfg.StrOpt('vms_file', default='vms.json'),
    cfg.StrOpt('group_file', default='groups.yaml'),
    cfg.BoolOpt('keep_interim_data', default=False,
                help=("Stores interim data required for the condensation "
                      "process to run in files defined in `flavors_file`, "
                      "`nodes_file`, and `group_file` config options.")),
    cfg.IntOpt('precision', default=85)]

database = cfg.OptGroup(name="database",
                        title="options for database")

database_opts = [
    cfg.StrOpt("host", default="localhost"),
    cfg.IntOpt("port", default=6379)]


evacuation = cfg.OptGroup(name='evacuation',
                          title='Evacuation related settings')

evacuation_opts = [
    cfg.StrOpt('nova_home_path', default='/var/lib/nova',
               help='Home directory of user under which nova services are '
                    'running'),
    cfg.StrOpt('nova_user', default='nova',
               help='Name of user under which nova services are running'),
    cfg.IntOpt('state_change_timeout', default=120,
               help='For how much seconds to wait for VM state change '
                    'during evacuation'),
    cfg.IntOpt('migration_timeout', default=600,
               help='For how much seconds to wait for VM to migrate '
                    'during evacuation'),
]

bbcp_group = cfg.OptGroup(name='bbcp', title='BBCP related settings')

bbcp_opts = [
    cfg.StrOpt('path', default='bbcp',
               help='path to the executable bbcp to execute on the cloudferry '
                    'host'),
    cfg.StrOpt('src_path', default='$path',
               help='path to the compiled bbcp for the source cloud hosts'),
    cfg.StrOpt('dst_path', default='$path',
               help='path to the compiled bbcp for the destination cloud '
                    'hosts'),
    cfg.StrOpt('options', default='-P 20', help='additional options'),
]

cfg_for_reg = [
    (src, src_opts),
    (dst, dst_opts),
    (migrate, migrate_opts),
    (mail, mail_opts),
    (src_mysql, src_mysql_opts),
    (src_rabbit, src_rabbit_opts),
    (src_compute, src_compute_opts),
    (src_storage, src_storage_opts),
    (src_identity, src_identity_opts),
    (src_image, src_image_opts),
    (src_network, src_network_opts),
    (src_objstorage, src_objstorage_opts),
    (dst_mysql, dst_mysql_opts),
    (dst_rabbit, dst_rabbit_opts),
    (dst_compute, dst_compute_opts),
    (dst_storage, dst_storage_opts),
    (dst_identity, dst_identity_opts),
    (dst_image, dst_image_opts),
    (dst_network, dst_network_opts),
    (dst_objstorage, dst_objstorage_opts),
    (snapshot, snapshot_opts),
    (import_rules, import_rules_opts),
    (initial_check, initial_check_opts),
    (condense, condense_opts),
    (database, database_opts),
    (import_rules, import_rules_opts),
    (evacuation, evacuation_opts),
    (bbcp_group, bbcp_opts),
]

CONF = cfg.CONF

name_configs = ['configs/config.ini']


def init_config(name_config=None):
    for i in cfg_for_reg:
        CONF.register_group(i[0])
        CONF.register_opts(i[1], i[0])
    if name_config:
        name_configs[0] = name_config
    CONF(default_config_files=name_configs, args="")
