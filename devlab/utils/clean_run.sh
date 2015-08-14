#!/bin/bash

# Use this script at your own risk.
# Shell session should be new before running it.
# Workspace should be configured for devlab environment, see README.md.
# Run script from the root of workspace.

set -e

cur_pwd=`pwd`
cfg="devlab/config.ini"
dftl_ip="192.168.1.2"

usage() {
    echo
    echo "Script to run clean migration"
    echo "It uses $cfg for getting access to environment"
    echo "If you want to do it for default options, please, use -f"
    echo "  bash $0 -f"
    echo "In other case the script uses $cfg"
    echo "Make sure you have update it properly for all IPs"
    echo
}

if [[ "$1" != "-f" ]] && [[ `grep -q $dftl_ip $cfg && echo $?` == "0" ]]; then
    echo "Warning! Default config detected"
    usage
    exit 1
fi

SRC=`grep grizzly_ip $cfg | awk '{print $3}'`
DST=`grep icehouse_ip $cfg | awk '{print $3}'`
dst_mysql_user=`grep dst_mysql_user $cfg | awk '{print $3}'`
dst_mysql_password=`grep dst_mysql_password $cfg | awk '{print $3}'`

echo "src $SRC, dst $DST"
export SRC_OS_TENANT_NAME=admin
export SRC_OS_USERNAME=admin
export SRC_OS_PASSWORD=admin
export SRC_OS_AUTH_URL="http://$SRC:5000/v2.0/"
export SRC_OS_IMAGE_ENDPOINT="http://$SRC:9292"
export SRC_OS_NEUTRON_ENDPOINT="http://$SRC:9696/"
export DST_OS_TENANT_NAME=admin
export DST_OS_USERNAME=admin
export DST_OS_PASSWORD=admin
export DST_OS_AUTH_URL="http://$DST:5000/v2.0/"
export DST_OS_IMAGE_ENDPOINT="http://$DST:9292"
export DST_OS_NEUTRON_ENDPOINT="http://$DST:9696/"
cd devlab
cd tests && python generate_load.py --clean --env DST
python generate_load.py --clean --env DST
python generate_load.py --clean --env DST
ssh root@$DST \
"mysql -u $dst_mysql_user -p$dst_mysql_password cinder -e \"delete from cinder.volume_admin_metadata;
delete from cinder.volumes;delete from cinder.reservations;delete from cinder.quota_usages;\""

cd $cur_pwd
bash devlab/utils/os_cli.sh clean dst
fab migrate:configuration.ini
