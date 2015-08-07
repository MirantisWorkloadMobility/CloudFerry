#!/bin/bash

# Prerequisites installation

set -x
set -e

source /home/vagrant/openstackrc
nova service-list
neutron agent-list
sudo /etc/init.d/dnsmasq restart
sleep 30
nova service-list
neutron agent-list
neutron agent-list | grep -v icehouse-cf-functional-tests- | grep xxx | awk '{print $2}' | xargs -I {} neutron agent-delete {}
initctl list | grep neutron | grep running | awk '{print $1}' | xargs -I {} sudo initctl restart {}
initctl list | grep nova | grep running | awk '{print $1}' | xargs -I {} sudo initctl restart {}
sleep 60
nova service-list
neutron agent-list
