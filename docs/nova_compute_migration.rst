=============================
Nova non-VM objects migration
=============================

:dfn:`act_comp_res_trans` action which can be found in
:file:`cold_migrate.yaml` and :file:`4_transport_compute_resources.yaml`
allows user to migrate following nova compute objects:

 - nova user quotas;
 - nova tenant quotas;
 - nova flavors.


.. note::

    User quotas have only become available with Icehouse (2014.1) Openstack
    release and they allow to control quotas for each user. This means that
    user quotas will not be migrated in case source cloud is Grizzly or
    earlier release.


Quota migration process
-----------------------

Quota migration process only involves nova APIs, so the process from the
high level is following:

 1. Retrieve all quotas based on :ref:`filtering rules <filter-configuration>`
    from source cloud using nova APIs;
 2. Create user and tenant quotas to destination cloud using nova APIs.


.. warning::

    Default nova user and tenant quotas are configured in :file:`nova.conf`
    and are **not** transferred to the destination cloud, Openstack services
    configuration migration is beyond CloudFerry functionality.


Flavor migration process
------------------------

.. note::

    Flavors UUID are kept during migration


.. note::

    If flavor with the same ID exists in destination, but differs from
    flavor in source -- it will be deleted and replaced with flavor from
    source cloud


Flavors are one of the few objects in Openstack which allow setting UUID
through APIs, which may lead to a situation when destination cloud already has
flavor with the same ID as flavor in the source cloud, yet different (for
example number of VCPUs are different). This creates a special case for
migration process:

 1. Retrieve list of flavors from source based on
    :ref:`filtering rules <filter-configuration>` using nova APIs;
 2. Try to create flavor in destination cloud with the same ID and all
    flavor attributes (number of VCPUs, RAM, ephemeral storage, etc.);
 3. In case flavor with the same ID, but with different attributes exists in
    destination -- this flavor is **removed**, and flavor from source cloud
    is created instead;
 4. For private flavors -- share flavor with tenants it was shared in the
    source cloud.
