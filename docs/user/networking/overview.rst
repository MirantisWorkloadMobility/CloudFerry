==========================
Network migration overview
==========================

Network migration is perhaps the most complicated part of migration process.
Primarily because there is a need to determine whether networking object
(network, subnet, port, router) already exists in destination cloud or not.

Since networking migration may introduce a lot of problems, there is a
mandatory preliminary check which detects all the potential conflicts
between source and destination cloud, and is implemented in ``check_networks``
:ref:`action <scenario-files-config>`.

Following objects are supported as part of networking migration:

 - Networks
    - Private tenant networks
    - Shared networks
    - External networks
 - Subnets
 - Routers
 - Ports
 - Floating IPs
 - Security groups
 - Load balancer objects
    - Pools
    - Monitors
    - Members
    - VIPs
 - Neutron quotas
