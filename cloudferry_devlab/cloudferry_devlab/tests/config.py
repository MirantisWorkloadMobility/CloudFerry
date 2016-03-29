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

INVALID_STATUSES = ['creating', 'error', 'deleting', 'error_deleting']

img_url = 'http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img'
username_for_ssh = 'cirros'
"""Username for ssh access for cirros image"""

password_for_ssh = 'cubswin:)'
"""Password for ssh access for cirros image"""

cloud_ferry_conf = 'configuration.ini'
"""Path to CloudFerry config relative to the root folder"""

ssh_check_user = 'cirros'
ssh_vm_shell = '/bin/sh -c'

logging_configuration = {
    'version': 1,
    'formatters': {
        'simple': {'format': '%(asctime)s - %(levelname)s - %(message)s'}
    },
    'handlers': {
        'simple_handler': {'class': 'logging.StreamHandler',
                           'formatter': 'simple',
                           'level': 'INFO'}
    },
    'loggers': {
        'cloudferry_devlab.generate_load': {'handlers': ['simple_handler'],
                                            'level': 'INFO',
                                            'propagate': False},
        'cloudferry_devlab.tests.cleanup': {'handlers': ['simple_handler'],
                                            'level': 'INFO',
                                            'propagate': False}
    }
}

filters_file_naming_template = 'filter_{tenant_name}.yaml'
"""Naming template for filter files."""

pre_migration_vm_states_file = 'pre_migration_vm_states.json'
"""Filename to save vm states before migration."""

ext_net_map = 'ext_net_map.yaml'
"""This file contains map of relationships between external networks on source
and destination clouds."""

users = [
    {'name': 'user1', 'password': 'passwd1', 'email': 'mail@example.com',
     'tenant': 'tenant1', 'enabled': True},
    {'name': 'user2', 'password': 'passwd2', 'email': 'aa@example.com',
     'tenant': 'tenant2', 'enabled': True},
    {'name': 'user3', 'password': 'paafdssswd1', 'email': 'mdsail@example.com',
     'enabled': False},
    {'name': 'user4', 'password': 'asaasdf', 'tenant': 'tenant2',
     'enabled': False},
    {'name': 'test_volume_migration', 'password': 'passwd', 'enabled': True,
     'email': 'volume_test@example.com', 'tenant': 'tenant1', 'deleted': True},
    {'name': 'user5', 'password': 'passwd', 'email': 'asdasd@example.com',
     'tenant': 'tenant3', 'enabled': True},
    {'name': 'user6', 'password': 'passwd', 'email': 'testd@example.com',
     'tenant': 'tenant3', 'enabled': True, 'additional_tenants':
        [{'name': 'tenant1', 'role': '_member_'}]},
    {'name': 'user7', 'password': 'passwd', 'email': 'user7@example.com',
     'tenant': 'tenant4', 'enabled': True},
    {'name': 'user8', 'password': 'passwd', 'email': 'tenant3@example.com',
     'tenant': 'tenant3', 'enabled': True}
]
"""Users to create/delete"""

user_tenant_roles = [
    {'user1': [{'tenant': 'tenant1', 'role': 'SomeRole'}]}
]

roles = [
    {'name': 'SomeRole'}, {'name': 'SecondRole'}
]
"""Roles to create/delete"""

