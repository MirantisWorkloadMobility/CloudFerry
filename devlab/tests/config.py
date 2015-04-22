# Users to create
users = [
    {'name': 'user1', 'pass': 'passwd1', 'email': 'mail@example.com',
     'tenant': 'tenant1', 'enabled': True},
    {'name': 'user2', 'pass': 'passwd2', 'email': 'aa@example.com',
     'tenant': 'tenant1', 'enabled': True}
]

# Tenants to create
tenants = [
    {'name': 'tenant1', 'description': 'None', 'enabled': True}
]

quotas = [
    {'instances': '9', 'cores': '19', 'ram': '52199', 'floating_ips': '9',
     'fixed_ips': '', 'metadata_items': '', 'injected_files': '',
     'injected_file_content_bytes': '', 'injected_file_path_bytes': '',
     'key_pairs': '5', 'security_groups': '9', 'security_group_rules': ''}
]

# Keypairs to create
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

# Images to create
images = [
    {'name': 'image1', 'copy_from': 'http://download.cirros-cloud.net/0.3.3/ci'
                                    'rros-0.3.3-x86_64-disk.img'},
    {'name': 'image2', 'copy_from': 'http://download.cirros-cloud.net/0.3.3/ci'
                                    'rros-0.3.3-x86_64-disk.img',
     'container_format': 'bare', 'disk_format': 'qcow2'}
]

# Flavors to create
flavors = [
    {'name': 'flavorname1', 'disk': '10', 'ram': '32', 'vcpus': '1'},
    {'name': 'flavorname2', 'disk': '5', 'ram': '64', 'vcpus': '2'}
]

# Networks to create
networks = [
    {'name': 'mynetwork1', 'admin_state_up': True}

]

# Subnets to create
subnets = [
    {'cidr': '10.4.2.0/24', 'ip_version': 4}
]

# VM's to create
vms = [
    {'name': 'server1', 'image': 'image1', 'flavor': 'flavorname1'},
    {'name': 'server2', 'image': 'image2', 'flavor': 'flavorname1'},
    {'name': 'server3', 'image': 'image1', 'flavor': 'flavorname2'},
    {'name': 'server4', 'image': 'image2', 'flavor': 'flavorname2'},
    {'name': 'server5', 'image': 'image1', 'flavor': 'flavorname1'}
]

# Snapshots to create
snapshots = [
    {'server': 'server2', 'image_name': 'asdasd'}
]

# Client's versions
NOVA_CLIENT_VERSION = '1.1'
GLANCE_CLIENT_VERSION = '1'
NEUTRON_CLIENT_VERSION = '2.0'
