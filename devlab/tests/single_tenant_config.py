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

# Tenants to create/delete
tenants = [
    {'name': 'tenant1', 'description': 'None', 'enabled': True,
     'quota': {'instances': '9', 'cores': '19', 'ram': '52199',
               'floating_ips': '9', 'fixed_ips': '', 'metadata_items': '',
               'injected_files': '', 'injected_file_content_bytes': '',
               'injected_file_path_bytes': '', 'key_pairs': '5',
               'security_groups': '9', 'security_group_rules': ''},
     'vms': [
         {'name': 'tn1server1', 'image': 'image1', 'flavor': 'flavorname2',
          'key_name': 'key1'},
         {'name': 'tn1server2', 'image': 'image1', 'flavor': 'flavorname1'},
         {'name': 'server6', 'image': 'image1', 'flavor': 'del_flvr'}],
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
         {'name': 'sg12', 'description': 'Blah blah group2'}],
     'cinder_volumes': [
         {'name': 'cinder_volume1', 'size': 1, 'device': '/dev/vdb',
          'server_to_attach': 'tn1server1'},
         {'name': 'cinder_volume2', 'size': 1}
     ],
     'cinder_snapshots': [
         # Commented because of unimplemented error in nfs driver for grizzly.
         # {'name': 'tn1snapsh', 'volume_id': 'tn1_volume2'}
     ]
     }
]

# Images to create/delete
img_url = 'http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img'
images = [
    {'name': 'image1', 'copy_from': img_url, 'is_public': True},
    {'name': 'image3', 'copy_from': img_url, 'container_format': 'bare',
     'disk_format': 'qcow2', 'is_public': False},
    {'name': 'image4', 'copy_from': img_url, 'container_format': 'bare',
     'disk_format': 'qcow2', 'is_public': False}
]

# Images not to be migrated:
images_not_included_in_filter = []

# Instances not to be included in filter:
vms_not_in_filter = ['not_in_filter']

# Images that should have few specific members:
members = ['tenant1', 'admin']
img_to_add_members = ['image3', 'image4']

# Flavors to create/delete
flavors = [
    {'name': 'flavorname1', 'disk': '1', 'ram': '64', 'vcpus': '1'},
    # Disabled for now, but in the future we need to generate non-pubic flavors
    # {'name': 'flavorname3', 'disk': '10', 'ram': '32', 'vcpus': '1',
    #  'is_public': False},
    {'name': 'flavorname2', 'disk': '2', 'ram': '48', 'vcpus': '2'},
    {'name': 'del_flvr', 'disk': '1', 'ram': '64', 'vcpus': '1'}
]

# Networks to create/delete
# Connected to tenants
networks = [
    {'name': 'tenantnet1', 'admin_state_up': True, 'shared': False,
     'router:external': False},
    {'name': 'shared_net', 'admin_state_up': True, 'shared': True,
     'router:external': True}

]

# Subnets to create/delete
subnets = [
    {'cidr': '10.5.2.0/24', 'ip_version': 4},
    {'cidr': '172.18.10.0/24', 'ip_version': 4, 'name': 'subnet_2'}
]

# VM's to create/delete
vms = [

]

routers = [

]

# VM's snapshots to create/delete
snapshots = [
    {'server': 'server2', 'image_name': 'asdasd'}
]

# Cinder images to create/delete
cinder_volumes = [
    {'name': 'cinder_volume3', 'size': 1, 'user': 'test_volume_migration'},
    {'name': 'tn1_volume1', 'size': 1},
    {'name': 'tn1_volume2', 'size': 1},
]

# Cinder snapshots to create/delete
cinder_snapshots = [
    # Commented because of unimplemented error in nfs driver for grizzly.
    # {'display_name': 'snapsh1', 'volume_id': 'cinder_volume1'}
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
        'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDtvUaRYdwzIBL+CpSayYfbeTtnZNps'
        'e/Fx1FAMX7DQBBD7aghNkbQMjVrdGpI7hOSJsU11Gmhl4/B3LFTu8oTUZNfz8nM+g0fT'
        'iZVICtvQUnB89xnH3RNYDBGFQKS3gOUtjvOb0oP9RVNELHftrGMnjJOQCLF+R0eG+Byc'
        '9DZy3PfajJftUZsgCyzIkVT7YBZVQ7VubB3jOGZqXCpMfLFZtZad2+G+C3sYm3rMGu8l'
        'b+wS90o98IrpF4av6y13cfkqkucw3sJ18+wzPbWKQ41YW9QyZ6Er0Vu4+4pJcj+1qn+O'
        'kINp0A7C2WbXXgiyeaxBR8nBV9A01cFm/W6Q63/r vagrant@grizzly'}]

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
