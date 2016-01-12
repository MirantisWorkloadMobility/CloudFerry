#!/bin/bash
# Add physical eth1 interface to the floating bridge
# This allows access to the vm's inside of openstack directly
# from the host-server
function setup_interface {
    sudo ovs-vsctl add-port $1 $2
    int_addr=`ip addr sh $2 | grep "inet " | awk '{print $2}'`
    sudo ip addr del $int_addr dev $2
    sudo ip addr add $int_addr dev $1
    sudo ip link set $2 promisc on
    sudo ip link set $1 promisc on
    sudo ip link set dev $1 up
}
setup_interface br-ex eth1
setup_interface br-ex2 eth2
