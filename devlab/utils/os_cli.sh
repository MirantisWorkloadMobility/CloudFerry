#!/bin/bash

# Use this script at your own risk.
# Shell session should be new before running it.
# Workspace should be configured for devlab environment.
# Run script from the root of workspace.
# Usage examples:
# bash devlab/utils/os_cli.sh clean src
# bash devlab/utils/os_cli.sh clean dst

set -x

cfg="devlab/config.ini"

usage() {
    echo
    echo "Script to operate in OpenStack"
    echo "Current usage of this script is to clean lab"
    echo "(remove all VMs, flavors, images, networks, volumes)"
    echo "  bash $0 clean {dst|src}"
    echo "The script uses $cfg for getting access to environment"
    echo "Make sure you have update it properly for all IPs"
    echo
}

src=`grep grizzly_ip $cfg | awk '{print $3}'`
dst=`grep icehouse_ip $cfg | awk '{print $3}'`

pushd $WORKSPACE/cloudferry/devlab

src_hostname=`vagrant status | grep running | grep grizzly | awk '{print $1}'`
dst_hostname=`vagrant status | grep running | grep icehouse | awk '{print $1}'`

src_ip=`vagrant ssh-config $src_hostname | grep HostName | awk '{print $2}'`
dst_ip=`vagrant ssh-config $dst_hostname | grep HostName | awk '{print $2}'`

src_user=`vagrant ssh-config $src_hostname | grep -w "User" | awk '{print $2}'`
dst_user=`vagrant ssh-config $dst_hostname | grep -w "User" | awk '{print $2}'`

src_port=`vagrant ssh-config $src_hostname | grep Port | awk '{print $2}'`
dst_port=`vagrant ssh-config $dst_hostname | grep Port | awk '{print $2}'`

src_id=`vagrant ssh-config $src_hostname | grep IdentityFile | awk '{print $2}'`
dst_id=`vagrant ssh-config $dst_hostname | grep IdentityFile | awk '{print $2}'`

ssh_options="-oConnectTimeout=5 -oStrictHostKeyChecking=no -oCheckHostIP=no"
src_ssh_cmd="ssh -q ${ssh_options} -i ${src_id} ${src_user}@${src_ip} -p ${src_port}"
dst_ssh_cmd="ssh -q ${ssh_options} -i ${dst_id} ${dst_user}@${dst_ip} -p ${dst_port}"

dst_env=`cat << EOF
declare -x OS_AUTH="http://${dst}:35357/v2.0";
declare -x OS_AUTH_URL="http://${dst}:35357/v2.0";
declare -x OS_PASSWORD="admin";
declare -x OS_TENANT_NAME="admin";
declare -x OS_USERNAME="admin";
EOF`
src_env=`cat << EOF
declare -x OS_AUTH="http://${src}:35357/v2.0";
declare -x OS_AUTH_URL="http://${src}:35357/v2.0";
declare -x OS_PASSWORD="admin";
declare -x OS_TENANT_NAME="admin";
declare -x OS_USERNAME="admin";
EOF`

dst_ssh="${dst_ssh_cmd} ${dst_env}"
src_ssh="${src_ssh_cmd} ${src_env}"
net_service="neutron"

#define functions
#arg1 - project name
#arg2 - project description
function create_tenant {
  ${ssh} keystone tenant-create --name ${1} --description ${2}
}

#arg1 - project name
function delete_tenant {
  ${ssh} keystone tenant-delete ${1}
}

#arg1 - name
function get_tenant_id {
  ${ssh} keystone tenant-list | grep ${1} | cut -d ' ' -f 2
}

#arg1 - user name
#arg2 - tenant name
#arg3 - user password
function create_user {
  ${ssh} keystone user-create --name ${1} --tenant ${2} --pass ${3}
}

#arg1 - user name
function delete_user {
  ${ssh} keystone user-delete ${1}
}

#arg1 - user name
#arg2 - role name
#arg3 - tenant name
function add_role_to_user {
  ${ssh} keystone user-role-add --user ${1} --role ${2} --tenant ${3}
}

#arg1 - user name
#arg2 - role name
#arg3 - tenant name
function delete_role_from_user {
  ${ssh} keystone user-role-remove --user ${1} --role ${2} --tenant ${3}
}

