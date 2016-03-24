#!/bin/bash
# Create two block devices needed for swift

set -x

sudo losetup /dev/loop0 /srv/swift_images/swift0.img
sudo losetup /dev/loop1 /srv/swift_images/swift1.img
sudo mount /dev/loop0 /srv/node/sdb1
sudo mount /dev/loop1 /srv/node/sdc1
