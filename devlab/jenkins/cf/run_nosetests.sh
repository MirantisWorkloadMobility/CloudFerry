#!/bin/bash

set -e
set -x

export CF_DIR=${HOME}/cloudferry

cd ${CF_DIR}

echo "Activate python venv..."
source .venv/bin/activate

source ${CF_DIR}/devlab/tests/openrc.example

cd ${CF_DIR}/devlab/tests
echo 'Run tests'
set +e
nosetests -d -v --with-xunit
set -e
