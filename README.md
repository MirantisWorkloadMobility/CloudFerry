CloudFerry
==========

# Overview

CloudFerry is a tool for resources and workloads migration between two 
OpenStack clouds. 


# Supported OpenStack Releases

 - Grizzly
 - Icehouse
 - Juno
 

# Objects Supported for Migration
 
## Keystone

 - Tenants
 - User roles

## Neutron

 - Networks
     * Private
     * Public
     * Shared
 - Subnets
 - Ports
 - Floating IPs
 - Security groups
 - Routers
 - LBaaS objects
 - Quotas

## Glance

 - Images
 
## Cinder

 - Volumes
 - Quotas

## Nova

 - VMs
 - VM's ephemeral storage
 - Flavors
 - User quotas
 - Tenant quotas
 - Key pairs

# User documentation

End-user documentation is available in `docs` folder, to compile in HTML run:

```
sphinx-build docs/ sphinx-build
```

# Requirements

 - Connection to source and destination clouds through external (public) 
   network from host with CloudFerry.
 - Valid private ssh-key for both clouds which will be using by CloudFerry for
   data transferring.
 - Admin keystone access (typically admin access point lives on 35357 port).
 - sudo/root access on compute and controller nodes.
 - Openstack MySQL DB write access.
 - Credentials of global cloud admin for both clouds.
 - All the Python requirements are listed in requirements.txt.


# Installation
Cloudferry can be prepared and installed as docker container.

## Building the docker container
```
docker build --build-arg cf_commit_or_branch=origin/master -t <username>/cf-in-docker .
```

## Container running
```
docker run -it <username>/cf-in-docker
```

## Saving and loading the container files
```
docker save --output=/path/to/save/CloudFerry.img <username>/cf-in-docker
docker load --input=/path/to/save/CloudFerry.img
```

# Usage

## Overview

CloudFerry tool is used by running python fabric scripts from the CloudFerry 
directory.

All available commands can be viewed with:
```
# see list of available commands
fab list
```

## Configuration

You can find sample configs in `configs/config.ini`

Configuration process is quite complex and mostly manual try-and-see-if-works
process.

## Whole cloud migration

Use `migrate` command with config file specified:

```
fab migrate:<config file>
```

## Migrating specific instances

In order to migrate specific VMs, one should use filters. This is done through
modifying filters file (`configs/filter.yaml` by default).

Edit `configs/filter.yaml`:

```
instances:
    id:
        - 7c53a6ab-0149-4232-80b3-b2d7ce02995a
        - f0fea76a-0a7d-4c25-ab9e-f048dbc7365d
```

Run migration as usual:
```
fab migrate:<config file>
```

## Playground

See QUICKSTART.md for the quickest way of running your first successful migration.
