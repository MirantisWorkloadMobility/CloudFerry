#!/bin/bash

set -e
set -x

export CF_DIR=${HOME}/cloudferry

cd ${CF_DIR}

echo "Activate python venv..."
source .venv/bin/activate

source ${CF_DIR}/devlab/tests/openrc.example
echo "Preparing configuration for CloudFerry"
cd ${CF_DIR}
devlab/provision/generate_config.sh --cloudferry-path "$CF_DIR"

echo "Run migration"
fab migrate:configuration.ini,debug=True
