#!/bin/bash
# Description
#    Installs qemu v2.0, which is required for successful live migration
# Usage
#    ./qemu.sh

set -e
set -x

stop nova-compute
add-apt-repository cloud-archive:icehouse
apt-get update
apt-get -y install -o 'Dpkg::Options::=--force-confold' qemu
apt-get install --reinstall libvirt-bin python-libvirt
start nova-compute