tenants = [
    {'name': 'tenant1', 'description': 'None', 'enabled': True,
     'quota': {'instances': '20', 'cores': '19', 'ram': '52199',
               'floating_ips': '9', 'fixed_ips': '', 'metadata_items': '',
               'injected_files': '', 'injected_file_content_bytes': '',
               'injected_file_path_bytes': '', 'key_pairs': '5',
               'security_groups': '9', 'security_group_rules': ''},
     'quota_network': {
         'floatingip': 60,
         'network': 12,
         'port': 90,
         'router': 14,
         'subnet': 55
     },
     'quota_cinder': {
         'gigabytes': 700, 'gigabytes_nfs1': -1, 'gigabytes_nfs2': 1000,
         'snapshots': 9, 'snapshots_nfs1': 8, 'snapshots_nfs2': 7,
         'volumes': 6, 'volumes_nfs1': 5, 'volumes_nfs2': 4,
     },
     'server_groups': [
         {'name': 'tn1_server_group', 'policies': ['affinity']},
         {'name': 'tn1_server_group2', 'policies': ['affinity']}
     ],
     'vms': [
         {'name': 'tn1server1', 'image': 'image1', 'flavor': 'flavorname2',
          'key_name': 'key1', 'server_group': 'tn1_server_group'},
         {'name': 'tn1server2', 'image': 'image1', 'flavor': 'flavorname1',
          'server_group': 'tn1_server_group'},
         {'name': 'server6', 'image': 'image1', 'flavor': 'del_flvr',
          'server_group': 'tn1_server_group2'}],
     'networks': [
         {'name': 'tenantnet1', 'admin_state_up': True,
          'subnets': [
              {'cidr': '10.5.2.0/24', 'ip_version': 4, 'name': 't1_s1',
               'routers_to_connect': ['tn1_router']}]},
         {'name': 'tenant1_net2', 'admin_state_up': True,
          'subnets': [
              {'cidr': '10.6.2.0/24', 'ip_version': 4, 'name': 't1_s2',
               'routers_to_connect': ['tn2_router']}]
          }
     ],
     'routers': [
         {'router': {'external_gateway_info': {}, 'name': 'tn1_router',
                     'admin_state_up': True}}
     ],
     'pools': [
         {
             'name': "pool2",
             'tenant_name': "tenant1",
             'subnet_name': "t1_s1",
             'protocol': "HTTPS",
             'lb_method': "SOURCE_IP"}
     ],
     'monitors': [
         {
             'tenant_name': "tenant1",
             'type': "PING",
             'delay': 600,
             'timeout': 100,
             'max_retries': 10
         }
     ],
     'members_lbaas': [
         {
             'protocol_port': "83",
             'address': "10.5.2.1",
             'pool_name': "pool2",
             'tenant_name': "tenant1"
         }
     ],
     'vips': [
         {
             'name': "vip2",
             'description': "111",
             'address': "10.5.2.5",
             'protocol': "HTTPS",
             'protocol_port': "83",
             'connection_limit': 100,
             'pool_name': "pool2",
             'tenant_name': "tenant1",
             'subnet_name': "t1_s1"
         }
     ],
     'security_groups': [
         {'name': 'sg11', 'description': 'Blah blah group', 'rules': [
             {'ip_protocol': 'icmp',
              'from_port': '0',
              'to_port': '255',
              'cidr': '0.0.0.0/0'},
             {'ip_protocol': 'tcp',
              'from_port': '80',
              'to_port': '80',
              'cidr': '0.0.0.0/0'}]
          },
         {'name': 'sg12', 'description': 'Blah blah group2'}],
     'cinder_volumes': [
         {'display_name': 'tn1_volume1', 'size': 1,
          'volume_type': 'nfs1',
          'server_to_attach': 'tn1server1', 'device': '/dev/vdb'},
         {'display_name': 'tn1_volume2', 'size': 1,
          'volume_type': 'nfs2', 'metadata': {'tenant_data': 'tenant_rocks',
                                              'enabled': "True", 'exists': ""}}
         ],
     'cinder_snapshots': [
         # Commented because of unimplemented error in nfs driver for grizzly.
         # {'name': 'tn1snapsh', 'volume_id': 'tn1_volume2'}
     ],
     'flavors': [
         {'name': 'tn1fl1', 'disk': '1', 'ram': '64', 'vcpus': '1'}
     ]
     },
    {'name': 'tenant2', 'description': 'Bljakslhf ajsdfh', 'enabled': True,
     'quota_network': {
         'floatingip': 90,
         'network': 12,
         'port': 90,
         'router': 14,
         'subnet': 60
     },
     'vms': [
         {'name': 'tn2server1', 'image': 'image1', 'flavor': 'flavorname2',
          'fip': True, 'key_name': 'key2', 'nics': [{'net-id': 'tenantnet2'}]},
         {'name': 'keypair_test_server', 'image': 'deleted_image',
          'flavor': 'flavorname2', 'key_name': 'key2', 'nics': [
              {'net-id': 'tenantnet2'}], 'fip': True}],
     'networks': [
         {'name': 'tenantnet2', 'admin_state_up': True,
          'subnets': [
              {'cidr': '22.2.2.0/24', 'ip_version': 4, 'name': 't2_s1',
               'routers_to_connect': ['tn2_router']}]
          }
     ],
     'routers': [
         {'router': {'external_gateway_info': {}, 'name': 'tn2_router',
                     'admin_state_up': True}}
     ],
     'cinder_volumes': [
         {'display_name': 'tn_volume1', 'size': 1, 'volume_type': 'nfs1',
          'server_to_attach': 'tn2server1', 'device': '/dev/vdb',
          'mount_point': '/tmp/mount_here/',
          'write_to_file': [
              {'filename': 'test_data.txt', 'data': 'some useless string'},
              {'filename': 'test/dir/test_data.txt',
               'data': 'test data string'}]}
         ],
     'unassociated_fip': 3
     },
    {'name': 'tenant3', 'description': 'This tenant will be deleted',
     'enabled': True, 'deleted': True,
     'networks': [
         {'name': 'tenantnet3', 'admin_state_up': True,
          'subnets': [
              {'cidr': '10.7.2.0/24', 'ip_version': 4, 'name': 't3_s1',
               'routers_to_connect': ['ext_router']}]}],
     'vms': [
         {'name': 'tn3server1', 'image': 'image1', 'flavor': 'flavorname1',
          'key_name': 'key4'}],
     'cinder_volumes': [
         {'display_name': 'tn3_volume1', 'size': 1,
          'server_to_attach': 'tn3server1', 'device': '/dev/vdb'}],
     'cinder_snapshots': [],
     'images': [{'name': 'image6', 'copy_from': img_url, 'is_public': False}],
     'flavors': [
         {'name': 'tn3fl1', 'disk': '1', 'ram': '64', 'vcpus': '1'}
     ],
     'pools': [
         {
             'name': "pool3",
             'tenant_name': "tenant3",
             'subnet_name': "t3_s1",
             'protocol': "HTTPS",
             'lb_method': "SOURCE_IP"}
     ],
     'monitors': [
         {
             'tenant_name': "tenant3",
             'type': "PING",
             'delay': 600,
             'timeout': 100,
             'max_retries': 10
         }
     ],
     'members_lbaas': [
         {
             'protocol_port': "83",
             'address': "10.7.2.8",
             'pool_name': "pool3",
             'tenant_name': "tenant3"
         }
     ],
     'vips': [
         {
             'name': "vip3",
             'description': "111",
             'address': "10.7.2.9",
             'protocol': "HTTPS",
             'protocol_port': "83",
             'connection_limit': 100,
             'pool_name': "pool3",
             'tenant_name': "tenant3",
             'subnet_name': "t3_s1"
         }
     ]
     },
    {'name': 'tenant4', 'description': 'None', 'enabled': True,
     'quota': {'instances': '4', 'cores': '9', 'ram': '84399',
               'floating_ips': '3', 'fixed_ips': '', 'metadata_items': '',
               'injected_files': '', 'injected_file_content_bytes': '',
               'injected_file_path_bytes': '', 'key_pairs': '3',
               'security_groups': '5', 'security_group_rules': ''},
     'neutron_quotas': [{'security_group_rule': 100, 'subnet': 10,
                         'tenant_id': '', 'network': 10, 'floatingip': 3,
                         'security_group': 10, 'router': 10, 'port': 50}],
     'images': [{'name': 'cirros_image_for_tenant4', 'copy_from': img_url,
                 'is_public': True}],
     'networks': [
         {'name': 'tenantnet4', 'admin_state_up': True,
          'subnets': [
              {'cidr': '33.33.33.0/24', 'ip_version': 4, 'name': 't4_s1',
               'routers_to_connect': ['ext_router']}]},
         {'name': 'tenantnet4_segm_id_cidr1', 'admin_state_up': True,
          'shared': False,
          'router:external': False, 'real_network': False,
          'provider:segmentation_id': 177,
          'provider:network_type': 'gre',
          'subnets': [
              {'cidr': '31.31.31.0/24', 'ip_version': 4,
               'name': 'segm_id_test_subnet_1', 'connect_to_ext_router': False,
               }
              ]
          },
         {'name': 'tenantnet4_segm_id_cidr2', 'admin_state_up': True,
          'shared': False,
          'router:external': False, 'real_network': False,
          'provider:segmentation_id': 178,
          'provider:network_type': 'gre',
          'subnets': [
              {'cidr': '40.40.40.0/24', 'ip_version': 4,
               'name': 'segm_id_test_subnet_2', 'connect_to_ext_router': False,
               }
              ]
          }],
     'security_groups': [
         {'name': 'sg41', 'description': 'Tenant4 blah blah group', 'rules': [
             {'ip_protocol': 'icmp',
              'from_port': '0',
              'to_port': '255',
              'cidr': '0.0.0.0/0'},
             {'ip_protocol': 'tcp',
              'from_port': '80',
              'to_port': '80',
              'cidr': '0.0.0.0/0'}]
          },
         {'name': 'sg42', 'description': 'Tenant4 blah group2'}],
     'cinder_volumes': [],
     'cinder_snapshots': []
     }
]
"""Tenants to create/delete"""

