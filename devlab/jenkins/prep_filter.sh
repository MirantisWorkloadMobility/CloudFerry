#!/bin/bash

set -e

filter="configs/filter.yaml"
cfg="devlab/config.ini"

usage() {
    echo
    echo "Script to make a filter.yaml"
    echo "  bash $0 --tenant <tenant_name>"
    echo "The script uses $cfg for getting access to environment"
    echo "Make sure you have update it properly for all IPs"
    echo
}

src=$(grep grizzly_ip $cfg | awk '{print $3}')
ssh_user=$(grep src_ssh_user $cfg | awk '{print $3}')
ssh_cmd="ssh $ssh_user@${src}"

if [[ "$#" -lt "2" ]]; then usage; exit 1; fi
if [[ $1 == "--tenant" ]]; then
tenant_id=$(${ssh_cmd} "keystone tenant-list | grep $2 | cut -d \" \" -f 2")
cat <<EOF > $filter
tenants:
    tenant_id:
        - $tenant_id
EOF
fi

