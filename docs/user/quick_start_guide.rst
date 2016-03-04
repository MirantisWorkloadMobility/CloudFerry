=================
Quick Start Guide
=================

Following procedure allows one to dive into CloudFerry world in the quickest
possible manner.

1. Get CloudFerry sources::

    git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git
    cd CloudFerry
    git fetch
    # The latest code is in devel branch
    git checkout -b devel origin/devel

2. Install vagrant (devlab requires vagrant version >= 1.6)::

    wget https://dl.bintray.com/mitchellh/vagrant/vagrant_1.7.4_x86_64.deb
    sudo dpkg -i vagrant_1.7.4_x86_64.deb

3. Install virtualbox hypervisor::

    sudo apt-get install virtualbox -y

4. Setup development environment::

    cd CloudFerry/devlab
    vagrant up grizzly icehouse nfs

5. Setup virtual environment for cloudferry::

    apt-get install python-dev libssl-dev python-virtualenv libffi-dev -y
    cd CloudFerry
    virtualenv .venv
    source .venv/bin/activate
    pip install pip==7.1.2
    pip install -r requirements.txt
    pip install -r test-requirements.txt

6. Generate cloudferry config for development lab::

    cd CloudFerry
    ./devlab/provision/generate_config.sh --cloudferry-path $(pwd)

7. Generate load on source VM (this will create a number of VMs on grizzly
   node)::

    cd CloudFerry/
    source ./devlab/tests/openrc.example
    python ./devlab/generate_load.py --clean
    python ./devlab/generate_load.py

8. Run migration::

    cd CloudFerry
    source .venv/bin/activate
    fab migrate:configuration.ini,debug=True

