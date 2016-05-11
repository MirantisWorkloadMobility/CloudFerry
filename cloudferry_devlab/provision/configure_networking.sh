#!/usr/bin/env bash

HW_IFACE=$1
BRIDGE_IFACE=$2
IP_ADDR=$3

sudo cat << EOF > /etc/rc.local
#!/bin/sh -e
bridges=\`awk '{ if (\$1 == "allow-ovs") { print \$2; } }' /etc/network/interfaces\`
[ -n "\${bridges}" ] && ifup --allow=ovs \${bridges}

exit 0
EOF

sudo cat << EOF >> /etc/network/interfaces

auto ${HW_IFACE}
iface ${HW_IFACE} inet manual
    up ip link set \$IFACE promisc on
    down ip link set \$IFACE promisc off

allow-ovs ${BRIDGE_IFACE}
iface ${BRIDGE_IFACE} inet static
    ovs_type OVSBridge
    address ${IP_ADDR}
    netmask 255.255.255.0
    up ip link set \$IFACE promisc on
    down ip link set \$IFACE promisc off
EOF

[ -z $(sudo ovs-vsctl list-ports ${BRIDGE_IFACE} | grep ${HW_IFACE}) ] && sudo ovs-vsctl add-port ${BRIDGE_IFACE} ${HW_IFACE}
sudo ip addr add ${IP_ADDR}/24 dev ${BRIDGE_IFACE}
sudo ip link set ${HW_IFACE} promisc on
sudo ip link set ${BRIDGE_IFACE} promisc on
sudo ip link set dev ${HW_IFACE} up
sudo ip link set dev ${BRIDGE_IFACE} up
