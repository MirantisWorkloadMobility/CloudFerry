=========================
Routers migration process
=========================

Private tenant routers migration
--------------------------------

Private router migration (routers which only connect private tenant
networks) is dead simple:

 - Read router list from source clond;
 - Create routers using neutron APIs in destination cloud.


External router migration
-------------------------

External routers are more tricky, because they can be shared between tenants.
Thus the process for external router migration is as follows:

 - Get router list from source cloud;
 - If tenant's network is routed through a router belonging to a different
   tenant - this tenant is added to the list of tenants, which need to be
   migrated and is migrated prior to router migration;
 - If router is connected to external network which belongs to a different
   tenant - this tenant is added to the list of tenants which need to be
   migrated and is migrated prior to router migration;
 - When all dependencies are available in destination router is created
   using neutron APIs.
