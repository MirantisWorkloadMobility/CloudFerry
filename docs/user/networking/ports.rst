=======================
Ports migration process
=======================

CloudFerry allows migration of neutron ports as independent step if all the
dependencies (neutron networks and keystone tenants) already exist in
destination.

CloudFerry supports both attached (VM's ports) and detached port
(standalone) migration. Detached port migration can be useful in cases when
neutron ports are used as load balancers.
