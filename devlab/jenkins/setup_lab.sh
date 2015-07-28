#!/bin/bash
set -e
set -x

export WORKSPACE="${WORKSPACE:-$( cd $( dirname "$0" ) && cd ../../../ && pwd)}"
export CF_DIR=$WORKSPACE/cloudferry
export JOB_NAME="${JOB_NAME:-cloudferry-functional-tests}"
export BUILD_NUMBER="${BUILD_NUMBER:-$[ 1 + $[ RANDOM % 1000 ]]}"
export BUILD_NAME="${BUILD_NAME:--$(echo $JOB_NAME | sed s/cloudferry/cf/)-${BUILD_NUMBER}}"
export VIRTUALBOX_NETWORK_NAME="vn-${JOB_NAME}-${BUILD_NUMBER}"

echo "Generate SSH key pair for 'cloudferry' instance"
rm -rf ${CF_DIR}/devlab/provision/cf_keys
mkdir ${CF_DIR}/devlab/provision/cf_keys
cd ${CF_DIR}/devlab/provision/cf_keys
ssh-keygen -f id_rsa -t rsa -N ''


echo "Preparing lab"
cd  ${CF_DIR}/devlab
echo 'Removing old VMs if exist...'
vagrant destroy --force

echo 'Booting new VMs...'
#vagrant box update
vagrant up grizzly${BUILD_NAME} icehouse${BUILD_NAME} cloudferry${BUILD_NAME}


echo 'Running test load cleaning...'
pushd $CF_DIR
bash ${CF_DIR}/devlab/utils/os_cli.sh clean dst
