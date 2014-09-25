from oslo.config import cfg

src = cfg.OptGroup(name='src',
                   title='Credetionals and general config for source cloud')

src_opts = [
    cfg.StrOpt('type', default="os",
               help='os - OpenStack Cloud'),
    cfg.StrOpt('host', default="-",
               help='ip-address controller for cloud'),
    cfg.StrOpt('user', default="-",
               help='user for access to API'),
    cfg.StrOpt('password', default="-",
               help='password for access to API'),
    cfg.StrOpt('tenant', default="-",
               help='tenant for access to API'),
    cfg.StrOpt('temp', default="-",
               help='temporary directory on controller')

]

dst = cfg.OptGroup(name='dst',
                   title='Credetionals and general config for destination cloud')

dst_opts = [
    cfg.StrOpt('type', default="os",
               help='os - OpenStack Cloud'),
    cfg.StrOpt('host', default="-",
               help='ip-address controller for cloud'),
    cfg.StrOpt('user', default="-",
               help='user for access to API'),
    cfg.StrOpt('password', default="-",
               help='password for access to API'),
    cfg.StrOpt('tenant', default="-",
               help='tenant for access to API'),
    cfg.StrOpt('temp', default="-",
               help='temporary directory on controller'),

]

migrate = cfg.OptGroup(name='migrate',
                       title='General config for migration process')

migrate_opts = [
    cfg.StrOpt('keep_user_passwords', default="yes",
               help='yes - keep user passwords, no - not keep user passwords'),
    cfg.StrOpt('key_filename', default="id_rsa",
               help='name pub key'),
    cfg.StrOpt('keep_ip', default="no",
               help='yes - keep ip, no - not keep ip'),
    cfg.StrOpt('speed_limit', default="10MB",
               help='speed limit for glance to glance'),
    cfg.StrOpt('instances', default="key_name-qwerty",
               help='filter instance by parametrs'),
    cfg.StrOpt('mail_server', default="-",
               help='name mail server'),
    cfg.StrOpt('mail_username', default="-",
               help='name username for mail'),
    cfg.StrOpt('mail_password', default="-",
               help='password for mail'),
    cfg.StrOpt('mail_from_addr', default="-",
               help='field FROM in letter'),
    cfg.StrOpt('file_compression', default="dd",
               help='gzip - use GZIP when file tranfering via ssh, dd - no compression, directly via dd'),
    cfg.IntOpt('level_compression', default="7",
               help='level compression for gzip'),
    cfg.StrOpt('ssh_transfer_port', default="9990",
               help='interval ports for ssh tunnel'),
    cfg.StrOpt('port', default="9990",
               help='interval ports for ssh tunnel')
]

src_mysql = cfg.OptGroup(name='src_mysql',
                         title='Config mysql for source cloud')

src_mysql_opts = [
    cfg.StrOpt('user', default="-",
               help='user for mysql'),
    cfg.StrOpt('password', default="-",
               help='password for mysql'),
    cfg.StrOpt('connection', default="mysql+mysqlconnector",
               help='driver for connection'),
]

src_compute = cfg.OptGroup(name='src_compute',
                           title='Config service for compute')

src_compute_opts = [
    cfg.StrOpt('service', default="nova",
               help='name service for compute'),
    cfg.StrOpt('backend', default="ceph",
               help='backend for ephemeral drives'),
    cfg.StrOpt('convert_diff_file', default="qcow2",
               help='convert diff file to'),
    cfg.StrOpt('convert_ephemeral_disk', default="qcow2",
               help='convert ephemeral disk to'),

]


src_storage = cfg.OptGroup(name='src_storage',
                           title='Config service for storage')

src_storage_opts = [
    cfg.StrOpt('service', default="cinder",
               help='name service for storage'),
    cfg.StrOpt('backend', default="iscsi",
               help='backend for storage'),
    cfg.StrOpt('protocol_transfer', default="GLANCE",
               help="mode transporting volumes GLANCE or SSH"),
    cfg.StrOpt('disk_format', default="qcow2",
               help='convert volume'),

]

src_images = cfg.OptGroup(name='src_images',
                          title='Config service for images')

