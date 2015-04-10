#!/bin/bash -e
#
# 1. Remove vagrant-assigned static IP from /etc/network/interfaces;
# 2. Put insecure vagrant SSH key for vagrant and root users;
# 3. Repackage box
#

SCRIPT=$(basename 0)

error_exit() {
    echo $* 1>&2
    echo 1>&2
    echo "Usage: $SCRIPT --box <box name> [-f, --force]" 1>&2

    exit 1
}

while [[ $# -ge 1 ]]; do
    case $1 in
        -f | --force)
            shift
            forced=1
            ;;
        --box)
            shift
            box=$1
            shift
            ;;
        *) error_exit "Invalid arg $1";;
    esac
done

if [[ -z $box || $box -ne 'grizzly' || $box -ne 'icehouse' ]]; then
    error_exit "Invalid box name provided: '$box'. Should be one of 'grizzly' or 'icehouse'."
fi

ssh_config=$(vagrant ssh-config $box)
ssh_host=$(echo "$ssh_config" | grep HostName | cut -d' ' -f4)
ssh_port=$(echo "$ssh_config" | grep Port | cut -d' ' -f4)
ssh_private_key=$(echo "$ssh_config" | grep IdentityFile | cut -d' ' -f4)
ssh_user=$(echo "$ssh_config" | grep '\<User\>' | cut -d' ' -f4)
ssh_users_private_key=~/.ssh/id_rsa.pub
ssh_opts='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'

insecure_pub_key=~/.vagrant.d/vagrant.pub
insecure_private_key=~/.vagrant.d/insecure_private_key

ssh_cmd() {
    local private_key=$1
    local cmd=$2

    ssh $ssh_user@$ssh_host -p $ssh_port -i $private_key $ssh_opts $cmd
}

# remove vagrant-assigned static IP
ssh_cmd $ssh_private_key 'sudo sed -i "/^#VAGRANT-BEGIN/,\$d" /etc/network/interfaces'
ssh_cmd $ssh_private_key "echo \"$(cat $insecure_pub_key)\" > ~/.ssh/authorized_keys"
ssh_cmd $insecure_private_key "echo \"$(cat $insecure_pub_key)\" | sudo tee /root/.ssh/authorized_keys"

vm_name=$(VBoxManage list runningvms | grep $box | head -1 | cut -d' ' -f1 | sed 's/"//g')

echo "Shutting down $box VM"
VBoxManage controlvm $vm_name poweroff

if [[ ! $forced ]]; then
    read -p "Please verify the VM name: $vm_name " vm_name_from_user
    if [[ -n $vm_name_from_user ]]; then
        vm_name=$vm_name_from_user
    fi
fi

echo "Vagrant box packaging started for $box (VirtualBox VM name is $vm_name)"
vagrant package --base $vm_name --output ${box}.box

