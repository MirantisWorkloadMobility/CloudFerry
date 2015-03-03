from oslo.config import cfg
import addons
src = cfg.OptGroup(name='src',
                   title='Credentials and general config for source cloud')

src_opts = [
    cfg.StrOpt('type', default='os',
               help='os - OpenStack Cloud'),
    cfg.StrOpt('host', default='-',
               help='ip-address controller for cloud'),
    cfg.StrOpt('ssh_host', default='',
               help='ip-address of cloud node for ssh connect'),
    cfg.StrOpt('ext_cidr', default='',
               help='external network CIDR'),
    cfg.StrOpt('user', default='-',
               help='user for access to API'),
    cfg.StrOpt('password', default='-',
               help='password for access to API'),
    cfg.StrOpt('tenant', default='-',
               help='tenant for access to API'),
    cfg.StrOpt('temp', default='-',
               help='temporary directory on controller')

]

dst = cfg.OptGroup(name='dst',
                   title='Credentials and general '
                         'config for destination cloud')

dst_opts = [
    cfg.StrOpt('type', default='os',
               help='os - OpenStack Cloud'),
    cfg.StrOpt('host', default='-',
               help='ip-address controller for cloud'),
    cfg.StrOpt('ssh_host', default='',
               help='ip-address of cloud node for ssh connect'),
    cfg.StrOpt('ext_cidr', default='',
               help='external network CIDR'),
    cfg.StrOpt('user', default='-',
               help='user for access to API'),
    cfg.StrOpt('password', default='-',
               help='password for access to API'),
    cfg.StrOpt('tenant', default='-',
               help='tenant for access to API'),
    cfg.StrOpt('temp', default='-',
               help='temporary directory on controller'),

]

migrate = cfg.OptGroup(name='migrate',
                       title='General config for migration process')

migrate_opts = [
    cfg.BoolOpt('keep_user_passwords', default=True,
               help='True - keep user passwords, '
                    'False - not keep user passwords'),
    cfg.StrOpt('key_filename', default='id_rsa',
               help='name pub key'),
    cfg.BoolOpt('keep_ip', default=False,
               help='yes - keep ip, no - not keep ip'),
    cfg.BoolOpt('migrate_extnets', default=False,
               help='yes - migrate external networks, no - do not migrate external networks'),
    cfg.BoolOpt('keep_floatingip', default=False,
               help='yes - keep floatingip, no - not keep floatingip'),
    cfg.BoolOpt('keep_lbaas', default=False,
               help='yes - keep lbaas settings, no - not keep lbaas settings'),
    cfg.BoolOpt('keep_volume_snapshots', default=False,
               help='yes - keep volume snapshots, no - not keep volume snapshots'),
    cfg.BoolOpt('keep_volume_storage', default=False,
               help='True - keep volume_storage, False - not keep volume_storage'),
    cfg.StrOpt('speed_limit', default='10MB',
               help='speed limit for glance to glance'),
    cfg.StrOpt('instances', default='key_name-qwerty',
               help='filter instance by parameters'),
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
                help='Direct data transmission between compute nodes via external network'),
    cfg.StrOpt('filter_path', default='configs/filter.yaml',
               help='path to the filter yaml file with options for search resources'),
    cfg.IntOpt('retry', default='7',
               help='Number retry if except Performing error'),
    cfg.IntOpt('time_wait', default='5',
               help='Time wait if except Performing error'),
    cfg.IntOpt('ssh_chunk_size', default=100,
               help='Size of one chunk to transfer via SSH')
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
    cfg.StrOpt('user', default='-',
               help='user for mysql'),
    cfg.StrOpt('password', default='-',
               help='password for mysql'),
    cfg.StrOpt('host', default='-',
               help='host of mysql'),
    cfg.StrOpt('connection', default='mysql+mysqlconnector',
               help='driver for connection'),
]

src_compute = cfg.OptGroup(name='src_compute',
                           title='Config service for compute')

