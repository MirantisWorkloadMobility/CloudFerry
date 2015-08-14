#!/bin/bash

# Script installs devstack on predefined Ubuntu14.04
# You can specify as branch or tag
# Usage ./devstack.sh --branch stable/juno 
# Usage ./devstack.sh --branch icehouse_eol

set -e

devstack_dir='devstack'

while [[ $# -ge 1 ]]; do
    case $1 in
        --branch) shift; branch="$1"; shift;;
    esac
done

which git || sudo apt-get install -y git
git clone https://github.com/openstack-dev/devstack.git ${devstack_dir}
cd ${devstack_dir}
git checkout $branch

cp /tmp/local.conf .

./stack.sh


# Add physical eth1 interface to the floating bridge
# This allow access to the vm's inside of openstack directly from the host-server
floating_interface='eth1'
sudo ovs-vsctl add-port br-ex $floating_interface
sudo ip addr del `ip addr sh $floating_interface   | grep "inet " | awk '{print $2}'` dev $floating_interface
sudo ip link set $floating_interface promisc on
sudo ip link set br-ex promisc on



#generate openrc file
. openrc
function gen_openrc {
    destination_openrc=$1
    OS_USERNAME=$2
    OS_TENANT_NAME=$3

    > $destination_openrc
    for i in `env | grep ^OS`
        do
            echo "export $i" >> ${destination_openrc}
        done
}

gen_openrc "../openrc_admin" "admin" "admin"
gen_openrc "../openrc_demo" "demo" "demo"


