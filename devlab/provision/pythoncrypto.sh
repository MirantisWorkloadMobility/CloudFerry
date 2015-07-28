#!/bin/bash

# Prerequisites installation

set -e

sudo apt-get update --fix-missing
sudo apt-get install build-essential libssl-dev libffi-dev python-dev -y

