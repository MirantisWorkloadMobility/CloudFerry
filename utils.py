from fabric.api import local, run
import os

__author__ = 'mirrorcoder'


class forward_agent:
    def __init__(self, key_file):
        self.key_file = key_file

    def __enter__(self):
            info_agent = local("eval `ssh-agent` && echo $SSH_AUTH_SOCK && ssh-add %s"%(self.key_file), capture=True).split("\n")
            self.pid = info_agent[0].split(" ")[-1]
            self.ssh_auth_sock = info_agent[1]
            os.environ["SSH_AGENT_PID"] = self.pid
            os.environ["SSH_AUTH_SOCK"] = self.ssh_auth_sock

    def __exit__(self, type, value, traceback):
        local("kill -9 %s"%(self.pid))
        del os.environ["SSH_AGENT_PID"]
        del os.environ["SSH_AUTH_SOCK"]


class up_ssh_tunnel:
    def __init__(self, address_dest_compute, address_dest_controller):
        self.address_dest_compute = address_dest_compute
        self.address_dest_controller = address_dest_controller
        self.cmd = "ssh -oStrictHostKeyChecking=no -L 9999:%s:22 -R 9999:localhost:9999 %s -Nf"

    def __enter__(self):
        run(self.cmd % (self.address_dest_compute, self.address_dest_controller))

    def __exit__(self, type, value, traceback):
        run(("pkill -f '"+self.cmd+"'") % (self.address_dest_compute, self.address_dest_controller))

# def test(source_cnt):
#     with settings(host_string=source_cnt):
# 	    with forward_agent("privkey"):
# 		    with up_ssh_tunnel("node-17", "172.18.172.22"):
# 			    run("ssh -oStrictHostKeyChecking=no node-15 'dd bs=1M if=/var/lib/nova/instances/82a5dd60-f02e-4e14-a540-6e3dd1b73a01/disk' | ssh -oStrictHostKeyChecking=no -p 9999 localhost 'dd bs=1M of=/root/disk_test_new'")