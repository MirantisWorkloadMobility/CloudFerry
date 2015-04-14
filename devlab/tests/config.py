# Users to create
users = [
    {'name': 'user111', 'pass': 'passwd1', 'email': 'mail@example.com', 'tenant': 'tenant1', 'enabled': True},
    {'name': 'user2', 'pass': 'passwd2', 'email': 'aa@example.com', 'tenant': 'tenant1', 'enabled': True}
]

# Tenants to create 
tenants = [
    {'name': 'tenant1', 'description': 'None', 'enabled': True}
]

quotas = [
    {'instances': '9', 'cores': '19', 'ram': '52199', 'floating_ips': '9', 'fixed_ips': '', 'metadata_items': '',
     'injected_files': '', 'injected_file_content_bytes': '', 'injected_file_path_bytes': '', 'key_pairs': '5',
     'security_groups': '9', 'security_group_rules': ''}
]

# Keypairs to create 
keypairs = [
    {'name': 'key1', 'pub': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCn4vaa1MvLLIQM9G2i9eo2OWoW66i7/tz+F+sSBxjiscmXMGSUx'
                            'ZN1a0yK4TO2l71/MenfAsHCSgu75vyno62JTOLo+QKG07ly8vx9RF+mp+bP/6g0nhcgndOD30NPLEv3vtZbZRDiYe'
                            'b3inc/ZmAy8kLoRPXE3sW4v+xq+PB2nqu38DUemKU9WlZ9F5Fbhz7aVFDhBjvFNDw7w5nO7zeAFz2RbajJksQlHP6'
                            '2VmkWmTgu/otEuhM8GcjZIXlfHJtv0utMNfqQsNQ8qzt38OKXn/k2czmZX59DXomwdo3DUSmkSHym3kZtZPSTgT6G'
                            'IGoWA1+QHlhx5kiMVEN+YRZF vagrant'},
    {'name': 'key2', 'pub': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCn4vaa1MvLLIQM9G2i9eo2OWoW66i7/tz+F+sSBxjiscmXMGSUx'
                            'ZN1a0yK4TO2l71/MenfAsHCSgu75vyno62JTOLo+QKG07ly8vx9RF+mp+bP/6g0nhcgndOD30NPLEv3vtZbZRDiYe'
                            'b3inc/ZmAy8kLoRPXE3sW4v+xq+PB2nqu38DUemKU9WlZ9F5Fbhz7aVFDhBjvFNDw7w5nO7zeAFz2RbajJksQlHP6'
                            '2VmkWmTgu/otEuhM8GcjZIXlfHJtv0utMNfqQsNQ8qzt38OKXn/k2czmZX59DXomwdo3DUSmkSHym3kZtZPSTgT6G'
                            'IGoWA1+QHlhx5kiMVEN+YRZF vagrant'}
]

# Images to create 
images = [
    {'name': 'image1', 'copy_from': 'http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img'},
    {'name': 'image2', 'copy_from': 'http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img'}
]

# Flavors to create 
flavors = [
    {'name': 'flavorname1', 'disk': '100', 'ram': '32', 'vcpus': '1'},
    {'name': 'flavorname2', 'disk': '50', 'ram': '64', 'vcpus': '2'}
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

