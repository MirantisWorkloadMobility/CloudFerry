Introduction
============

Assumed Knowledge: You should be a Linux/Unix system administrator or
engineer with at least a passing familiarity with programming languages
(CF is written in Python), networking, databases, Unix text editors,
large scale storage appliances, RESTful applications and, of course,
substantial knowledge of and experience with OpenStack including at the
command line.

CloudFerry is a highly configurable tool and as such there are more ways
to use it than can be described in a brief document. This demo will
assist you in creating a pair of virtual OpenStack clouds, adding
tenants and configuring resources for you to migrate. 

In the real world it’s almost certain that since migration implys moving
workloads from one cloud environment to another that you’ll need to
perform a Condensation and Evacuation run prior to migration simply to
free up enough hardware to pull it off. Those 2 topics are not covered
in this document. 

**Before You Begin**
-----------------------
This guide is meant to get a demo of CloudFerry going. Normally it would be installed
on a host or VM which has network connectivity to the public IP's of both the source
and destination clouds. It's advised that this migration host be a Debian/Ubuntu
Linux distribution when doing real migrations or any significant testing.
 
The instructions below use the "nfs" VM as the migration host but it could equally
well be done directly from a Debian/Ubuntu or MacOS workstation. 

It is not recommended to use CentOS as your migration host. 

How-To: CloudFerry for Beginners
================================
**System Requirements**
-----------------------

1.  100GB free disk space as a minimum.
2.  CPU power to spare 5 cores.
3.  12GB free RAM (you should have 16GB total as a practical minimum)
4.  Internet access (for git clone).
5.  MacOS or Ubuntu Linux (or other Debian distribution) Operating
    System

**Setting Up CloudFerry Test Environment on MacOS**
-----------------------
1.  Download and install Vagrant http://www.vagrantup.com/downloads.html

2.  Download and install VirtualBox https://www.virtualbox.org/wiki/Downloads
    Open Terminal application and proceed.

3.  [user@MacOS ~/]$ ```mkdir ~/git```

4.  [user@MacOS ~/]$ ```cd ~/git```

5.  [user@MacOS ~/git]$ ```git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git```

6.  [user@MacOS ~/git]$ ```cd ~/git/CloudFerry/devlab```

7.  [user@MacOS ~/git/CloudFerry/devlab]$ ```vagrant up grizzly icehouse juno nfs```
    
    Open a new terminal window to watch logs.
    Copy SSH keys around to make your life easier.

8.  [user@MacOS ~/git/CloudFerry/devlab]$ ```cat ~/.ssh/id_rsa```

9.  [user@MacOS ~/git/CloudFerry/devlab]$ ```cat ~/.ssh/id_rsa.pub```

10. [user@MacOS ~/git/CloudFerry/devlab]$ ```vagrant ssh grizzly```

11. [user@MacOS ~/git/CloudFerry/devlab]$ ```vagrant ssh icehouse```

12. [user@MacOS ~/git/CloudFerry/devlab]$ ```vagrant ssh nfs```

    Now you have Vagrant managed VM's running in Virutalbox. 

13. [vagrant@nfs ~/]$ ```sudo apt-get install virtualbox python-dev python-virtualenv libffi-dev git -y```
    
    Clone the git repo on the CloudFerry server. Yes, the repo is cloned
    on both the nfs VM and on your local machine. Don't let that confuse
    you.

14. [vagrant@nfs ~/]$ ```git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git```

15. [vagrant@nfs ~/]$ ```cd CloudFerry```

16. [vagrant@nfs ~/CloudFerry]$ ```git fetch```

17. [vagrant@nfs ~/CloudFerry]$ ```git checkout -b devel origin/devel```
    
    Now we'll finish up some prep. pip version 6.1.1 is required so
    install that now.

18. [vagrant@nfs ~/CloudFerry]$ ```virtualenv .venv```

19. [vagrant@nfs ~/CloudFerry]$ ```source .venv/bin/activate```

20. [vagrant@nfs ~/CloudFerry]$ ```pip install pip==6.1.1```

21. [vagrant@nfs ~/CloudFerry]$ ```pip install --allow-all-external -r requirements.txt```