images = [
    {'name': 'image1', 'copy_from': img_url, 'is_public': True},
    {'name': 'image2', 'copy_from': img_url, 'container_format': 'bare',
     'disk_format': 'qcow2', 'is_public': False},
    {'name': 'image3', 'copy_from': img_url, 'container_format': 'bare',
     'disk_format': 'qcow2', 'is_public': False},
    {'name': 'image4', 'copy_from': img_url, 'container_format': 'bare',
     'disk_format': 'qcow2', 'is_public': False},
    {'name': 'image5', 'copy_from': img_url, 'container_format': 'bare',
     'disk_format': 'qcow2', 'is_public': False},
    # When location field is specified, glance creates images without checksum
    {'name': 'without_checksum', 'location': img_url, 'disk_format': 'qcow2',
     'container_format': 'bare'},
    # Image, deleted from back-end
    {'name': 'broken_image', 'copy_from': img_url, 'disk_format': 'qcow2',
     'container_format': 'bare', 'broken': True},
    # Image, deleted using glance delete command
    {'name': 'deleted_image', 'copy_from': img_url, 'disk_format': 'qcow2',
     'container_format': 'bare', 'is_deleted': True, 'is_public': True},
    # Image will be created on src and dst with the same UUID.
    # After that deleted from dst before migration.
    # CF must create new UUID during migration for this image
    # and migrate it successfully
    {'name': 'deleted_on_dst', 'id': 'e38390f0-e660-42fc-b8cd-db163fce1510',
     'copy_from': img_url, 'disk_format': 'qcow2',
     'container_format': 'bare', 'upload_on_dst': True, 'delete_on_dst': True}
]
"""Images to create/delete"""

