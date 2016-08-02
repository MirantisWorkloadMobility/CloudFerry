#!/usr/bin/env bash

set -e
set -x

NEW_USERNAME=$1
PASSWORD=$2

sudo useradd -m -s /bin/bash -G sudo -U "${NEW_USERNAME}"
echo "${NEW_USERNAME}:${PASSWORD}" | sudo chpasswd

