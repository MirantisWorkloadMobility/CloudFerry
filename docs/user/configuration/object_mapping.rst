============================
Object Mapping Configuration
============================

Currently there are two configuration files which allow mapping of OpenStack
resources between clouds:

 - external networks mapping defined in ``[migrate] ext_net_map`` config
   option;
 - VM parameters mapping rules defined in ``[migrate] override_rules`` for 
   attributes like availability zone and flavor.
   

External networks mapping
-------------------------

For the cases when external (public) networks in source cloud don't match 
those in destination one may want to define where the floating IPs will land. 
This can be done by setting ``[migrate] ext_net_map`` config value to point 
to a YAML file with the following format::

    <source cloud external net id 1>: <destination cloud external net id 1>
    <source cloud external net id 2>: <destination cloud external net id 2>
    ...
    <source cloud external net id N>: <destination cloud external net id N>    

See more in :ref:`external-networks-migration`.


Nova objects mapping
--------------------

Often clouds don't have the same availability zones or server groups defined,
in these cases migration operator may want to map those objects in source 
cloud to objects in destination cloud. This can be done by specifying 
``[migrate] override_rules`` config option to point to a YAML file with the 
following format::

    <migration object attribute>:
    - [when:
         <migration object attribute>
       replace:
         <value>]
    - [default:
         <default value>]

There can be zero or more matching rules defined with ``when`` and
``replace`` keywords and zero or one ``default`` value.

The workflow for this config is as follows: process goes through the list of
rules and picks the first match for object attribute. If no matches found -
``default`` value is used. If ``default`` value is not specified - source
object value is used.

See examples below for more insight.


Mapping server groups
^^^^^^^^^^^^^^^^^^^^^

Use ``server_group`` migration object name::

    server_group:
    - when:
        id:
        - 14ba292e-f0bb-4eec-9b3a-abb775db7ff4
        - 533d5840-8584-47bc-be16-2825536e9027
        - 7398b91f-e1c2-4378-9943-391318981aee
        - 1da4d59e-06de-4d34-b0e7-655e886e0183
      replace: 66e76c27-874d-48e1-bca2-b0eb0ea95ff3

This would replace all server groups listed in ``id`` group with 
``66e76c27-874d-48e1-bca2-b0eb0ea95ff3``.


Mapping availability zones
^^^^^^^^^^^^^^^^^^^^^^^^^^

Use ``availability_zone`` migration object name::

    availability_zone:
    - when: source_az
      replace: destination_az
    - when:
        availability_zone:
        - us_west_dc3
        - us_west_dc4
        - us_west_dc5
      replace: us_east_dc1
    - when: null
      replace: us_west_dc2

In this example

 1. VMs running in ``source_az`` availability zone, will be created in
    ``destination_az`` availability zone in destination cloud;

 2. VMs running in ``us_west_dc3``, or ``us_west_dc4``, or ``us_west_dc5``
    availability zones in source cloud will be created in ``us_east_dc1``
    availability zone in destination cloud;

 3. VMs running in all other zones will be created in ``us_west_dc2``
    availability zone in destination cloud.
