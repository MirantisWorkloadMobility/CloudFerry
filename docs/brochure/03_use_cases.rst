================
Nominal Use Case
================

An enterprise has an existing OpenStack cloud running an older
release and wants to upgrade. CloudFerry provides the Condensation, Evacuation
and Migration functionality making this process less confusing, less error prone
and massively faster than any manual means.


.. image:: images/time-to-upgrade.jpg
    :align: center


Since OpenStack doesn't provide a direct software upgrade path the Cloud
operator will start by building a small OpenStack cloud with enough hardware to
take the first few tenants with the latest OpenStack release. They then run
CloudFerry Condensation to determine the number of physical nodes that can be
freed up and moved to the destination cloud. They then run Evacuation to get the
legacy cloud workloads onto as few nodes as possible. Once the source cloud has
been compacted the Cloud operator can move the freed up physical nodes to the
new cloud and gradually migrate workloads into the new cloud to use the migrated
hardware.

Migrations are done tenant-by-tenant which allows a measure of granularity,
control and flexibility making the process massively easier than it would be to
do manually. It also means that you don't use CloudFerry to move a single
instance from Cloud-A to Cloud-B.

If a particular server or set of servers needs to be freed up for any reason
before some other set then an Evacuation can be performed against those specific
servers or filters can be used to set the order of operations or the operator
can manually migrate the instances from those nodes and run Condensation after
that.

Now that resources are in place to take the first wave of workload, migration
can be undertaken. A tenant is chosen for migration and moved to the new
OpenStack Cloud using CloudFerry. As hardware is freed up it can be moved to the
destination cloud. It may become necessary, depending on how much hardware was
provisioned for the destination cloud in the first place, to run multiple
Condensation and/or Evacuation processes along the way. Once all tenants have
been migrated the source cloud can be dismantled and its remaining resources
added to the destination cloud. Project complete!


Pre-Migration Considerations
----------------------------

Application Fault Tolerance:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Properly designed cloud capable applications are distributed across many
availability zones and should be able to tolerate bringing down of a single
availability zone without substantially degrading performance or functionality.
CloudFerry operates only within a single availability zone which means that
while all of the availability zones aren't running, the application remains
available as far as the consumer of that application knows.


Requirements:
^^^^^^^^^^^^^

 - Connection to source and destination clouds through external (public)
   network from host with CloudFerry;
 - Valid private ssh-key for both clouds which will be used by CloudFerry for
   data transferring;
 - Admin keystone access (typically admin access point lives on 35357 port)
 - sudo/root access on compute and controller nodes;
 - Openstack MySQL DB write access;
 - Credentials of global cloud admin for both clouds;
 - All the Python requirements are listed in the package in
   :file:`requirements.txt`.


Other Important Factors:
^^^^^^^^^^^^^^^^^^^^^^^^

The amount of time it takes to migrate a tenant will depend
completely upon the speed of the network.

 - Condensation of VM's is fast. Condensation of Software Defined Networks
   can be exceptionally slow due to limitations of the Neutron API.
 - CloudFerry configuration can be described as non-trivial. Just like any
   highly configurable system. It is advised that users take a little while to
   get to know CloudFerry before attempting to use it on a production
   environment.
 - CloudFerry works via SSH/SCP, MySQL transactions and OpenStack API calls.
 - Considerable knowledge of OpenStack is a requirement for successful use of
   CloudFerry
