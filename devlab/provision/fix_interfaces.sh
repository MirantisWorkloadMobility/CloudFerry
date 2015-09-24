#!/bin/bash
# Add physical eth1 interface to the floating bridge
# This allows access to the vm's inside of openstack directly
# from the host-server
floating_interface='eth1'
sudo ovs-vsctl add-port br-ex $floating_interface
int_addr=`ip addr sh $floating_interface   | grep "inet " | awk '{print $2}'`
sudo ip addr del $int_addr dev $floating_interface
sudo ip addr add $int_addr dev br-ex
sudo ip link set $floating_interface promisc on
sudo ip link set br-ex promisc on
sudo ip link set dev br-ex up
