#!/bin/bash
# Prerequisites installation
set -e
sudo apt-get install build-essential libssl-dev libffi-dev python-dev zlib1g-dev -y

# install the latest version of bbcp
wget http://www.slac.stanford.edu/~abh/bbcp/bbcp.tgz
tar xvfz bbcp.tgz
cd bbcp/src
make
ls /home/vagrant/bbcp/bin/amd64_linux/bbcp
