# Users to create/delete
users = [
    {'name': 'user1', 'password': 'passwd1', 'email': 'mail@example.com',
     'tenant': 'tenant1', 'enabled': True},
    {'name': 'user3', 'password': 'paafdssswd1', 'email': 'mdsail@example.com',
     'tenant': 'tenant1', 'enabled': False}
]

# Roles to create/delete
roles = [
    {'name': 'SomeRole'}
]

# Keypairs to create/delete
# Connected to user's list
keypairs = [
    {'name': 'key1', 'public_key':
        'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCn4vaa1MvLLIQM9G2i9eo2OWoW66i7'
        '/tz+F+sSBxjiscmXMGSUxZN1a0yK4TO2l71/MenfAsHCSgu75vyno62JTOLo+QKG07ly'
        '8vx9RF+mp+bP/6g0nhcgndOD30NPLEv3vtZbZRDiYeb3inc/ZmAy8kLoRPXE3sW4v+xq'
        '+PB2nqu38DUemKU9WlZ9F5Fbhz7aVFDhBjvFNDw7w5nO7zeAFz2RbajJksQlHP62VmkW'
        'mTgu/otEuhM8GcjZIXlfHJtv0utMNfqQsNQ8qzt38OKXn/k2czmZX59DXomwdo3DUSmk'
        'SHym3kZtZPSTgT6GIGoWA1+QHlhx5kiMVEN+YRZF vagrant'},
    {'name': 'key2', 'public_key':
        'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCn4vaa1MvLLIQM9G2i9eo2OWoW66i7'
        '/tz+F+sSBxjiscmXMGSUxZN1a0yK4TO2l71/MenfAsHCSgu75vyno62JTOLo+QKG07ly'
        '8vx9RF+mp+bP/6g0nhcgndOD30NPLEv3vtZbZRDiYeb3inc/ZmAy8kLoRPXE3sW4v+xq'
        '+PB2nqu38DUemKU9WlZ9F5Fbhz7aVFDhBjvFNDw7w5nO7zeAFz2RbajJksQlHP62VmkW'
        'mTgu/otEuhM8GcjZIXlfHJtv0utMNfqQsNQ8qzt38OKXn/k2czmZX59DXomwdo3DUSmk'
        'SHym3kZtZPSTgT6GIGoWA1+QHlhx5kiMVEN+YRZF vagrant'}
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
    {'name': 'm1.tiny'}
    # {'name': 'flavorname1', 'disk': '7', 'ram': '64', 'vcpus': '1'},
    # Disabled for now, but in the future we need to generate non-pubic flavors
    # {'name': 'flavorname3', 'disk': '10', 'ram': '32', 'vcpus': '1',
    #  'is_public': False},
    # {'name': 'flavorname2', 'disk': '5', 'ram': '48', 'vcpus': '2'}
]

# Security groups to create/delete
security_groups = [{'security_groups': [
    {'name': 'sg11',
     'description': 'Blah blah group',
     'rules': [{'ip_protocol': 'icmp',
                'from_port': '0',
                'to_port': '255',
                'cidr': '0.0.0.0/0'},
               {'ip_protocol': 'tcp',
                'from_port': '80',
                'to_port': '80',
                'cidr': '0.0.0.0/0'}]},
    {'name': 'sg12',
     'description': 'Blah blah group2'}]}]


# Networks to create/delete
# Connected to tenants
ext_net = {'name': 'shared_net', 'admin_state_up': True, 'shared': True,
           'router:external': True}

networks = [
    {'name': 'mynetwork1', 'admin_state_up': True},
]

# Subnets to create/delete
ext_subnet = {'cidr': '172.18.10.0/24', 'ip_version': 4}

subnets = [
    {'cidr': '10.4.2.0/24', 'ip_version': 4},
]

# VM's to create/delete
vms = [
    {'name': 'server1', 'image': 'image1', 'flavor': 'm1.tiny'},
    {'name': 'server2', 'image': 'image2', 'flavor': 'm1.tiny'},
    {'name': 'server3', 'image': 'image1', 'flavor': 'm1.tiny'},
    {'name': 'server4', 'image': 'image2', 'flavor': 'm1.tiny'},
    {'name': 'server5', 'image': 'image1', 'flavor': 'm1.tiny'},
    {'name': 'server6', 'image': 'image1', 'flavor': 'm1.tiny'}
]

routers = [
    {
        'router': {
            'name': 'ext_router',
            'external_gateway_info': {
                'network_id': 'shared_net'},
            'admin_state_up': True}}
]

# VM's snapshots to create/delete
snapshots = [
    {'server': 'server2', 'image_name': 'asdasd'}
]

# Cinder images to create/delete
cinder_volumes = [
    {'name': 'cinder_volume1', 'size': 1},
    {'name': 'cinder_volume2', 'size': 1,
     'server_to_attach': 'server2', 'device': '/dev/vdb'}
]

# Cinder snapshots to create/delete
cinder_snapshots = [
    {'display_name': 'snapsh1', 'volume_id': 'cinder_volume1'}
]

# Emulate different VM states
vm_states = [
    {'name': 'server1', 'state': 'error'},
    {'name': 'server2', 'state': 'stop'},
    {'name': 'server3', 'state': 'suspend'},
    {'name': 'server4', 'state': 'pause'},
    {'name': 'server5', 'state': 'resize'}
]

# Client's versions
NOVA_CLIENT_VERSION = '1.1'
GLANCE_CLIENT_VERSION = '1'
NEUTRON_CLIENT_VERSION = '2.0'
CINDER_CLIENT_VERSION = '1'