src_compute_opts = [
    cfg.StrOpt('service', default='nova',
               help='name service for compute'),
    cfg.StrOpt('backend', default='ceph',
               help='backend for ephemeral drives'),
    cfg.StrOpt('convert_diff_file', default='qcow2',
               help='convert diff file to'),
    cfg.StrOpt('convert_ephemeral_disk', default='qcow2',
               help='convert ephemeral disk to'),
    cfg.StrOpt('host_eph_drv', default='-',
               help='host ephemeral drive')
]


src_storage = cfg.OptGroup(name='src_storage',
                           title='Config service for storage')

src_storage_opts = [
    cfg.StrOpt('service', default='cinder',
               help='name service for storage'),
    cfg.StrOpt('backend', default='iscsi',
               help='backend for storage'),
    cfg.StrOpt('host', default='',
               help='storage node ip address'),
    cfg.StrOpt('protocol_transfer', default='GLANCE',
               help='mode transporting volumes GLANCE or SSH'),
    cfg.StrOpt('disk_format', default='qcow2',
               help='convert volume'),
    cfg.StrOpt('volume_name_template', default='volume-',
               help='template for creating names of volumes on storage backend'),
    cfg.StrOpt('rbd_pool', default='volumes',
               help='name of pool for volumes in Ceph RBD storage'),
    cfg.StrOpt('snapshot_name_template', default='snapshot-',
               help='template for creating names of snapshots on storage backend')
]

src_image = cfg.OptGroup(name='src_image',
                         title='Config service for images')

src_image_opts = [
    cfg.StrOpt('service', default='glance',
               help='name service for images'),
    cfg.StrOpt('backend', default='file',
               help='backend for images')
]

src_identity = cfg.OptGroup(name='src_identity',
                            title='Config service for identity')

src_identity_opts = [
    cfg.StrOpt('service', default='keystone',
               help='name service for keystone')
]


src_network = cfg.OptGroup(name='src_network',
                           title='Config service for network')

src_network_opts = [
    cfg.StrOpt('service', default='auto',
               help='name service for network, '
                    'auto - detect avaiable service')
]

src_objstorage = cfg.OptGroup(name='src_objstorage',
                              title='Config service for object storage')

src_objstorage_opts = [
    cfg.StrOpt('service', default='swift',
               help='service name for object storage')
]

dst_mysql = cfg.OptGroup(name='dst_mysql',
                         title='Config mysql for destination cloud')

dst_mysql_opts = [
    cfg.StrOpt('user', default='-',
               help='user for mysql'),
    cfg.StrOpt('password', default='-',
               help='password for mysql'),
    cfg.StrOpt('host', default='-',
               help='host of mysql'),
    cfg.StrOpt('connection', default='mysql+mysqlconnector',
               help='driver for connection'),
]

dst_compute = cfg.OptGroup(name='dst_compute',
                           title='Config service for compute')

dst_compute_opts = [
    cfg.StrOpt('service', default='nova',
               help='name service for compute'),
    cfg.StrOpt('backend', default='ceph',
               help='backend for ephemeral drives'),
    cfg.StrOpt('convert_diff_file', default='qcow2',
               help='convert diff file to'),
    cfg.StrOpt('convert_ephemeral_disk', default='qcow2',
               help='convert ephemeral disk to'),
    cfg.StrOpt('host_eph_drv', default='-',
               help='host ephemeral drive')
]


dst_storage = cfg.OptGroup(name='dst_storage',
                           title='Config service for storage')

