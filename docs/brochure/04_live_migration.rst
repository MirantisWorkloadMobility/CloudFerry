==============
Live Migration
==============

Live Migration is tiny bit of a misnomer. When you migrate tenants
between clouds there will be a period of unavailability for the workloads and resources
being moved, however brief. Live migration uses block migration which alleviates
the need to take snapshots. That means the instance doesn't need to quiesce to
migrate and can stay up and running.
