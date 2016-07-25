#!/usr/bin/env bash

CINDER_CONF_FILES="/etc/cinder/nfsshares*"
OLD_NFS_NAME=${1}
NEW_NFS_NAME=${2}

sed -i "s/${OLD_NFS_NAME}/${NEW_NFS_NAME}/g" ${CINDER_CONF_FILES}
service cinder-volume restart
