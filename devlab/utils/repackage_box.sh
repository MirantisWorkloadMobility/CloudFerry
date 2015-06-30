#!/bin/bash -e
#
# 1. Remove vagrant-assigned static IP from /etc/network/interfaces;
# 2. Put insecure vagrant SSH key for vagrant and root users;
# 3. Repackage box
#

SCRIPT=$(basename $0)

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

if [[ -z $box || "$box" != 'grizzly' && "$box" != 'grizzlycompute' && "$box" != 'icehouse' && "$box" != 'icehousecompute' ]]; then
    error_exit "Invalid box name provided: '$box'. Should be one of 'grizzly' or 'icehouse' or 'grizzlycompute' or 'icehousecompute' ."
fi

ssh_config=$(vagrant ssh-config $box)
ssh_host=$(echo "$ssh_config" | grep HostName | cut -d' ' -f4)
ssh_port=$(echo "$ssh_config" | grep Port | cut -d' ' -f4)
ssh_private_key=$(echo "$ssh_config" | grep IdentityFile | cut -d' ' -f4)
ssh_user=$(echo "$ssh_config" | grep '\<User\>' | cut -d' ' -f4)
ssh_opts='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR'

insecure_pub_key=~/.vagrant.d/vagrant.pub
insecure_private_key=~/.vagrant.d/insecure_private_key

if [[ ! -f $insecure_pub_key ]]; then
    ssh-keygen -f $insecure_private_key -y > $insecure_pub_key
fi

ssh_cmd() {
    local private_key="$1"
    local cmd="$2"

    ssh $ssh_user@$ssh_host -p $ssh_port -i $private_key $ssh_opts "$cmd"
}

# grizzly box has eth1 udev rules which must be flushed
# to correctly assign eth device index on boot
# Icehouse box doesn't have this because it runs more recent Ubuntu
if [[ $box == 'grizzly' || $box == 'grizzlycompute' ]]; then
    grizzly_mac_re='([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
    grizzly_eth1_mac=$(ssh_cmd $ssh_private_key "ip link show eth1 | sed -r -n 's/.*\<$grizzly_mac_re\>.*/\1/p'")
    echo "Removing $grizzly_eth1_mac from udev net rules"
    ssh_cmd $ssh_private_key "sudo sed -i -r '/$grizzly_eth1_mac/d' /etc/udev/rules.d/70-persistent-net.rules"
fi

# remove vagrant-assigned static IP
echo "Removing static configuration for eth1 network interface"
ssh_cmd $ssh_private_key 'sudo sed -i "/^#VAGRANT-BEGIN/,\$d" /etc/network/interfaces'
echo "Updating authorized keys for vagrant user"
ssh_cmd $ssh_private_key "echo '$(cat $insecure_pub_key)' > ~/.ssh/authorized_keys"
echo "Updating authorized keys for root user"
ssh_cmd $insecure_private_key "echo '$(cat $insecure_pub_key)' | sudo tee /root/.ssh/authorized_keys >/dev/null"

vagrant_key_updated=$(ssh_cmd $insecure_private_key "grep insecure ~/.ssh/authorized_keys")
if [[ $? != 0 || ! $vagrant_key_updated ]]; then
    error_exit "Something went wrong during SSH keys substitution. Please check your box. Packaging will be aborted"
fi

echo "Writing caches to disk"
ssh_cmd $insecure_private_key "sync"

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

packaged_box_name=${box}-$(date +%d%m%y_%H%M%S).box
vagrant package --base $vm_name --output $packaged_box_name

