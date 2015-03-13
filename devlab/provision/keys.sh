#!/bin/bash

SCRIPT=$(basename $0)

error_exit() {
    local message=$1

    if [[ -n $message ]]; then
        echo $message &>2
        echo &>2
    fi

    echo "Usage: ${SCRIPT} --public-key <PUBLIC_KEY>"

    exit 1
}

while [[ $# -ge 1 ]]; do
    case $1 in
        --public-key) shift; PUB_KEY="$1"; shift;;
        *) error_exit "Invalid arg $1";;
    esac
done

[[ -z $PUB_KEY ]] && error_exit "Missing --public-key option"

ssh_dir=/root/.ssh

if ! grep -s "$PUB_KEY" $ssh_dir/authorized_keys; then
    mkdir -p $ssh_dir
    echo "$PUB_KEY" >> $ssh_dir/authorized_keys
fi
