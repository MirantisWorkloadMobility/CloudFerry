========
Overview
========

CloudFerry is a command-line tool which helps you move VMs, networks, images,
volumes, and other objects between two Openstack clouds. Here you’ll find user
documentation for the tool.


High-level Functionality Overview
---------------------------------

When configured correctly, CloudFerry allows to move following objects between
two Openstack clouds:

 - Identity
    - tenants
    - user roles
 - Images
    - glance images
 - Storage
    - cinder volumes
 - Networking
    - networks
    - subnets
    - security groups
    - ports
    - quotas
 - Compute
    - key pairs
    - flavors
    - VMs
    - VM’s ephemeral storage
    - quotas


General Migration Rules
-----------------------

 - Keep all the object’s metadata (such as object name, description, primary
   object attributes) whenever possible
 - If not possible – map metadata according to the rules defined in config
 - If not possible – print warning message and skip to the next object