swift_containers = [
    {'name': 'container1',
     'objects': [
         {'name': 'object1',
          'random_contents_size_in_MB': 10,
          'metadata': {"content-type": "Superuser"}},
         {'name': 'object2',
          'random_contents_size_in_MB': 10,
          'metadata': {"X-Object-Meta-Color": "Yellow"}},
         {'name': 'treefile/subtree1',
          'contents': 'some content for object'},
         {'name': 'treefile/subtree2',
          'random_contents_size_in_MB': 100},
     ]}
]
"""Swift containers and ojects to create"""

create_zero_image = True
"""Create zero image, without any parameters"""

images_not_included_in_filter = ['image5']
"""Images not to be migrated"""

vms_not_in_filter = ['not_in_filter']
"""Instances not to be included in filter"""

members = ['tenant1']
"""Images that should have few specific members"""

img_to_add_members = ['image3', 'image4', 'image6']

flavors = [
    {'name': 'flavorname1', 'disk': '1', 'ram': '64', 'vcpus': '1'},
    {'name': 'flavorname3', 'disk': '10', 'ram': '32', 'vcpus': '1',
     'is_public': False},
    {'name': 'flavorname2', 'disk': '2', 'ram': '48', 'vcpus': '2'},
    {'name': 'del_flvr', 'disk': '1', 'ram': '64', 'vcpus': '1'},
    {'name': 'deleted_flavor', 'flavorid': '777', 'disk': '1', 'ram': '48',
     'vcpus': '1', "ephemeral": '0', 'is_deleted': True},
    {'name': 'recreated_flavor', 'flavorid': '777', 'disk': '1', 'ram': '48',
     'vcpus': '1', "ephemeral": '2'}
]
"""Flavors to create/delete.
`deleted_flavor` flavor covers this scenario:
- In source cloud
   -- Create flavor with ID 3 with ephemeral == 0
   -- Delete flavor
   -- Create new flavor with the same ID with ephemeral > 0
 - Run migration"""

