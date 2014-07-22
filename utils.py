from fabric.api import local, run
import os

__author__ = 'mirrorcoder'

ISCSI = "iscsi"
CEPH = "ceph"
BOOT_FROM_VOLUME = "boot_volume"
BOOT_FROM_IMAGE = "boot_image"
ANY = "any"
NOT_EPHEMERAL = "not_ephemeral"
EPHEMERAL = "ephemeral"
REMOTE_FILE = "remote file"
QCOW2 = "qcow2"


class forward_agent:

    """
        Forwarding ssh-key for access on to source and destination clouds via ssh
    """

    def __init__(self, key_file):
        self.key_file = key_file

    def __enter__(self):
            info_agent = local("eval `ssh-agent` && echo $SSH_AUTH_SOCK && ssh-add %s" % (self.key_file), capture=True).split("\n")
            self.pid = info_agent[0].split(" ")[-1]
            self.ssh_auth_sock = info_agent[1]
            os.environ["SSH_AGENT_PID"] = self.pid
            os.environ["SSH_AUTH_SOCK"] = self.ssh_auth_sock

    def __exit__(self, type, value, traceback):
        local("kill -9 %s"%(self.pid))
        del os.environ["SSH_AGENT_PID"]
        del os.environ["SSH_AUTH_SOCK"]


class up_ssh_tunnel:

    """
        Up ssh tunnel on dest controller node for transferring data
    """

    def __init__(self, address_dest_compute, address_dest_controller):
        self.address_dest_compute = address_dest_compute
        self.address_dest_controller = address_dest_controller
        self.cmd = "ssh -oStrictHostKeyChecking=no -L 9999:%s:22 -R 9999:localhost:9999 %s -Nf"

    def __enter__(self):
        run(self.cmd % (self.address_dest_compute, self.address_dest_controller))

    def __exit__(self, type, value, traceback):
        run(("pkill -f '"+self.cmd+"'") % (self.address_dest_compute, self.address_dest_controller))


class ChecksumImageInvalid(Exception):
    def __init__(self, checksum_source, checksum_dest):
        self.checksum_source = checksum_source
        self.checksum_dest = checksum_dest

    def __str__(self):
        return repr("Checksum of image source = %s Checksum of image dest = %s" %
                    (self.checksum_source, self.checksum_dest))