# CloudFerry Development Lab

## Overview

This allows for setting up a development lab environment using
[Vagrant](http://www.vagrantup.com/downloads.html).

## Lab Description

Vagrant sets up 5 nodes:
 - Openstack Grizzly all-in-one node on Ubuntu 12.04;
 - Openstack Grizzly compute node on Ubuntu 12.04;
 - Openstack Icehouse all-in-one node on Ubuntu 12.04;
 - Openstack Icehouse compute node on Ubuntu 12.04;
 - Openstack Juno all-in-one node on Ubuntu 14.04;
 - CloudFerry node on Ubuntu 12.04
   - Creates a user with the same name as the one running vagrant;
   - Mounts user's $HOME in VMs $HOME so that user has familiar working
     environment and full access to host data.

## Configuration

Configuration is done through modifying `config.ini`. Most recent configurable
options:

 - `public_key_path` -- public key CloudFerry uses to ssh into SRC and DST
   migration environments;
 - `ENV['VIRTUALBOX_NETWORK_NAME']` -- Optional variable which allows you to
   specify private virtual vbox network.

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
    or
    ```
    vagrant up grizzly juno
    ```
 5. At some point vagrant will ask you for the password, this is needed to
    configure NFS export on your host system.
 6. You also can start minimum development environment by running:
    ```
    vagrant up grizzly icehouse cloudferry
    ```

## Common Vagrant use-cases

 1. Check current VMs state (whether it's up, down and so on)
   - `vagrant status`
 2. SSH
   - `vagrant ssh <vm name>`
   - `<vm name>` is one of grizzly, icehouse or cloudferry
 3. SSH configuration used for each VM:
   - `vagrant ssh-config <vm name>`
 4. If something went wrong and you cannot ssh with keypairs, all the VMs have
    following users:
   - Username: vagrant
   - Password: vagrant
 5. `vagrant` user is added to paswordless sudoers, so you can easily become
    root:
   - `sudo su`

## CloudFerry usage

 1. Connect to 'cloudferry' node:
    ```
    vagrant ssh cloudferry
    ```
 2. Move to directory with CloudFerry and activate virtual environment:
    ```
    cd <cloud_ferry_dir>
    source .ubuntu-venv/bin/activate
    ```
 3. Run migration process:
    ```
    fab migrate:configuration.ini
    ```

## Known Issues

 - Windows is *not* supported due to NFS dependency;
 - In rare cases OSX users may experience problems due to OSX filesystem case
   insensitivity.