networks = [
    {'name': 'mynetwork1', 'admin_state_up': True,
     'subnets': [
         {'cidr': '10.4.2.0/24', 'ip_version': 4, 'name': 'subnet_1',
          'connect_to_ext_router': True, 'routers_to_connect': ['ext_router']},
         {'cidr': '10.9.2.0/24', 'ip_version': 4, 'name': 'subnet_2',
          "dns_nameservers": ["10.9.2.1"], 'connect_to_ext_router': True,
          'routers_to_connect': ['ext_router']}]
     },
    {'name': 'shared_net', 'admin_state_up': True, 'shared': True,
     'router:external': True, 'real_network': True,
     'provider:physical_network': 'physnet1', 'provider:network_type': 'flat',
     'subnets': [
         {'cidr': '192.168.1.0/24', 'ip_version': 4, 'name': 'external_subnet',
          'set_as_gateway_for_routers': {'ext_router': {'enable_snat': False},
                                         'tn1_router': {}, 'tn2_router': {}},
          'dns_nameservers': ['8.8.8.8', '8.8.4.4'],
          'allocation_pools': [
              {'start': '192.168.1.100', 'end': '192.168.1.254'}]
          }]
     }
]
"""Networks to create/delete. Only one gateway can be assigned to router.
If two networks have the same router in 'routers_to_connect', gateway set for
last networks (updating).
Test scenario:
 - Create subnets with cidr, ip_version, name, allication_pools,
  dns_nameservers attributes in source cloud
 - Run network migration
 - Verify all attributes migrated """

pools = [
    {
        'name': "pool1",
        'tenant_name': "admin",
        'subnet_name': "subnet_1",
        'protocol': "HTTPS",
        'lb_method': "SOURCE_IP"
    }]
members_lbaas = [
    {
        'protocol_port': "83",
        'address': "10.4.2.1",
        'pool_name': "pool1",
        'tenant_name': 'admin'
    }
]
monitors = [
    {
        'tenant_name': "admin",
        'type': "PING",
        'delay': 600,
        'timeout': 100,
        'max_retries': 10
    }]
vips = [
    {
        'name': "vip1",
        'description': "111",
        'address': "10.4.2.5",
        'protocol': "HTTPS",
        'protocol_port': "83",
        'connection_limit': 100,
        'pool_name': "pool1",
        'tenant_name': "admin",
        'subnet_name': "subnet_1"
        },
    ]

dst_routers = [
    {'router': {'external_gateway_info': {}, 'name': 'another_ext_router',
                'admin_state_up': True}
     }
]

dst_networks = [
    {'name': 'test_segm_id_cidr1', 'admin_state_up': True,
     'shared': False, 'router:external': False, 'real_network': False,
     'provider:segmentation_id': 177, 'provider:network_type': 'gre',
     'subnets': [
         {'cidr': '31.31.31.0/24', 'ip_version': 4,
          'name': 'segm_id_test_subnet_1', 'connect_to_ext_router': True,
          'routers_to_connect': ['another_ext_router']
          }
         ]
     },
    {'name': 'test_segm_id_cidr2', 'admin_state_up': True,
     'shared': False, 'router:external': False, 'real_network': False,
     'provider:segmentation_id': 178, 'provider:network_type': 'gre',
     'subnets': [
         {'cidr': '41.41.41.0/24', 'ip_version': 4,
          'name': 'segm_id_test_subnet_2', 'connect_to_ext_router': True,
          'routers_to_connect': ['another_ext_router']
          }
         ]
     },
    {'name': 'another_shared_net', 'admin_state_up': True, 'shared': True,
     'router:external': True, 'real_network': True,
     'provider:physical_network': 'physnet2', 'provider:network_type': 'flat',
     'subnets': [
         {'cidr': '172.16.1.0/24', 'ip_version': 4,
          'set_as_gateway_for_routers':
              {'another_ext_router': {'enable_snat': False}},
          'name': 'another_ext_subnet', 'allocation_pools': [
              {'start': '172.16.1.100', 'end': '172.16.1.254'}]
          }]
     }]

