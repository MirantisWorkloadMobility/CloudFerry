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
    sudo -u $VAGRANT_USER $*
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

CF_PATH=/home/${VAGRANT_USER}/${CF_PATH}
pushd $CF_PATH

apt-get install redis-server -y
service redis-server start

if [[ ! -d CloudFerry && ! -f CloudFerry/requirements.txt ]]; then
    echo "Cloning CloudFerry repo to $CF_PATH"
    run git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git
fi

pushd CloudFerry
if [[ ! -d .ubuntu-venv ]]; then
    echo "Setting up CloudFerry virtual environment"

    apt-get install python-dev libffi-dev -y
    run virtualenv .ubuntu-venv
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install --upgrade pip
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install -r requirements.txt
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install -r test-requirements.txt
    run PATH=$(pwd)/.ubuntu-venv/bin:$PATH env pip install pylint pep8 flake8
    echo "CloudFerry setup succeeded!"
else
    echo "CloudFerry venv is already present, skipping"
fi
popd

popd
