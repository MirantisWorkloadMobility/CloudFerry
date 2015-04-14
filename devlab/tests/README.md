Directory with tests for Cloudferry's devlab
==========

## Prerequisite action

Prepare small tenant:
- vms
- networks
- subnets
- users
- keypairs
- tenants
- modifies tenants quotas
- upload images and snapshot
- creates flavors
- creates volumes

## Usage

Modify config.py if you'll need additional amount of OS objects described above.
```
vim devlab/tests/config.py
```

Export all needed environment variables, for example:
```
export OS_TENANT_NAME=admin
export OS_USERNAME=admin
export OS_PASSWORD=admin
export OS_AUTH_URL="http://192.168.1.2:5000/v2.0/"
export OS_IMAGE_ENDPOINT="http://192.168.1.2:9292"
export OS_NEUTRON_ENDPOINT="http://192.168.1.2:9696/" 
```

Prepare the same virtualenv as for Cloudferry and run:
```
python prerequisite_actions.py
```
