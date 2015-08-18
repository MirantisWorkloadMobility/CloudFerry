#!/bin/bash -ex

export CF_DIR=${HOME}/CloudFerry

cd ${CF_DIR}
echo "Create python venv..."
virtualenv --clear .venv
source .venv/bin/activate
pip install pip==6.1.1
pip install --allow-all-external -r requirements.txt -r test-requirements.txt

cd ${CF_DIR}/devlab/tests
echo "Clean load..."
source openrc.example
python generate_load.py --clean --env DST
python generate_load.py --clean --env DST
python generate_load.py --clean --env SRC
python generate_load.py --clean --env SRC

python generate_load.py
echo 'Openstack resources for source cloud have been successfully created.'
