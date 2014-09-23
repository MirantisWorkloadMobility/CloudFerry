from __future__ import print_function
from oslo.config import cfg

config = {}
 

clouds_source = cfg.OptGroup(name='clouds_source',
                             title='Credetionals and general config for source cloud')

clouds_source_opts = [
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

clouds_destination = cfg.OptGroup(name='clouds_destination',
                                  title='Credetionals and general config for destination cloud')

clouds_destination_opts = [
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
    cfg.StrOpt('keep_user_passwords', default="no",
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
               help='interval ports for ssh tunnel')
]

clouds_source_mysql = cfg.OptGroup(name='clouds_source_mysql',
                                   title='Config mysql for source cloud')

clouds_source_mysql_opts = [
    cfg.StrOpt('user', default="-",
               help='user for mysql'),
    cfg.StrOpt('password', default="-",
               help='password for mysql'),
    cfg.StrOpt('connection', default="mysql+mysqlconnector",
               help='driver for connection'),
]

clouds_source_services_compute = cfg.OptGroup(name='clouds_source_services_compute',
                                              title='Config service for compute')

clouds_source_services_compute_opts = [
    cfg.StrOpt('service', default="nova",
               help='name service for compute'),
    cfg.StrOpt('backend', default="ceph",
               help='backend for ephemeral drives'),
    cfg.StrOpt('convert_diff_file', default="qcow2",
               help='convert diff file to'),
    cfg.StrOpt('convert_ephemeral_disk', default="qcow2",
               help='convert ephemeral disk to'),

]


clouds_source_services_storage = cfg.OptGroup(name='clouds_source_services_storage',
                                              title='Config service for storage')

clouds_source_services_storage_opts = [
    cfg.StrOpt('service', default="cinder",
               help='name service for storage'),
    cfg.StrOpt('backend', default="iscsi",
               help='backend for storage'),
    cfg.StrOpt('protocol_transfer', default="GLANCE",
               help="mode transporting volumes GLANCE or SSH"),
    cfg.StrOpt('disk_format', default="qcow2",
               help='convert volume'),

]

clouds_source_services_images = cfg.OptGroup(name='clouds_source_services_images',
                                             title='Config service for images')

clouds_source_services_images_opts = [
    cfg.StrOpt('service', default="glance",
               help='name service for images')
]

clouds_source_services_identity = cfg.OptGroup(name='clouds_source_services_identity',
                                               title='Config service for identity')

clouds_source_services_identity_opts = [
    cfg.StrOpt('service', default="keystone",
               help='name service for keystone')
]


clouds_source_services_network = cfg.OptGroup(name='clouds_source_services_network',
                                              title='Config service for network')

clouds_source_services_network_opts = [
    cfg.StrOpt('service', default="auto",
               help='name service for network, auto - detect avaiable service')
]

clouds_destination_mysql = cfg.OptGroup(name='clouds_destination_mysql',
                                        title='Config mysql for destination cloud')

clouds_destination_mysql_opts = [
    cfg.StrOpt('user', default="-",
               help='user for mysql'),
    cfg.StrOpt('password', default="-",
               help='password for mysql'),
    cfg.StrOpt('connection', default="mysql+mysqlconnector",
               help='driver for connection'),
]

clouds_destination_services_compute = cfg.OptGroup(name='clouds_destination_services_compute',
                                                   title='Config service for compute')

clouds_destination_services_compute_opts = [
    cfg.StrOpt('service', default="nova",
               help='name service for compute'),
    cfg.StrOpt('backend', default="ceph",
               help='backend for ephemeral drives'),
    cfg.StrOpt('convert_diff_file', default="qcow2",
               help='convert diff file to'),
    cfg.StrOpt('convert_ephemeral_disk', default="qcow2",
               help='convert ephemeral disk to'),

]


clouds_destination_services_storage = cfg.OptGroup(name='clouds_destination_services_storage',
                                                   title='Config service for storage')

clouds_destination_services_storage_opts = [
    cfg.StrOpt('service', default="cinder",
               help='name service for storage'),
    cfg.StrOpt('backend', default="iscsi",
               help='backend for storage'),
    cfg.StrOpt('protocol_transfer', default="GLANCE",
               help="mode transporting volumes GLANCE or SSH"),
    cfg.StrOpt('disk_format', default="qcow2",
               help='convert volume'),

]

clouds_destination_services_images = cfg.OptGroup(name='clouds_destination_services_images',
                                                  title='Config service for images')

clouds_destination_services_images_opts = [
    cfg.StrOpt('service', default="glance",
               help='name service for images'),
    cfg.BoolOpt('convert_to_raw', default="True",
                help='convert to raw images')
]

clouds_destination_services_identity = cfg.OptGroup(name='clouds_destination_services_identity',
                                                    title='Config service for identity')

clouds_destination_services_identity_opts = [
    cfg.StrOpt('service', default="keystone",
               help='name service for keystone')
]


clouds_destination_services_network = cfg.OptGroup(name='clouds_destination_services_network',
                                                   title='Config service for network')

clouds_destination_services_network_opts = [
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

CONF = cfg.CONF
CONF.register_group(clouds_source)
CONF.register_opts(clouds_source_opts, clouds_source)
CONF.register_group(clouds_destination)
CONF.register_opts(clouds_destination_opts, clouds_destination)
CONF.register_group(migrate)
CONF.register_opts(migrate_opts, migrate)
CONF.register_group(clouds_source_mysql)
CONF.register_opts(clouds_source_mysql_opts, clouds_source_mysql)
CONF.register_group(clouds_source_services_compute)
CONF.register_opts(clouds_source_services_compute_opts, clouds_source_services_compute)
CONF.register_group(clouds_source_services_storage)
CONF.register_opts(clouds_source_services_storage_opts, clouds_source_services_storage)
CONF.register_group(clouds_source_services_images)
CONF.register_opts(clouds_source_services_images_opts, clouds_source_services_images)
CONF.register_group(clouds_source_services_identity)
CONF.register_opts(clouds_source_services_identity_opts, clouds_source_services_identity)
CONF.register_group(clouds_source_services_network)
CONF.register_opts(clouds_source_services_network_opts, clouds_source_services_network)
CONF.register_group(clouds_destination_mysql)
CONF.register_opts(clouds_destination_mysql_opts, clouds_destination_mysql)
CONF.register_group(clouds_destination_services_compute)
CONF.register_opts(clouds_destination_services_compute_opts, clouds_destination_services_compute)
CONF.register_group(clouds_destination_services_storage)
CONF.register_opts(clouds_destination_services_storage_opts, clouds_destination_services_storage)
CONF.register_group(clouds_destination_services_images)
CONF.register_opts(clouds_destination_services_images_opts, clouds_destination_services_images)
CONF.register_group(clouds_destination_services_identity)
CONF.register_opts(clouds_destination_services_identity_opts, clouds_destination_services_identity)
CONF.register_group(clouds_destination_services_network)
CONF.register_opts(clouds_destination_services_network_opts, clouds_destination_services_network)
CONF.register_group(import_rules)
CONF.register_opts(import_rules_opts, import_rules)


def init_global_config(name_config):
    CONF(default_config_files=[name_config])

if __name__ == "__main__":
    init_global_config('test.ini')