dst_unassociated_fip = 4
"""Amount of unassociated Floating IP will be created on DST cloud."""

server_groups = [
    {'name': 'admin_server_group', 'policies': ['anti-affinity']}
]
"""Server groups to create"""

vms = [
    {'name': 'server1', 'image': 'image1', 'flavor': 'flavorname1'},
    {'name': 'server2', 'image': 'image2', 'flavor': 'flavorname1'},
    {'name': 'server3', 'image': 'deleted_image', 'flavor': 'flavorname2',
     'fip': True},
    {'name': 'server4', 'image': 'deleted_image', 'flavor': 'flavorname2'},
    {'name': 'server5', 'image': 'image1', 'flavor': 'flavorname1'},
    {'name': 'not_in_filter', 'image': 'image1', 'flavor': 'flavorname1'},
    {'name': 'server7', 'image': 'image1', 'flavor': 'flavorname1',
     'broken': True},
    {'name': 'server8', 'image': 'broken_image', 'flavor': 'flavorname1',
     'server_group': 'admin_server_group'}
]
"""VM's to create/delete"""

vms_from_volumes = [
    {'name': 'server_from_volume', 'flavor': 'flavorname1',
     'volume': 'volume_from_image'}
]

routers = [
    {'router': {'external_gateway_info': {}, 'name': 'ext_router',
                'admin_state_up': True}
     }
]

snapshots = [
    {'server': 'server2', 'image_name': 'asdasd'}
]
"""VM's snapshots to create/delete"""

cinder_volumes = [
    {'display_name': 'cinder_volume1', 'size': 1, 'volume_type': 'nfs1'},
    {'display_name': 'cinder_volume2', 'size': 1,
     'volume_type': 'nfs2',  'metadata': {'data': 'nope', 'enabled': "False"},
     'server_to_attach': 'server2', 'device': '/dev/vdb'},
    {'display_name': 'cinder_volume3', 'size': 1,
     'user': 'test_volume_migration'}
]
"""Cinder images to create/delete.
To write some date, use "write_to_file" parameter. Now only string could be
written into the file. Make sure volume is attached to the server, before write
data. MD5 of file store in separate file in the same directory with name
"${filename}_md5"."""

cinder_volumes_from_images = [
    {'display_name': 'volume_from_image', 'size': 1, 'image': 'image1',
     'volume_type': 'nfs1'}
]

cinder_snapshots = [
    # Commented because of unimplemented error in nfs driver for grizzly.
    # {'display_name': 'snapsh1', 'volume_id': 'cinder_volume1'}
]
"""Cinder snapshots to create/delete"""

vm_states = [
    {'name': 'server1', 'state': 'error'},
    {'name': 'server2', 'state': 'stop'},
    {'name': 'server3', 'state': 'suspend'},
    {'name': 'server4', 'state': 'pause'},
    {'name': 'server5', 'state': 'resize'},
    {'name': 'server6', 'state': 'active'},
    {'name': 'server7', 'state': 'shutoff'},
    {'name': 'server8', 'state': 'active'},
    {'name': 'tn1server1', 'state': 'active'},
    {'name': 'tn1server2', 'state': 'active'},
    {'name': 'tn2server1', 'state': 'active'},
    {'name': 'tn4server1', 'state': 'active'}
]
"""Emulate different VM states"""

NOVA_CLIENT_VERSION = '1.1'
GLANCE_CLIENT_VERSION = '1'
NEUTRON_CLIENT_VERSION = '2.0'
CINDER_CLIENT_VERSION = '1'
"""Client's versions"""

