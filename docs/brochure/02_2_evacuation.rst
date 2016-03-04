Evacuation
----------

Evacuation within the context of CloudFerry is the stage where the
scenario file created by the Condensation phase is used as a control input
to actually move workloads around within a single cloud to minimize the
number of physical nodes in use. The net result is all the servers that
have any load on them at all are likely to have quite a lot of load on
them until environment is rebalanced or migrated (some rebalancing is a
by-product of migrating). Once Evacuation is undertaken it would be wise
to move forward through to migration or to manually rebalance workload
distribution as quickly as practicable since the failure cost of any one
physical node going down is larger than it was before Evacuation was run.

If, for example, you need to be able to spawn a series of big VM's but no
single node has enough spare resources to contain one then you could use the
Condensation and Evacuation features as a set of tools to move things around to
a maximal load:node ratio thereby freeing up the contiguous resources you need
to spawn that set of large VM's. That is of course only one example; and a very
primitive one at that, of a use case in an infinite world of possibilities and
motivations. The primary purpose of the Condensation and Evacuation features is
to allow cloud operators to clear physical nodes so that they can be moved to
a new cloud and the resources and workloads migrated to that new cloud. It is
not meant for finely managing the node:workload layout within any single cloud.

Evacuation can be configured to deal with the whole of the set of nodes
within a cloud or restricted to any arbitrary subset of nodes through
the use of filter files and the modification of the scenario file
that is outputted as part of the Condensation run. Evacuation allows
two possible back-ends to be used - cobalt and nova live-migrate.
