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

Prepare virtual environment to run tests and scripts. You can use the same
venv as prepared for cloudferry with same requirements and test-requirements
installed.
Modify config.py if you'll need additional amount of OS objects described above.
```
vim devlab/tests/config.py
```

Export all needed environment variables, for example:
```
export SRC_OS_TENANT_NAME=admin
export SRC_OS_USERNAME=admin
export SRC_OS_PASSWORD=admin
export SRC_OS_AUTH_URL="http://192.168.1.2:5000/v2.0/"
export SRC_OS_IMAGE_ENDPOINT="http://192.168.1.2:9292"
export SRC_OS_NEUTRON_ENDPOINT="http://192.168.1.2:9696/"
```

Prepare the same virtualenv as for Cloudferry and run to create Openstack 
objects on source cloud:
```
cd devlab/tests
python generate_load.py
```

To execute tests run:
```
cd devlab/tests
nosetests -v
```