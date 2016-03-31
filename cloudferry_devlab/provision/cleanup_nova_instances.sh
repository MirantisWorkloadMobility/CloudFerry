#!/bin/bash
# Description
#    Cleans up `nova.instances` table with all it's constraints to automate
#    live migration.
# Usage
#    ./cleanup_nova_instances.sh

tables_to_remove=(
    block_device_mapping
    instance_actions_events
    instance_actions
    instance_faults
    instance_info_caches
    instance_system_metadata
    instances
)

service nova-compute stop

for t in ${tables_to_remove[*]}; do
    mysql -uroot -psecret -e "delete from ${t}" nova
done

service nova-compute restart
