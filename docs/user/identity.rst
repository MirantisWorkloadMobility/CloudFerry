==========================
Keystone objects migration
==========================

CloudFerry supports migration of following keystone objects:

 - tenants (projects);
 - user roles.

Keystone object migration is prerequisite for all the other objects, thus it
must be executed before any other stage.

Keystone object migration can be done with ``2_identity_transporter.yaml``
scenario.


Tenants (projects) migration
----------------------------

Tenant migration depends on:

 - :ref:`filtering rules <filter-configuration>`
 - tenants of shared objects, such as:
    - shared networks;
    - external networks;
    - public images;
    - `shared images <http://docs.openstack.org/openstack-ops/content/user_facing_images.html#sharing_images>`_;
    - public flavors;

In the most common case CloudFerry migrates tenant specified in
:ref:`filter config <filter-configuration>` plus all tenants of shared
objects, which may result in a lot of tenants migrated to the destination
cloud.

Tenant migration is a simple execution of keystone APIs:

 - Read all tenants to be migrated from source;
 - Create the same tenants in destination.


User roles migration
--------------------

CloudFerry supports migration of user roles and associates users, tenants
and roles as the very last step of ``2_identity_transporter.yaml`` scenario,
and only involves keystone APIs.


Configuration options
---------------------

``optimize_user_role_fetch``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Speeds up user role migration process, but is dangerous due to direct DB
manipulations. Tested with grizzly, icehouse and juno releases of keystone.


Frequently Asked Questions
--------------------------

**Q**: I have only specified 1 (one!!!) tenant in filter config, but CF
tries to migrate 100500 tenants to destination! WTF???

**A**:

1. Make sure you have following actions in your `scenario file
   <scenario-files-config>`_:

   - ``act_get_filter: True``
   - ``act_check_filter: True``

2. If you don't need all the public images in destination, you can set
   ``dont_include_public_and_members_from_other_tenants`` option in you
   `filter file <filter-configuration>`_. This will significantly reduce the
   number of tenants to be migrated.
