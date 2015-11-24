#!/bin/bash
# Description:
#    Updates libvirt configuration to support passwordless unencrypted
#    connection in libvirt
# Usage:
#    ./libvirt.sh
#

echo "Updating libvirtd.conf"
sed -i 's/^.*listen_tls.*=.*$/listen_tls = 0/' /etc/libvirt/libvirtd.conf
sed -i 's/^.*listen_tcp.*=.*$/listen_tcp = 1/' /etc/libvirt/libvirtd.conf
sed -i 's/^.*auth_tcp.*=.*$/auth_tcp = "none"/' /etc/libvirt/libvirtd.conf

echo "Updating libvirt-bin default config"
sed -i 's/^.*libvirtd_opts.*=.*$/libvirtd_opts="-d -l"/' /etc/default/libvirt-bin

echo "Restarting libvirt services"
service libvirt-bin restart
service nova-compute restart
