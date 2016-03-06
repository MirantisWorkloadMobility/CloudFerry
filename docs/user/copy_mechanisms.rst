.. _copy-mechanisms:

====================
File copy mechanisms
====================

CloudFerry supports 3 different tools to copy files across clouds:

 1. ``scp``
 2. ``rsync``
 3. ``bbcp``

Those are configured in :ref:`primary-config-file`::

    [migrate]
    copy_backend = <scp, rsync or bbcp>


scp
---

Uses ``scp`` to copy data between clouds.

Pros:

 - reliable - present on most of systems;
 - secure - data is encrypted;

Cons:

 - may be slower compared to other data copy types due to encryption of data.


rsync
-----

Uses ``rsync`` to copy data between clouds.

Pros:

 - reliable - ``rsync`` protocol is well defined and is known for ages.

Cons:

 - may be slower than other types of data transfer because it requires SSH
   tunnel to run in.


bbcp
----

`bbcp <http://pcbunn.cithep.caltech.edu/bbcp/using_bbcp.htm>`_ allows copying
data in multiple parallel networking connections, which usually results in
much faster data transfer rates.

Pros:

 - the fastest kind of data transfer thanks to multiple network connections
   for data transfer;

Cons:

 - is not present in most common linux distributions, thus requires
   compilation from sources and distribution on nodes
