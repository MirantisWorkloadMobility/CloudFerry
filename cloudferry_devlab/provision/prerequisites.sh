#!/bin/bash

# Prerequisites installation

set -e

sudo apt-get update --fix-missing
sudo apt-get install vim git nfs-common python-software-properties htop -y
