CloudFerry
==========

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
of network manager on source and destination clouds (neutron, quantum or nova).


All functions are configured in yaml file, you can see the examples in configs directory.
At the moment config file does not support default values so you need to set up all settings manually. Please note,
that if any valuable setting appeared to be missing in config file, process will crash. Default settings is planned
to implement in nearest future.


## Requirements


- Connection to source and destination clouds through external(public) network from host with CloudFerry.
- Valid private ssh-key for both clouds which will be using by CloudFerry for data transferring.
- Credentials of global cloud admin for both clouds.
- python-dev
- Fabric ver.>= 1.8.2
- python-novaclient
- python-cinderclient
- python-glanceclient
- python-keystoneclient
- python-neutronclient (python-quantumclient)*
- ipaddr
- sqlalchemy


\* If you know which network managers are used on your clouds you can install only f.e. python-neutronclient,
if you are not we recommend to install both packages.


## Usage


fab migrate:configs/config_iscsi_to_iscsi.yaml - to start process of migration:
        migrate - command for tool “to start migration process”
        configs/config_iscsi_to_iscsi.yaml - path to config file
fab migrate:configs/config_iscsi_to_iscsi.yaml,name_instance=<name_instance> - to start migration process of one given
instance with the name <name_instance>


Config description
(see file config_description.txt)