keypairs = [
    {'name': 'key1', 'user': 'user1', 'public_key':
        'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCn4vaa1MvLLIQM9G2i9eo2OWoW66i7'
        '/tz+F+sSBxjiscmXMGSUxZN1a0yK4TO2l71/MenfAsHCSgu75vyno62JTOLo+QKG07ly'
        '8vx9RF+mp+bP/6g0nhcgndOD30NPLEv3vtZbZRDiYeb3inc/ZmAy8kLoRPXE3sW4v+xq'
        '+PB2nqu38DUemKU9WlZ9F5Fbhz7aVFDhBjvFNDw7w5nO7zeAFz2RbajJksQlHP62VmkW'
        'mTgu/otEuhM8GcjZIXlfHJtv0utMNfqQsNQ8qzt38OKXn/k2czmZX59DXomwdo3DUSmk'
        'SHym3kZtZPSTgT6GIGoWA1+QHlhx5kiMVEN+YRZF vagrant'},
    {'name': 'key2', 'user': 'user2', 'public_key':
        'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDtvUaRYdwzIBL+CpSayYfbeTtnZNps'
        'e/Fx1FAMX7DQBBD7aghNkbQMjVrdGpI7hOSJsU11Gmhl4/B3LFTu8oTUZNfz8nM+g0fT'
        'iZVICtvQUnB89xnH3RNYDBGFQKS3gOUtjvOb0oP9RVNELHftrGMnjJOQCLF+R0eG+Byc'
        '9DZy3PfajJftUZsgCyzIkVT7YBZVQ7VubB3jOGZqXCpMfLFZtZad2+G+C3sYm3rMGu8l'
        'b+wS90o98IrpF4av6y13cfkqkucw3sJ18+wzPbWKQ41YW9QyZ6Er0Vu4+4pJcj+1qn+O'
        'kINp0A7C2WbXXgiyeaxBR8nBV9A01cFm/W6Q63/r vagrant@grizzly'},
    {'name': 'key3', 'user': 'user7', 'public_key':
        'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDVIFUSSlxG8vPj11aLXZderymbR5G2e'
        'uoxPaZSZ33DUtGurPBnBhS3ztnR3Cg4vBgpoTVyti7LYenhfBlcGyjxA+RA2iM8Q3YYrX'
        'AL64Itad/IzPfq6+qpSErqkU/tLzoWasFJBXuex8FSWg7lYbZX4CJZkSsEGiNqSdNw4lS'
        'pdWfvGbMh6ywyGAMxNRHi7JyaFoMATLqHYy/w+9EHkNqKaFtICw5RhNG6zEGCAnHuRz+g'
        'nvvEOaVHY7En0PlSL2tqAmT7a8m98T8zS1w1uNeed4WXI8gWofOFlzyB5e1l5v/e4ANwg'
        '9jlzyyPa4i+rAfBSyg1wR02cRnEgejvPzrn user7@grizzly'},
    {'name': 'key4', 'user': 'user8', 'public_key':
        'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDVIFUSSlxG8vPj11aLXZderymbR5G2e'
        'uoxPaZSZ33DUtGurPBnBhS3ztnR3Cg4vBgpoTVyti7LYenhfBlcGyjxA+RA2iM8Q3YYrX'
        'AL64Itad/IzPfq6+qpSErqkU/tLzoWasFJBXuex8FSWg7lYbZX4CJZkSsEGiNqSdNw4lS'
        'pdWfvGbMh6ywyGAMxNRHi7JyaFoMATLqHYy/w+9EHkNqKaFtICw5RhNG6zEGCAnHuRz+g'
        'nvvEOaVHY7En0PlSL2tqAmT7a8m98T8zS1w1uNeed4WXI8gWofOFlzyB5e1l5v/e4ANwg'
        '9jlzyyPa4i+rAfBSyg1wR02cRnEgejvPzrn user8@grizzly'}]
"""Keypairs to create/delete, connected to user's list"""

