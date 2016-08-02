#!/bin/bash

PUB_KEY=$1
PRV_KEY=$2
USERS=("${@:3}")

if [[ -z ${PUB_KEY} ]]
then
    echo "Missing user public-key"
    exit 1
fi

if [[ -z ${PRV_KEY} ]]
then
    echo "Missing user private-key"
    exit 1
fi

for user in "${USERS[@]}"; do
    home=$( awk -F: -v user=${user} 'user == $1 {print $(NF - 1)}' /etc/passwd )
    ssh_dir="${home}/.ssh"
    mkdir -p "${ssh_dir}"
    echo "${PUB_KEY}" >> "${ssh_dir}/authorized_keys"
    echo "${PUB_KEY}" > "${ssh_dir}/id_rsa.pub"
    echo "${PRV_KEY}" > "${ssh_dir}/id_rsa"
    chown "${user}:${user}" "${ssh_dir}" -R
    chmod 700 "${ssh_dir}"
    chmod 660 "${ssh_dir}/authorized_keys"
    chmod 600 "${ssh_dir}/id_rsa"
    chmod 644 "${ssh_dir}/id_rsa.pub"
done

