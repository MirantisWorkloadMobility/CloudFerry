#!/bin/bash
set -e
set -x

export WORKSPACE="${WORKSPACE:-$( cd $( dirname "$0" ) && cd ../../../ && pwd)}"
export CF_DIR="${WORKSPACE}/cloudferry"

cd ${CF_DIR}/devlab/

cf_hostname=`vagrant status | grep running | grep cloudferry | awk '{print $1}'`

echo "Copy code archive to cloudferry-${cf_hostname} VM ..."
cf_ip=`vagrant ssh-config ${cf_hostname} | grep HostName | awk '{print $2}'`
cf_user=`vagrant ssh-config ${cf_hostname} | grep -w "User" | awk '{print $2}'`
cf_port=`vagrant ssh-config ${cf_hostname} | grep Port | awk '{print $2}'`
cf_id=`vagrant ssh-config ${cf_hostname} | grep IdentityFile | awk '{print $2}'`

cf_ssh_options="-oConnectTimeout=5 -oStrictHostKeyChecking=no -oCheckHostIP=no"

cf_ssh_cmd="ssh -q ${cf_ssh_options} -i ${cf_id} ${cf_user}@${cf_ip} -p ${cf_port}"
run_nosetests="cloudferry/devlab/jenkins/cf/run_nosetests.sh"
${cf_ssh_cmd} ${run_nosetests}


xml_src_path="cloudferry/devlab/tests/nosetests.xml"
xml_dst_path="${CF_DIR}/devlab/tests/nosetests.xml"
scp -q ${cf_ssh_options} -i ${cf_id} -P ${cf_port} \
${cf_user}@${cf_ip}:${xml_src_path} ${xml_dst_path}

cd ${CF_DIR}/devlab
vboxmanage list vms
vagrant destroy --force
vboxmanage list vms
