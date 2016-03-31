====================
Migration Estimation
====================

Overview
--------

It is usually required to estimate how much time migration will take in order
to plan for maintenance hours on production systems. Migration estimation
functionality will help to figure out how much data it is necessary to transfer
between clouds and based on this estimate amount of time it will take.

Quick Start Guide
-----------------

1. Add credentials for source and destination cloud to ``discover.yaml`` file,
   for example::

    clouds:
      src_grizzly:
        credential:
          auth_url: https://keystone.example.com/v2.0/
          username: admin
          password: admin
          region_name: grizzly
        scope:
          project_id: 00000000000000000000000000000001
        ssh:
          username: foobar
          sudo_password: foobar
          connection_attempts: 3
      dst_liberty:
        credential:
          auth_url: https://keystone.example.com/v2.0/
          username: admin
          password: admin
          region_name: liberty
        scope:
          project_id: 00000000000000000000000000000002
        ssh:
          username: foobar
          sudo_password: foobar
          connection_attempts: 3

2. Add information about migrations to ``discover.yaml`` file, for example::

    migrations:
      grizzly_to_liberty:
        source: src_grizzly
        destination: dst_liberty
        objects:
          vms:
            - tenant.name: demo
          images:
            - tenant.name: demo
          volumes:
            - tenant.name: demo

3. Run ``fab estimate_migration:/path/to/discover.yaml,grizzly_to_liberty``.
   Where ``/path/to/discover.yaml`` is path to ``discover.yaml`` configuration
   file and ``grizzly_to_liberty`` is the name of migration defined in this
   file.
   Example::

    $ fab estimate_migration:/path/to/discover.yaml,grizzly_to_liberty
    Migration grizzly_to_liberty estimates:
    Images:
      Size: 842.3MB
    Ephemeral disks:
      Size: 121.3GB
    Volumes:
      Size: 0.0GB

    10 largest servers:
      1. 4fcc44be-583f-4f58-8f07-5fe703afaef8 poldb02 - 24.0GB
      2. 4b1593ef-d8c3-414c-9ca8-2a48157b0fb7 pol01 - 16.6GB
      3. 8f6f3beb-d4c5-434b-a96e-f92a6da22f3b syslog01 - 14.0GB
      4. 64546943-30c7-402d-a42d-64c94d27b9d2 nagios-sat-red01 - 9.8GB
      5. a1efe771-ecef-485d-97fa-843fc2578019 dispatch01 - 7.0GB
      6. 324d79b3-551e-49ea-85a4-e8121c639dbb marketplace-ui01 - 6.1GB
      7. e4ec887f-1c0e-4918-bb2e-62b54b3b953d authz01 - 6.0GB
      8. 0fbac35b-7195-49d9-976e-23eb6b0a0d0b dispatchlb01 - 5.9GB
      9. e2beafbb-670a-450a-9677-c2d2dc779888 support-ui01 - 5.8GB
      10. a677dc39-7339-4a91-961b-11e5a3956b5e policy-ui01 - 5.7GB

    Done.

   On first run this command will download information about all objects in
   all clouds defined in clouds section, then it ssh into every active compute
   node that have VM instance running and get information about connected disks
   from them. This step will be stored into local SQLite3 database which will
   be stored into ``migration_data.db`` file (you can change path to this file
   using ``CF_LOCAL_DB`` environment variable). This step can take long time
   (up to several hours) for large clouds with lots of VMs.

   All other ``fab estimate_migration`` runs will use data stored in SQLite3 DB
   and won't try to access cloud  API unless new cloud will be added into
   ``discover.yaml`` or ``region_name`` or ``auth_url`` parameters of existing
   clouds will be changed.

4. If you want to update information collected from clouds you will need to run
   ``fab discover:/path/to/discover.yaml``. This will erase all previously
   discovered information from SQLite3 DB and put updated information from
   cloud APIs and compute nodes there.


Object Selection for Migration
------------------------------

When defining migration you need to provide query which will define what
objects you want to migrate from source to destination cloud. Please keep in
mind that dependencies of those objects will be migrated too. For example
if you select to migrate all VMs owned by tenant "X", one of which is booted
from image "A" which is owned by tenant "Y", then both tenant "X" and "Y" will
be created in destination cloud and image "A" will be created in this tenant.
Other images owned by tenant "Y" will not be migrated unless some of chosen VMs
are booted from it.

Object selection queries are specified in ``objects`` section of migration. It
is a dictionary with keys specifying type of objects to be selected and values
specify list of filters. Object will be selected if it passes at least one
filter in the list.


Applying OR Logical Operator to Object Selection Rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example::

    migrations:
      grizzly_to_liberty:
        source: src_grizzly
        destination: dst_liberty
        objects:
          images:
            - tenant.name: demo
            - is_public: true

Object will be selected for migration if ``tenant.name: demo`` filter pass OR
``is_public: true`` filter pass. Basically it means that any public image OR
image owned by ``demo`` tenant will pass this filter and will be migrated as
part of ``grizzly_to_liberty`` migration.


Applying AND Logical Operator to Object Selection Rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example::

    migrations:
      grizzly_to_liberty:
        source: src_grizzly
        destination: dst_liberty
        objects:
          images:
            - tenant.name: demo
              is_public: true

Object will be selected for migration if ``tenant.name: demo`` filter AND
``is_public: true`` filter both pass. Basically it means that any image owned
by ``demo`` tenant AND being public at the same time will pass this filter and
will be migrated as part of ``grizzly_to_liberty`` migration.


Applying NOT Logical Operator to Object Selection Rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In order to create negative filter (e.g. for example you want to migrate all
images except from tenant ``rally_image_test``) prepend field name with "!"
sign::

    migrations:
      grizzly_to_liberty:
        source: src_grizzly
        destination: dst_liberty
        objects:
          images:
            - !tenant.name: rally_image_test

Object will be selected for migration if it is not owned by
``rally_image_test`` tenant. Basically all tenants except for
``rally_image_test`` will be migrated.

Writing Object Selection Rules using JMESPath syntax
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Object selection engine is built on top of JMESPath library, so it's also
possible to use raw JMESPath queries for advanced usage. Documentation on query
syntax can be found by following this link: http://jmespath.org/tutorial.html .
Example getting all public images or owned by tenant ``demo`` using JMESPath
query::

    migrations:
      grizzly_to_liberty:
        source: src_grizzly
        destination: dst_liberty
        objects:
          images:
            - '[? tenant.name == `demo` || is_public == true ]'
