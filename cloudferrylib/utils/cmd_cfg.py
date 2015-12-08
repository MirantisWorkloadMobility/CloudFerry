# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.


from cloudferrylib.utils.console_cmd import BC


cd_cmd = BC("cd %s")
qemu_img_cmd = BC("qemu-img %s")
mkdir_cmd = BC("mkdir -p %s")
move_cmd = BC("mv -f %s %s")
move_with_cd_cmd = cd_cmd & move_cmd
rbd_cmd = BC("rbd %s")
base_ssh_cmd = BC("ssh %s")
ssh_cmd = base_ssh_cmd("-oStrictHostKeyChecking=no %s '%s'")
ssh_cmd_port = base_ssh_cmd("-oStrictHostKeyChecking=no -p %s %s '%s'")
dd_cmd_of = BC("dd bs=%s of=%s")
dd_cmd_if = BC("dd bs=%s if=%s")
dd_full = BC('dd if=%s of=%s bs=%s count=%s seek=%sM')
gunzip_cmd = BC("gunzip")
gzip_cmd = BC("gzip -%s -c %s")
scp_cmd = BC('scp %s -o StrictHostKeyChecking=no %s %s@%s:%s %s')
rm_cmd = BC('rm -f %s')