#arg1 - name
#arg2 - file
#arg3 - disk format
#arg4 - container format
#arg5 - is public
function create_image {
  ${ssh} glance image-create --name ${1} --file ${2} --disk-format ${3} --container-format ${4} --is-public ${5} --progress
}

#arg1 - name
function delete_image {
  ${ssh} glance image-delete ${1}
}

#arg1 - name
function get_image_id {
  ${ssh} glance image-list | grep ${1} | cut -d ' ' -f 2
}

function get_image_list {
  ${ssh} glance image-list --all-tenants | grep bare | cut -d ' ' -f 2
}

#arg1 - project name
#arg2 - volume name
#arg3 - image src id
#arg4 - size(gb)
function create_volume {
  ${ssh} cinder --os-tenant-name ${1} create --display-name ${2} --image-id ${3} ${4}
}

#arg1 - name
function delete_volume {
  ${ssh} cinder delete ${1}
}

function get_volume_list {
  ${ssh} nova volume-list --all-tenants | grep none | cut -d ' ' -f 2
}

#arg1 - name
#arg2 - id
#arg3 - memory
#arg4 - disk size
#arg5 - cpu number
function create_flavor {
  ${ssh} nova flavor-create ${1} ${2} ${3} ${4} ${5}
}

#arg1 - name
function delete_flavor {
  ${ssh} nova flavor-delete ${1}
}

function get_flavor_list {
  ${ssh} nova flavor-list | grep True | cut -d ' ' -f 2
}

#arg1 - tenant name
#arg2 - vm name
#arg3 - flavor name/id
#arg4 - image name/id
#arg5 - network id
#arg6 - ipv4 fixed address
function create_vm {
  if [ -n "$5" ]; then
    ${ssh} nova --os-tenant-name ${1} boot --flavor ${3} --image ${4} --nic net-id=${5} ${2}
  else
    ${ssh} nova --os-tenant-name ${1} boot --flavor ${3} --image ${4} --nic ${2}
  fi
}

#arg1 - vm name
function delete_vm {
  ${ssh} nova delete ${1}
}

function get_vm_list {
  ${ssh} nova list --all-tenants | grep -v ID | grep -v + | cut -d ' ' -f 2
}

#arg1 - tenant name
#arg2 - network name
function create_in_net {
  ${ssh} ${net_service} net-create --tenant-id ${1} ${2}
}

#arg1 - tenant name
#arg2 - network name
function create_out_net {
  ${ssh} ${net_service} net-create --tenant-id ${1} ${2} --router:external true --provider:network_type flat --provider:physical_network physnet2
}

#arg1 - tenant id
function delete_net {
  ${ssh} ${net_service} net-delete ${1}
}

function get_net_list {
  ${ssh} nova net-list | grep -v ID | grep -v + | cut -d ' ' -f 2
}

#arg1 - name
function get_net_id {
  ${ssh} nova net-list | grep ${1} | grep -v ID | grep -v + | cut -d ' ' -f 2
}

#arg1 - network name
#arg2 - subnetwork name
#arg3 - disable-dhcp or enable-dhcp
#arg4 - gateway
#arg5 - netmask
#arg6 - float ip start
#arg7 - float ip end
function create_subnet {
  if [ -n "$7" ]; then
    ${ssh} ${net_service} subnet-create --tenant-id ${1} ${2} --name ${3} --allocation-pool start=${7},end=${8} --${4} --gateway ${5} ${6}
  else
    ${ssh} ${net_service} subnet-create --tenant-id ${1} ${2} --name ${3} --${4} --gateway ${5} ${6}
  fi
}

#arg1 - network name
function delete_subnet {
  ${ssh} ${net_service} subnet-delete ${1}
}

#arg1 - network name
#arg2 - max count
function get_subnet_list {
  ${ssh} ${net_service} net-show ${1} | grep -a ${2} subnets | grep -v tenant_id | grep -v + | cut -d '|' -f 3 | sed 's/^[ \t]*//'
}

#arg1 - tenant id
#arg2 - router name
#arg3 - external network name
#arg4 - subnet network name
function create_router {
  ${ssh} ${net_service} router-create --tenant-id ${1} ${2}
  ${ssh} ${net_service} router-gateway-set ${2} ${3}
  ${ssh} ${net_service} router-interface-add ${2} ${4}
}

