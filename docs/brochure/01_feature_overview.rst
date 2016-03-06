================
Feature Overview
================


.. image:: images/openstack-clouds.png
    :align: center


What is it?
-----------

Quite simply, CloudFerry is an open-source tool for resource and workload
migration between OpenStack clouds. A "workload" is a virtual machine
and all the resources that were used to create it.

Why?
----

Within an OpenStack cloud environment there may be many Tenants. Within a
tenant there are many workloads which are composed from resources like images,
flavors, block storage volumes, etc... Occasionally Cloud operators will need
to move Cloud resident resources and workloads from one environment to another.
Doing so manually is a tedious and risky process which has many steps,
challenges and pitfalls.

CloudFerry provides a source of automation for the task of resource
and workload migration between OpenStack Clouds that makes a virtue of
removing most of the risk and speeding the process tremendously; just like
automation is supposed to do. CloudFerry comes with useful pre-fabricated
configurations but is also highly configurable. Users can use the with minimal
customization or they can go completely custom to meet their requirements.
