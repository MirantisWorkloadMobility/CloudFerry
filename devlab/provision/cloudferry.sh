#!/bin/bash -e

SCRIPT=$(basename $0)

error_exit() {
    local message=$1

    if [[ -n $message ]]; then
        echo $message &>2
        echo &>2
    fi

    echo "Usage: ${SCRIPT} --cloudferry-path <CLOUDFERRY SOURCES PATH> --user <VAGRANT USER>"

    exit 1
}

run() {
    echo "Running '$*' as '$VAGRANT_USER'"
    sudo -H -u $VAGRANT_USER $*
}

while [[ $# -ge 1 ]]; do
    case $1 in
        --cloudferry-path) shift; CF_PATH=$1; shift;;
        --user) shift; VAGRANT_USER=$1; shift;;
        *) error_exit "Invalid arg $1";;
    esac
done

[[ -z $CF_PATH ]] && error_exit "Missing --cloudferry-path option"
[[ -z $VAGRANT_USER ]] && error_exit "Missing --user option"

pushd $CF_PATH

apt-get install redis-server -y
service redis-server start

if [[ ! -d .ubuntu-venv ]]; then
    echo "Setting up CloudFerry virtual environment"

    apt-get install build-essential libssl-dev libffi-dev python-dev -y
    run virtualenv .ubuntu-venv
    # pip>=7.0.0 causes fabric to fail dependency resolution (paramiko)
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install pip==6.1.1
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install --allow-all-external -r requirements.txt
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install -r test-requirements.txt
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install pylint pep8 flake8
    echo "CloudFerry setup succeeded!"
else
    echo "CloudFerry venv is already present, skipping"
fi

popd

