# Users to create/delete
users = [
    {'name': 'user1', 'pass': 'passwd1', 'email': 'mail@example.com',
     'tenant': 'tenant1', 'enabled': True},
    {'name': 'user2', 'pass': 'passwd2', 'email': 'aa@example.com',
     'tenant': 'tenant2', 'enabled': True},
    {'name': 'user3', 'pass': 'paafdssswd1', 'email': 'mdsail@example.com',
     'tenant': 'tenant1', 'enabled': False},
    {'name': 'user4', 'pass': 'asaasdf', 'email': 'asdasd@example.com',
     'tenant': 'tenant2', 'enabled': False}
]

# Tenants to create/delete
tenants = [
    {'name': 'tenant1', 'description': 'None', 'enabled': True,
     'quota': {'instances': '9', 'cores': '19', 'ram': '52199',
               'floating_ips': '9', 'fixed_ips': '', 'metadata_items': '',
               'injected_files': '', 'injected_file_content_bytes': '',
               'injected_file_path_bytes': '', 'key_pairs': '5',
               'security_groups': '9', 'security_group_rules': ''},
     'vms': [
         {'name': 'tn1server1', 'image': 'image1', 'flavor': 'flavorname2'},
         {'name': 'tn1server2', 'image': 'image1', 'flavor': 'flavorname1'}],
     'networks': [{'name': 'tenantnet1', 'admin_state_up': True}],
     'subnets': [{'cidr': '10.5.2.0/24', 'ip_version': 4}],
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
         {'name': 'sg12', 'description': 'Blah blah group2'}]
     },
    {'name': 'tenant2', 'description': 'Bljakslhf ajsdfh', 'enabled': True,
     'vms': [
         {'name': 'tn2server1', 'image': 'image1', 'flavor': 'flavorname2'}],
     'networks': [{'name': 'tenantnet2', 'admin_state_up': True}],
     'subnets': [{'cidr': '22.2.2.0/24', 'ip_version': 4}]
     }
]

# Keypairs to create/delete
# Connected to user's list
keypairs = [
    {'name': 'key1', 'pub': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCn4vaa1MvLL'
                            'IQM9G2i9eo2OWoW66i7/tz+F+sSBxjiscmXMGSUxZN1a0yK4T'
                            'O2l71/MenfAsHCSgu75vyno62JTOLo+QKG07ly8vx9RF+mp+b'
                            'P/6g0nhcgndOD30NPLEv3vtZbZRDiYeb3inc/ZmAy8kLoRPXE'
                            '3sW4v+xq+PB2nqu38DUemKU9WlZ9F5Fbhz7aVFDhBjvFNDw7w'
                            '5nO7zeAFz2RbajJksQlHP62VmkWmTgu/otEuhM8GcjZIXlfHJ'
                            'tv0utMNfqQsNQ8qzt38OKXn/k2czmZX59DXomwdo3DUSmkSHy'
                            'm3kZtZPSTgT6GIGoWA1+QHlhx5kiMVEN+YRZF vagrant'},
    {'name': 'key2', 'pub': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCn4vaa1MvLL'
                            'IQM9G2i9eo2OWoW66i7/tz+F+sSBxjiscmXMGSUxZN1a0yK4T'
                            'O2l71/MenfAsHCSgu75vyno62JTOLo+QKG07ly8vx9RF+mp+b'
                            'P/6g0nhcgndOD30NPLEv3vtZbZRDiYeb3inc/ZmAy8kLoRPXE'
                            '3sW4v+xq+PB2nqu38DUemKU9WlZ9F5Fbhz7aVFDhBjvFNDw7w'
                            '5nO7zeAFz2RbajJksQlHP62VmkWmTgu/otEuhM8GcjZIXlfHJ'
                            'tv0utMNfqQsNQ8qzt38OKXn/k2czmZX59DXomwdo3DUSmkSHy'
                            'm3kZtZPSTgT6GIGoWA1+QHlhx5kiMVEN+YRZF vagrant'}
]

# Images to create/delete
images = [
    {'name': 'image1', 'copy_from': 'http://download.cirros-cloud.net/0.3.3/ci'
                                    'rros-0.3.3-x86_64-disk.img',
     'is_public': True},
    {'name': 'image2', 'copy_from': 'http://download.cirros-cloud.net/0.3.3/ci'
                                    'rros-0.3.3-x86_64-disk.img',
     'container_format': 'bare', 'disk_format': 'qcow2', 'is_public': False}
]

# Flavors to create/delete
flavors = [
    {'name': 'flavorname1', 'disk': '10', 'ram': '32', 'vcpus': '1'},
    {'name': 'flavorname2', 'disk': '5', 'ram': '64', 'vcpus': '2'}
]

# Networks to create/delete
# Connected to tenants
networks = [
    {'name': 'mynetwork1', 'admin_state_up': True},
    {'name': 'shared_net', 'admin_state_up': True, 'shared': True,
     'router:external': True}

]

# Subnets to create/delete
subnets = [
    {'cidr': '10.4.2.0/24', 'ip_version': 4},
    {'cidr': '172.18.10.0/24', 'ip_version': 4}
]

# VM's to create/delete
vms = [
    {'name': 'server1', 'image': 'image1', 'flavor': 'flavorname1'},
    {'name': 'server2', 'image': 'image2', 'flavor': 'flavorname1'},
    {'name': 'server3', 'image': 'image1', 'flavor': 'flavorname2'},
    {'name': 'server4', 'image': 'image2', 'flavor': 'flavorname2'},
    {'name': 'server5', 'image': 'image1', 'flavor': 'flavorname1'}
]

routers = [
    {
        'router': {
            'external_gateway_info': {
                'network_id': 'shared_net'},
            'name': 'ext_router',
            'admin_state_up': True}}
]

# Snapshots to create/delete
snapshots = [
    {'server': 'server2', 'image_name': 'asdasd'}
]

# Client's versions
NOVA_CLIENT_VERSION = '1.1'
GLANCE_CLIENT_VERSION = '1'
NEUTRON_CLIENT_VERSION = '2.0'