22. [vagrant@nfs ~/CloudFerry]$ ```pip install -r test-requirements.txt```
    
    We have the base bits almost ready. You do not want to generate a
    configuration.ini manually if at all possible, especially while
    you are learning. Instead we will auto-generate one. Edit config.ini
    and generate your configuration.ini using the generate_config.sh
    script.

23. [vagrant@nfs ~/CloudFerry]$ ```vi devlab/config.ini```

24. [vagrant@nfs ~/CloudFerry]$ ```./devlab/provision/generate_config.sh --cloudferry-path $(pwd)```
    
    You'll want to verify the configuration.ini file has the proper src
    and dst user and password (vagrant/vagrant is the user on the vm's)
    and the correct src and dst IP's.

25. [vagrant@nfs ~/CloudFerry]$ ```vi configuration.ini```

26. [vagrant@nfs ~/CloudFerry]$ ```source
    devlab/tests/openrc.example```
    
    We'll now make sure that the test environment we're working in is
    pristine and then create tenants, resources and workloads to
    migrate.

27. [vagrant@nfs ~/CloudFerry]$ ```python devlab/tests/generate_load.py –clean```

28. [vagrant@nfs ~/CloudFerry]$ ```python devlab/tests/generate_load.py```

29. [vagrant@nfs ~/CloudFerry]$ ```source .venv/bin/activate```
    
    Now you're ready to run the migration. If this is your first time
    you'll find the debug output enlightening if you read it.

30. [vagrant@nfs ~/CloudFerry]$ ```fab
    migrate:configuration.ini,debug=true```

The steps above will have set up a grizzly cloud on a VM and an icehouse
cloud on another and a cloudferry host on a third and migrate a tenant
from grizzly to icehouse. To explore more read the configuration.ini
that we created in step 24 above. The configuration.ini file is at 
~/git/Cloudferry/configuration. The grizzlycompute and icehousecompute
VM's don't appear to be used and so it might be a fun first task to try
and get a migration going between those two. You'll have to figure out
the IP's to change and then change them in devlab/config.ini before
running the generate_config.sh script again.

**CloudFerry Configuration Work**
---------------------------------

Read the config.ini and configuration.ini files and familiarize yourself
with them. IP's, ports, passwords, usernames, etc... for source and
destination clouds need to be provided. devlab/config.ini is used to
generate configuration.ini.

1.  [vagrant@nfs ~/CloudFerry]$ ```vi devlab/config.ini```

    This is the file is used by generate_config.sh script to generate configuration.ini for you.

2.  [vagrant@nfs ~/CloudFerry]$ ```vi configuration.ini```

**Hard Resetting Your Test Environment**
----------------------------------------

As with all testing of unfamiliar and highly customizable software it’s
predicted that you’ll blow up several test environments while you learn
how to use CloudFerry. That necessitates being able to reset your
environment quickly. Sometimes a soft reset will do but sometimes you
need to take off and nuke it from orbit. This will reset your Vagrant
VM's for Icehouse, Grizzly and CloudFerry to pristine. Once complete
repeat steps 7 onward from the Setting Up CloudFerry Test Environment on
MacOS Laptop section above.

1.  [MacOS ~/CloudFerry]$ ```cd devlab```

2.  [MacOS ~/CloudFerry/devlab]$ ```vagrant destroy grizzly icehouse juno nfs```

3.  [MacOS ~/CloudFerry/devlab]$ ```vagrant up grizzly icehouse juno nfs```

Proceed from step 8 above.


**Tips For Running CloudFerry Directly From Debian/Ubuntu**
----------------------------------------

If you are using Debian/Ubunt as your workstation rather than MacOS there are minor differences. The bulk of the process is the same but the following should help. Perform the following step instead of step 1 from the "Setting Up CloudFerry Test Environment on MacOS" instructions above.

1.  [user@Ubuntu ~/]$ ```sudo apt-get install python-dev build-essential libssl-dev python-virtualenv libffi-dev virualbox -y ; wget https://dl.bintray.com/mitchellh/vagrant/vagrant_1.7.2_x86_64.deb && sudo dpkg -i vagrant_1.7.2_x86_64.deb```