#arg1 - tenant id
function delete_router {
  ${ssh} ${net_service} router-gateway-clear ${1}
  for n in `get_net_list`; do
    for s in `get_subnet_list ${n} 3`; do
      ${ssh} ${net_service} router-interface-delete ${1} ${s}
    done
  done
  ${ssh} ${net_service} router-delete ${1}
}

function get_router_list {
  ${ssh} ${net_service} router-list -F ID | grep -v + | grep -v ID | cut -d '|' -f 2 | sed 's/^[ \t]*//'
}

#arg1 - router name
function get_router_ifaces_list {
  ${ssh} ${net_service} router-show -F ID | grep -v + | grep -v ID | cut -d '|' -f 2 | sed 's/^[ \t]*//'
}

#arg1 - port id
#arg2 - vm id
function attach_port {
  ${ssh} nova interface-attach --port-id ${1} ${2}
}

#arg1 - network name
function create_port {
  ${ssh} ${net_service} port-create ${1}
}

#arg1 - port name
function delete_port {
  ${ssh} ${net_service} port-delete ${1}
}

function get_port_list {
  ${ssh} ${net_service} port-list -F ID | grep -v + | grep -v ID | cut -d '|' -f 2 | sed 's/^[ \t]*//'
}

#arg1 - subnet name
function get_port {
  for x in `${ssh} ${net_service} port-list | grep ${1} | cut -d '|' -f 2 | sed 's/^[ \t]*//'`; do
    output=`${ssh} ${net_service} port-show ${x} -F device_owner | grep compute`
    if [ -n "$output" ]; then echo $x; exit; fi
  done
}

#arg1 - tenant id
#arg2 - network name
function float_ip_create {
  ${ssh} ${net_service} floatingip-create --tenant-id ${1} ${2}
}

function get_float_list {
  ${ssh} ${net_service} floatingip-list | grep -v + | grep -v ID | cut -d '|' -f 2 | sed 's/^[ \t]*//'
}

#arg1 - float ip id
#arg2 - port id
function float_ip_ass {
  ${ssh} ${net_service} floatingip-associate ${1} ${2}
}

#arg1 - float ip id
function float_ip_del {
  ${ssh} ${net_service} floatingip-delete ${1}
}

#arg1 - tenant name
function get_secgrp {
  ${ssh} nova --os-tenant-id ${1} secgroup-list | grep def | cut -d '|' -f 2 | sed 's/^[ \t]*//'
}

#arg1 - group id
function add_rule {
  ${ssh} ${net_service} security-group-rule-create --protocol icmp --direction ingress --remote-ip-prefix 0.0.0.0/0 ${1}
  ${ssh} ${net_service} security-group-rule-create --protocol tcp --port-range-min 22 --port-range-max 22 --direction ingress ${1}
}

function mask2cidr {
    nbits=0
    ifs=.
    for dec in $1 ; do
        case $dec in
            255) let nbits+=8;;
            254) let nbits+=7;;
            252) let nbits+=6;;
            248) let nbits+=5;;
            240) let nbits+=4;;
            224) let nbits+=3;;
            192) let nbits+=2;;
            128) let nbits+=1;;
            0);;
            *) echo "error: $dec is not recognised"; exit 1
        esac
    done
    echo "$nbits"
}

if [[ "$#" -lt "2" ]]; then usage; exit 1; fi
if [[ "$1" == "clean" ]]; then
    if [[ "$2" == "dst" ]]; then ssh=${dst_ssh}; fi
    if [[ "$2" == "src" ]]; then ssh=${src_ssh}; fi
    res=`${ssh} ${net_service} --help &>/dev/null` || net_service="quantum"
    echo cleaning environment
    for x in `get_float_list`; do echo "delete float ip $x"; float_ip_del $x; done
    for x in `get_vm_list`; do echo "delete vm $x"; delete_vm $x; done
    for x in `get_flavor_list`; do echo "delete flavor $x"; delete_flavor $x; done
    for x in `get_volume_list`; do echo "delete volume $x"; delete_volume $x; done
    for x in `get_image_list`; do echo "delete image $x"; delete_image $x; done
    for x in `get_router_list`; do echo "delete router $x"; delete_router $x; done
    for x in `get_port_list`; do echo "delete port $x"; delete_port $x; done
    for x in `get_net_list`; do
        echo "delete subnet in network $x"
        for y in `get_subnet_list ${x}`; do echo "delete subnet $y"; delete_subnet $y; done
        echo "delete network $x"
        delete_net $x
    done
fi