dst_storage_opts = [
    cfg.StrOpt('service', default='cinder',
               help='name service for storage'),
    cfg.StrOpt('backend', default='iscsi',
               help='backend for storage'),
    cfg.StrOpt('host', default='',
               help='storage node ip address'),
    cfg.StrOpt('protocol_transfer', default='GLANCE',
               help='mode transporting volumes GLANCE or SSH'),
    cfg.StrOpt('disk_format', default='qcow2',
               help='convert volume'),
    cfg.StrOpt('volume_name_template', default='volume-',
               help='template for creating names of volumes on storage backend'),
    cfg.StrOpt('rbd_pool', default='volumes',
               help='name of pool for volumes in Ceph RBD storage'),
    cfg.StrOpt('snapshot_name_template', default='snapshot-',
               help='template for creating names of snapshots on storage backend')
]

dst_image = cfg.OptGroup(name='dst_image',
                         title='Config service for images')

dst_image_opts = [
    cfg.StrOpt('service', default='glance',
               help='name service for images'),
    cfg.BoolOpt('convert_to_raw', default='True',
                help='convert to raw images'),
    cfg.StrOpt('backend', default='file',
               help='backend for images')
]

dst_identity = cfg.OptGroup(name='dst_identity',
                            title='Config service for identity')

dst_identity_opts = [
    cfg.StrOpt('service', default='keystone',
               help='name service for keystone')
]


dst_network = cfg.OptGroup(name='dst_network',
                           title='Config service for network')

dst_network_opts = [
    cfg.StrOpt('service', default='auto',
               help='name service for network, '
                    'auto - detect available service'),
    cfg.ListOpt('interfaces_for_instance', default='net04',
                help='list interfaces for connection to instance')
]

dst_objstorage = cfg.OptGroup(name='dst_objstorage',
                              title='Config service for object storage')

dst_objstorage_opts = [
    cfg.StrOpt('service', default='swift',
               help='service name for object storage')
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
    cfg.StrOpt('snapshot_path', default="/root/dump.sql"),
    cfg.StrOpt('host', default='')]

cfg_for_reg = [
    (src, src_opts),
    (dst, dst_opts),
    (migrate, migrate_opts),
    (mail, mail_opts),
    (src_mysql, src_mysql_opts),
    (src_compute, src_compute_opts),
    (src_storage, src_storage_opts),
    (src_identity, src_identity_opts),
    (src_image, src_image_opts),
    (src_network, src_network_opts),
    (src_objstorage, src_objstorage_opts),
    (dst_mysql, dst_mysql_opts),
    (dst_compute, dst_compute_opts),
    (dst_storage, dst_storage_opts),
    (dst_identity, dst_identity_opts),
    (dst_image, dst_image_opts),
    (dst_network, dst_network_opts),
    (dst_objstorage, dst_objstorage_opts),
    (snapshot, snapshot_opts),
    (import_rules, import_rules_opts)
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


def get_plugins():
    plugins = addons
    dir_plugins = dir(plugins)
    exclude_field = ['__author__', '__builtins__', '__doc__', '__file__',
                     '__name__', '__package__', '__path__']
    plugins = [(item, plugins.__dict__[item])
               for item in dir_plugins if item not in exclude_field]
    return plugins


def find_group(group):
    for g in xrange(len(cfg_for_reg)):
        if group.name == cfg_for_reg[g][0].name:
            return g
    return -1


def find_field(field, fields):
    for g in xrange(len(fields)):
        if field.name == fields[g].name:
            return g
    return -1


def merge_fields(index_pair, fields):
    for field in fields:
        index_field = find_field(field, cfg_for_reg[index_pair][1])
        if index_field >= 0:
            cfg_for_reg[index_pair][1][index_field] = field
        else:
            cfg_for_reg[index_pair][1].append(field)


def merge_cfg(cfg):
    for pair in cfg:
        index_pair = find_group(pair[0])
        if index_pair == -1:
            cfg_for_reg.append(pair)
        else:
            merge_fields(index_pair, pair[1])


def collector_configs_plugins():
    plugins = get_plugins()
    for plugin in plugins:
        merge_cfg(plugin[1].cfg_for_reg)
        name_configs.append('addons/%s/configs/config.ini' % plugin[0])

if __name__ == '__main__':
    collector_configs_plugins()
    init_config()
