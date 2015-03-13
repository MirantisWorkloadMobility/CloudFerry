# CloudFerry Development Lab

## Overview

This allows for setting up a development lab environment using
[Vagrant](http://www.vagrantup.com/downloads.html).

## Lab Description

Vagrant sets up 3 nodes:
 - Openstack Grizzly all-in-one node on Ubuntu 12.04;
 - Openstack Icehouse all-in-one node on Ubuntu 12.04;
 - CloudFerry node on Ubuntu 12.04
   - Creates a user with the same name as the one running vagrant;
   - Mounts user's $HOME in VMs $HOME so that user has familiar working
     environment and full access to host data.

## Configuration

Configuration is done through modifying `Vagrantfile`. Configurable options:

 - `public_key_path` -- public key CloudFerry uses to ssh into SRC and DST
   migration environments;
 - `cloudferry_path` -- Path to CloudFerry sources. If sources are not present,
   this is the path where the sources will be cloned to.

## Prerequisites

 - Vagrant, version >= 1.6
 - Virtualbox
 - NFS server

## Setup

 1. Make sure you have all prerequisites installed;
 2. Clone [CloudFerry](https://github.com/MirantisWorkloadMobility/CloudFerry)
    repository and navigate to `devlab` folder
    ```
    git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git
    cd CloudFerry/devlab
    ```
 3. Configure according to your needs (see Configuration)
 4. Start vagrant
    ```
    vagrant up
    ```
 5. At some point vagrant will ask you for the password, this is needed to
    configure NFS export on your host system.

## Known Issues

 - Windows is *not* supported due to NFS dependency;
 - In rare cases OSX users may experience problems due to OSX filesystem case
   insensitivity.