private_key = {
    'name': 'key2',
    'id_rsa': '-----BEGIN RSA PRIVATE KEY-----\n'
    'MIIEowIBAAKCAQEA7b1GkWHcMyAS/gqUmsmH23k7Z2TabHvxcdRQDF+w0AQQ+2oI\n'
    'TZG0DI1a3RqSO4TkibFNdRpoZePwdyxU7vKE1GTX8/JzPoNH04mVSArb0FJwfPcZ\n'
    'x90TWAwRhUCkt4DlLY7zm9KD/UVTRCx37axjJ4yTkAixfkdHhvgcnPQ2ctz32oyX\n'
    '7VGbIAssyJFU+2AWVUO1bmwd4zhmalwqTHyxWbWWndvhvgt7GJt6zBrvJW/sEvdK\n'
    'PfCK6ReGr+std3H5KpLnMN7CdfPsMz21ikONWFvUMmehK9FbuPuKSXI/tap/jpCD\n'
    'adAOwtlm114IsnmsQUfJwVfQNNXBZv1ukOt/6wIDAQABAoIBABVJWUQzKvA48vpk\n'
    'ICIr4Uo5dKQxV41XG6tBg1lYSBCYDJ02RUAMx75H+dbKRkWmBIB/q5vMnYRiAGnr\n'
    'Qj+S32nVDbD+CGuUfZ3nN8KXlk700rWdumU22kCL9BWmUBlOJTcLEazmEINg7a+w\n'
    '+5wAT3B/GcdPv/S6lSD0njs/cpCeJDUzxQyxxg4pookNHlGZOgfyyI++qFfq9ijf\n'
    '4I5fbCxk/sxClEHziWkp0HM6RvXa0UnmpoZzfvfc8QpvbHmVxiIjnV289fkJgOKS\n'
    'yhqaxC8+wI25RKo12EAxPXCpDdG0mXqq4lhKf2igN8Dvd2vAXR+yXLUSLDP062Tn\n'
    'lE1wAgECgYEA+E9k8PQ48RZqvzkp6rbXVMYC20kpZ4c+l1j4ibEr1VCvO1L0sENq\n'
    'NY+XEYbvSXgxPQd8XhGf6OBimnuzBZjwBdGEAlwYWlE3e7O2zKFUMVBogUt/WACA\n'
    '37V2HUNrQOsCm5Yui6HI+xEMLNjG5zoFNvTI9QINUcHG9fXnX26ifKsCgYEA9RoT\n'
    'fF+VJDHGye5ZqBlGzx6pW94YpxCeoE658gC0ZChih+lLVkbPiyHrCZh3HNvCpcPC\n'
    'zON1N50KZB3cwyKkKn7ZhEU60JXWtLoAKWqOCcBGZbpUM2Dz45TRyccYr8tsPr7H\n'
    'qR1/rGzjX0nWHJ5VAkv+jTl+cOtq9kpkArMcicECgYEA9YhsY+bat2pXO6cmz7Tk\n'
    '0CrMgFGj439UYQvVFzJeCZyy6ZJp6jF/QF8wHmCzFI8JATP5wnrjCL94QRG4P/yu\n'
    'utImGr8+RXCx0Fwwkb+lJO5BqDgjP72fsZYZqW4VDChWd8rVU7UyqzB8PYxNgi9Z\n'
    'ILKEU+EnkoRuXKA/nZokiekCgYBH7Anxwh6Ci3S4xo9ai2hC2M17nrV/OJpDkjZw\n'
    'NBK7HTqkhSnNPGQkgKR2oV26gyYf/EzKUKiR1Cw7aqPgQucHbUeoz6PNl1p0l+v6\n'
    'O0FIzTobGc0hcn6+tmnFGv48f6XY16TBFF3lm+IwkPsaVL+/N8uPZ2KaAgrWEMg+\n'
    'Ho7uQQKBgGF85KSoTDe/uuVamEekgDSLS3xaxVz2zXGoSw1cyhBianAa51jWA0aS\n'
    '+R47D8BX8SD1QzBUXen8poGvfGcD6DhHyPdGdDxGcY64mOn8XkjX4jFWcgmgfvzv\n'
    '3tIflPBFw1Nege/HoFITiWU9wwukMxXaYMWO4TKGol1OZ27Q26Qt\n'
    '-----END RSA PRIVATE KEY-----'}

dst_prv_key_path = '~/.ssh/id_rsa'

rollback_params = {'data_file_names': {'PRE': 'data_before_migration.yaml',
                                       'POST': 'data_after_migration.yaml'},

                   'param_dict': {'Nova': ['servers', 'security_groups',
                                           'flavors', 'keypairs', 'quotas'],
                                  'Neutron': ['networks', 'routers', 'subnets',
                                              'ports', 'quotas'],
                                  'Keystone': ['users', 'tenants', 'roles'],
                                  'Glance': ['images', 'members'],
                                  'Cinder': ['volume_snapshots', 'volumes',
                                             'quotas']}}
"""Parameters required for rollback verification procedure"""