src_images_opts = [
    cfg.StrOpt('service', default="glance",
               help='name service for images')
]

src_identity = cfg.OptGroup(name='src_identity',
                            title='Config service for identity')

src_identity_opts = [
    cfg.StrOpt('service', default="keystone",
               help='name service for keystone')
]


src_network = cfg.OptGroup(name='src_network',
                           title='Config service for network')

src_network_opts = [
    cfg.StrOpt('service', default="auto",
               help='name service for network, auto - detect avaiable service')
]

dst_mysql = cfg.OptGroup(name='dst_mysql',
                         title='Config mysql for destination cloud')

dst_mysql_opts = [
    cfg.StrOpt('user', default="-",
               help='user for mysql'),
    cfg.StrOpt('password', default="-",
               help='password for mysql'),
    cfg.StrOpt('connection', default="mysql+mysqlconnector",
               help='driver for connection'),
]

dst_compute = cfg.OptGroup(name='dst_compute',
                           title='Config service for compute')

dst_compute_opts = [
    cfg.StrOpt('service', default="nova",
               help='name service for compute'),
    cfg.StrOpt('backend', default="ceph",
               help='backend for ephemeral drives'),
    cfg.StrOpt('convert_diff_file', default="qcow2",
               help='convert diff file to'),
    cfg.StrOpt('convert_ephemeral_disk', default="qcow2",
               help='convert ephemeral disk to'),

]


dst_storage = cfg.OptGroup(name='dst_storage',
                           title='Config service for storage')

dst_storage_opts = [
    cfg.StrOpt('service', default="cinder",
               help='name service for storage'),
    cfg.StrOpt('backend', default="iscsi",
               help='backend for storage'),
    cfg.StrOpt('protocol_transfer', default="GLANCE",
               help="mode transporting volumes GLANCE or SSH"),
    cfg.StrOpt('disk_format', default="qcow2",
               help='convert volume'),

]

dst_images = cfg.OptGroup(name='dst_images',
                          title='Config service for images')

dst_images_opts = [
    cfg.StrOpt('service', default="glance",
               help='name service for images'),
    cfg.BoolOpt('convert_to_raw', default="True",
                help='convert to raw images')
]

dst_identity = cfg.OptGroup(name='dst_identity',
                            title='Config service for identity')

dst_identity_opts = [
    cfg.StrOpt('service', default="keystone",
               help='name service for keystone')
]


dst_network = cfg.OptGroup(name='dst_network',
                           title='Config service for network')

dst_network_opts = [
    cfg.StrOpt('service', default="auto",
               help='name service for network, auto - detect avaiable service'),
    cfg.ListOpt('interfaces_for_instance', default="net04",
                help='list interfaces for connection to instance')
]

import_rules = cfg.OptGroup(name='import_rules',
                            title='Import Rules for overwrite something fields')

import_rules_opts = [
    cfg.StrOpt('key', default="",
               help=''),
]

cfg_for_reg = [
    (src, src_opts),
    (dst, dst_opts),
    (migrate, migrate_opts),
    (src_mysql, src_mysql_opts),
    (src_compute, src_compute_opts),
    (src_storage, src_storage_opts),
    (src_identity, src_identity_opts),
    (src_images, src_images_opts),
    (src_network, src_network_opts),
    (dst_mysql, dst_mysql_opts),
    (dst_compute, dst_compute_opts),
    (dst_storage, dst_storage_opts),
    (dst_identity, dst_identity_opts),
    (dst_images, dst_images_opts),
    (dst_network, dst_network_opts),
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
    CONF(default_config_files=name_configs)


def get_plugins():
    plugins = __import__('plugins')
    dir_plugins = dir(plugins)
    exclude_field = ['__author__', '__builtins__', '__doc__', '__file__', '__name__', '__package__', '__path__']
    plugins = [(item, plugins.__dict__[item]) for item in dir_plugins if item not in exclude_field]
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
        name_configs.append('plugins/%s/configs/config.ini' % plugin[0])

if __name__ == "__main__":
    collector_configs_plugins()
    init_config()
