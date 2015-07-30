CloudFerry
==========

# Overview

CloudFerry is a tool for resources and workloads migration between OpenStack clouds. First of all CloudFerry tool
migrates cloud resources as tenants, users (preserving their passwords or generating new ones), roles, flavors and after
that, it transfers virtual workloads as instances with their own data (instance
image, root disk data, ephemeral drives, attached volumes) and network settings.


CloudFerry was tested on Openstack releases from Grizzly to Ice-House.
It supports migration process for clouds using any iSCSI-like mechanism for volumes or Ceph as a backend for
Cinder&Glance services, including case with Nova - Ephemeral volumes in Ceph.
Supported cases are listed below. Tool supports any iscsi-like mechanism for Cinder backend as for Cinder service with
LVM backend:


- 1) Source - Cinder (LVM), Glance (file) --> Destination - Cinder (LVM), Glance (file)
- 2) Source - Cinder & Glance (Ceph) --> Destination - Cinder (LVM), Glance (file)
- 3) Source - Cinder & Glance (Ceph) and Nova ephemeral volumes (Ceph) -->   Destination - Cinder (LVM), Glance (file)
- 4) Source - Cinder (LVM), Glance (file) --> Destination - Cinder & Glance (Ceph)
- 5) Source - Cinder (LVM), Glance (file) --> Destination - Cinder & Glance (Ceph) and Nova ephemeral volumes (Ceph)
- 6) Source - Cinder & Glance (Ceph) --> Destination - Cinder & Glance (Ceph)
- 7) Source - Cinder & Glance (Ceph) and Nova ephemeral volumes (Ceph) -->   Destination - Cinder & Glance (Ceph) and
Nova ephemeral volumes (Ceph)


Also CloudFerry can migrate instances, which were booted from bootable  volumes with the same storage backends as in
previous listed cases.


CloudFerry uses External network as a transfer network, so you need to have a connectivity from host where you want
to execute the tool (transition zone) to both clouds through external network.
CloudFerry can migrate instances from clouds with nova-network or quantum/neutron to new cloud with neutron network
service. Also the tool can transfer instances in to the fixed networks with the same CIDR (they will be found
automatically) or list new networks for instances in config.yaml file in overwrite section.


Cloudferry also allow keep ip addresses of instances and transfer security groups (with rules) with automatic detection
of network manager on source and destination clouds (quantum/neutron or nova).


All functions are configured in yaml file, you can see the examples in configs directory.
At the moment config file does not support default values so you need to set up all settings manually. Please note,
that if any valuable setting appeared to be missing in config file, process will crash. Default settings is planned
to implement in nearest future.


# Requirements

 - Connection to source and destination clouds through external(public) network from host with CloudFerry.
 - Valid private ssh-key for both clouds which will be using by CloudFerry for data transferring.
 - Admin keystone access (typically admin access point lives on 35357 port).
 - sudo/root access on compute and controller nodes.
 - Openstack MySQL DB write access.
 - Credentials of global cloud admin for both clouds.
 - All the Python requirements are listed in requirements.txt.


# Installation

Currently the tool is not packaged in any manner, so the installation is based on simply cloning git repo
and installing all the requirements into python virtualenv:
```
# there are several requirements for the python libraries used in CloudFerry
# which are not installed on ubuntu by default
sudo apt-get install python-virtualenv python-dev libffi-dev -y

git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git
cd CloudFerry
virtualenv .venv
source .venv/bin/activate

# for some reason fabric has dependency resolution problems with pip>=7.0.0
pip install pip==6.1.1
pip install --allow-all-external -r requirements.txt
pip install -r test-requirements.txt
```

# Usage

## Overview
CloudFerry tool is used by running python fabric scripts from the CloudFerry repo directory:
```
cd CloudFerry
# see list of available commands
fab list
```

## Configuration

Configuration can be done through reusing of `devlab/config.template` and `devlab/provision/generate_config.sh`.
Configuration process is quite complex and mostly manual try-and-see-if-works process. Configuration documentation
is TBD.

## Whole cloud migration
Use `migrate` fabric command with config file specified:

```
fab migrate:<config file>
```

## Migrating specific instances

In order to migrate specific VMs, one should use filters. This is done through modifying filters file
(`configs/filter.yaml` by default).

Edit `configs/filter.yaml`:
```
instances:
    id:
        - 7c53a6ab-0149-4232-80b3-b2d7ce02995a
        - f0fea76a-0a7d-4c25-ab9e-f048dbc7365d
```

Run migration as usual:
```
fab migrate:<configuration file>
```


# Versions

## 1.0 - Full devlab environment migration

See `devlab/tests/generate_load.py` for the load migrated.

See `devlab/README.md` for test environment description.

 - Successful tenants migration
 - Successful users migration
 - Successful roles migration
 - Successful keypairs migration
     * User's
     * Admin's
 - Successful quotas migration
     * Quotas for all tenants
     * Tenant's quotas
 - Successful flavors migration
 - Successful images migration
 - Successful volumes migration
     * User's
     * Admin's
 - Successful security groups migration
     * User's
     * Admin's
 - Successful networks migration
     * Tenant's
     * External
 - Successful subnets migration
 - Successful routers migration
 - Successful floating-ips migration
     * Associated with VM's
     * Allocated in tenants
 - Successful VMs migration
     * Admin's
     * User's

