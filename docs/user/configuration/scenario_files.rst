.. _scenario-files-config:

==============
Scenario files
==============

Scenario file defines migration procedure and objects to be migrated. You
can specify scenario in :ref:`primary-config-file`::

    [migrate]
    scenario = <path to scenario file>


Scenario is a YAML file with actions split in following sections:

 - :dfn:`preparation` – actions which do not require rollback, typically sanity
   checks, such as configuration checks and source and destination clouds
   functionality verification
 - :dfn:`rollback` – actions executed if :dfn:`process` actions failed
 - :dfn:`process` – groups primary migration process actions, such as copying
   tenants, images, volumes, etc.

There are plenty of examples of migration scenarios in
:file:`CloudFerry/scenario` folder scenario file names speak for themselves:

 - :file:`cold_migrate.yaml` – all-in-one migration scenario, tries to migrate
   all the openstack objects in a single run

:file:`stages` folder contains all independent object migration split into
separate migration files, which allows more granularity for the user.

 - :file:`0_prechecks.yaml` runs initial checks, which allows to spot most of
   the problems in configuration
 - :file:`1_checkcloud.yaml` allows to verify that source and destination
   clouds are actually functioning which is not always the case with
   Openstack-based clouds
 - :file:`2_identity_transporter.yaml` runs migration of keystone objects
 - :file:`3_get_and_transfer_images.yaml` runs migration of glance images
 - :file:`4_transport_compute_resources.yaml` runs migration of nova flavors
   and quotas
 - :file:`5_network_transporter.yaml` runs migration of neutron resources,
   such as networks, subnets, ports and security groups
 - :file:`6_migrate_volumes.yaml` runs migration of cinder volumes
 - :file:`7_transport_keypairs.yaml` copies nova key pairs
 - :file:`8_migrate_server_groups.yaml` copies server groups

Most actions depend on :dfn:`act_identity_trans` action, because most objects
(all except key pairs) are explicitly associated with keystone tenant.
