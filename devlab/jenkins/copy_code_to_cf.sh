#!/bin/bash
set -e
set -x

export WORKSPACE="${WORKSPACE:-$( cd $( dirname "$0" ) && cd ../../../ && pwd)}"
export CF_DIR="${WORKSPACE}/cloudferry"

echo ${CF_DIR}


cd ${CF_DIR}/devlab/

cf_hostname=`vagrant status | grep running | grep cloudferry | awk '{print $1}'`

echo "Copy code archive to cloudferry-${cf_hostname} VM ..."
cf_ip=`vagrant ssh-config ${cf_hostname} | grep HostName | awk '{print $2}'`
cf_user=`vagrant ssh-config ${cf_hostname} | grep -w "User" | awk '{print $2}'`
cf_port=`vagrant ssh-config ${cf_hostname} | grep Port | awk '{print $2}'`
cf_id=`vagrant ssh-config ${cf_hostname} | grep IdentityFile | awk '{print $2}'`
cf_ssh_cmd="ssh -q -oConnectTimeout=5 -oStrictHostKeyChecking=no -oCheckHostIP=no -i ${cf_id} ${cf_user}@${cf_ip} -p ${cf_port}"
cf_ssh_cmd="ssh -q -oConnectTimeout=5 -oStrictHostKeyChecking=no -oCheckHostIP=no -i ${cf_id} ${cf_user}@${cf_ip} -p ${cf_port}"
untar_cf="rm -rf cloudferry/; tar xvfz cloudferry.tar.gz;"

scp -q -oConnectTimeout=5 -oStrictHostKeyChecking=no -oCheckHostIP=no -i ${cf_id} -P ${cf_port} ${WORKSPACE}/cloudferry.tar.gz ${cf_user}@${cf_ip}:cloudferry.tar.gz
${cf_ssh_cmd} ${untar_cf}
