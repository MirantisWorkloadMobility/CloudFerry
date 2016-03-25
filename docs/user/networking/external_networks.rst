.. _external-networks-migration:

=================
External networks
=================

External networks migration follows :ref:`general-neutron-migration-rules`
and :ref:`network-and-subnet-migration` with a number of specific details.

External networks with overlapping CIDRs
----------------------------------------

In case source and destination cloud external networks don't match exactly
and their CIDRs overlap, (for example 10.0.0.100-200 range in source cloud
and 10.0.0.150-250 range in destination) CloudFerry will not start migration
and operator is expected to resolve this problem manually.

Mapping external networks from source cloud to destination
----------------------------------------------------------

There are many cases when external networks in source cloud don't match
those in destination. In order to run migration in those cases CloudFerry
allows mapping between source and destination external networks, which is
specified in networks mapping YAML file with format::

    <source cloud external net id 1>: <destination cloud external net id 1>
    <source cloud external net id 2>: <destination cloud external net id 2>
    ...
    <source cloud external net id N>: <destination cloud external net id N>

The file is specified with ``[migrate] ext_net_map`` config option.

.. important::

    When external networks mapping is used, floating IPs will **not** be
    kept regardless of ``[migrate] keep_floating_ip`` option value and
    even if mapped networks are identical.


Floating IPs
------------

Floating IP migration depends on two config options:

 - ``keep_floatingip`` in ``[migrate]`` group
 - ``ext_net_map`` in ``[migrate]`` group


``keep_floatingip``
^^^^^^^^^^^^^^^^^^^

When ``keep_floatingip`` option is set to ``True``, CloudFerry attempts to
migrate floating IPs to destination cloud without modifying them. Neutron APIs
do not provide ways of specifying particular floating IP, thus this change is
done at DB level and is very dangerous.

.. warning::

    ``keep_floatingip`` option may be dangerous because it involves
    direct modification of destination cloud neutron database


When ``keep_floatingip`` option is disabled floating IPs are allocated in
the same external network in destination, but IP addresses are **not kept**.


``ext_net_map``
^^^^^^^^^^^^^^^

``ext_net_map`` option defines mapping between source cloud external
networks and destination cloud external networks. With mapping set floating
IPs are not kept during migration.
