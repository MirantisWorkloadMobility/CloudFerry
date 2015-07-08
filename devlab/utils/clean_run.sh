#!/bin/bash

# Use this script at your own risk.
# Shell session should be new before running it.
# Workspace should be configured for devlab environment, see README.md.
# Run script from the root of workspace.

set -e

cur_pwd=`pwd`
cfg=devlab/config.ini

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
delete from cinder.volumes;\""

cd $cur_pwd
fab migrate:configuration.ini
