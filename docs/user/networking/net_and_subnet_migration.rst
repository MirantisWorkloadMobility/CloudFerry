.. _network-and-subnet-migration:

==============================
Networks and subnets migration
==============================

Since networks have virtually no value without subnets, these two objects
are treated as a single object during migration.

Following attributes are kept during migration of networks and subnets:

 - Network attributes:
     - Tenant. If tenant does not exist in destination - network is skipped;
     - Network name;
     - Admin state (UP or DOWN);
     - Shared or not shared;
     - Private or external;
     - Network type (flat, VLAN, GRE, VXLAN, etc). If source cloud network
       type is not supported in destination cloud - migration does not start.
     - Segmentation ID, if available in destination. Otherwise neutron
       allocates new segmentation ID;
 - Subnet attributes:
     - Subnet name;
     - DHCP status (enabled or not);
     - CIDR;
     - Allocation pools;
     - IP version;

Shared private networks
-----------------------

Shared networks are accessible from all tenants, so they will be migrated
regardless of :ref:`filtering rules <filter-configuration>`.
