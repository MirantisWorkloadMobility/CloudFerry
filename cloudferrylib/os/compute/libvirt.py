# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import os

from xml.etree import ElementTree

from cloudferrylib.utils import log

LOG = log.getLogger(__name__)

nova_instances_path = "/var/lib/nova/instances/"


def instance_path(instance_id):
    return os.path.join(nova_instances_path, instance_id)


def instance_image_path(instance_id):
    return os.path.join(instance_path(instance_id), "disk")


def _qemu_img_rebase(src, dst):
    return "qemu-img rebase -b {src} {dst}".format(src=src, dst=dst)


class QemuBackingFileMover(object):
    def __init__(self, runner, src, instance_id):
        self.runner = runner
        self.src = src
        self.dst = instance_image_path(instance_id)

    def __enter__(self):
        cmd = _qemu_img_rebase(self.src, self.dst)
        self.runner.run(cmd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        cmd = _qemu_img_rebase(self.dst, self.src)
        self.runner.run_ignoring_errors(cmd)
        return self


class DestNovaInstanceDestroyer(object):
    """Fake instance is destroyed from libvirt as part of live migration. In
    case something fails during live migration, this action must be rolled
    back. The only valid rollback scenario is to delete the same instance from
    nova DB."""

    def __init__(self, dest_libvirt, dest_nova, libvirt_name, nova_vm_id):
        self.dest_libvirt = dest_libvirt
        self.dest_nova = dest_nova
        self.libvirt_name = libvirt_name
        self.nova_vm_id = nova_vm_id

    def __enter__(self):
        self.do()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.undo()

    def do(self):
        self.dest_libvirt.destroy_vm(self.libvirt_name)

    def undo(self):
        try:
            LOG.debug("Rolling back fake VM %s", self.nova_vm_id)
            self.dest_nova.reset_state(self.nova_vm_id)
            self.dest_nova.delete_vm_by_id(self.nova_vm_id)
        except:
            # ignoring all errors since it's a rollback
            pass


class Libvirt(object):
    def __init__(self, remote_runner):
        """
        :remote_runner: `cloudferrylib.utils.remote_runner.RemoteRunner` object
        """
        self.runner = remote_runner

    def get_backing_file(self, instance_id):
        cmd = ("qemu-img info {image_path} --output json".format(
            image_path=instance_image_path(instance_id)))

        try:
            image_info = json.loads(self.runner.run(cmd))
            return image_info['backing-filename']
        except (ValueError, TypeError) as e:
            LOG.error("Invalid value received from qemu: %s!", e)
        except KeyError:
            LOG.warning("Instance '%s' does not have backing file associated!",
                        instance_id)

    def get_xml(self, libvirt_instance_name):
        cmd = ("virsh dumpxml {inst_name}".format(
            inst_name=libvirt_instance_name))

        return LibvirtXml(self.runner.run(cmd))

    def destroy_vm(self, libvirt_instance_name):
        cmds = [
            "virsh destroy {instance}".format(instance=libvirt_instance_name),
            "virsh undefine {instance}".format(instance=libvirt_instance_name)
        ]
        for cmd in cmds:
            self.runner.run(cmd)

    def move_backing_file(self, source_file, instance_id):
        cmd = _qemu_img_rebase(src=source_file,
                               dst=instance_image_path(instance_id))
        self.runner.run(cmd)

    def live_migrate(self, libvirt_instance_name, dest_host, migration_xml):
        cmd = ("virsh migrate --live --copy-storage-all --verbose {instance} "
               "qemu+tcp://{dst_host}/system "
               "--xml {migration_xml}".format(instance=libvirt_instance_name,
                                              dst_host=dest_host,
                                              migration_xml=migration_xml))
        self.runner.run(cmd)


class LibvirtDeviceInterfaceHwAddress(object):
    def __init__(self, element):
        self.type = element.get('type')
        self.domain = element.get('domain')
        self.bus = element.get('bus')
        self.slot = element.get('slot')
        self.function = element.get('function')

    def __repr__(self):
        return "HW Address<%s %s %s>" % (self.type, self.bus, self.slot)

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.type == other.type and
                self.domain == other.domain and
                self.bus == other.bus and
                self.slot == other.slot and
                self.function == other.function)


class LibvirtDeviceInterface(object):
    def __init__(self, interface):
        """
        :interface: - `xml.etree.ElementTree.Element` object
        """
        self._xml_element = interface
        self.mac = interface.find('mac').get('address')
        self.source_iface = interface.find('source').get('bridge')
        self.target_iface = interface.find('target').get('dev')
        self.hw_address = LibvirtDeviceInterfaceHwAddress(
            interface.find('address'))

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.source_iface == other.source_iface and
                self.target_iface == other.target_iface and
                self.hw_address == other.hw_address)

    def __repr__(self):
        return "Iface<mac={mac}, src={src}, dst={dst}>".format(
            mac=self.mac, src=self.source_iface, dst=self.target_iface)

    @classmethod
    def _replace_attr(cls, element, attr, value):
        if element.get(attr) != value:
            element.clear()
            element.attrib = {attr: value}

    def element(self):
        source = self._xml_element.find('source')
        target = self._xml_element.find('target')

        self._replace_attr(source, 'bridge', self.source_iface)
        self._replace_attr(target, 'dev', self.target_iface)

        return self._xml_element


class LibvirtXml(object):
    def __init__(self, contents):
        """
        :contents - XML file contents (text)
        """
        self._xml = ElementTree.fromstring(contents)
        self._interfaces = map(LibvirtDeviceInterface,
                               self._xml.findall('.//devices/interface'))
        self.disk_file = self._get('.//disk/source', 'file')
        self.serial_file = self._get('.//serial/source', 'path')
        self.console_file = self._get('.//console/source', 'path')

    def _get(self, element, attribute):
        el = self._xml.find(element)
        if el is not None:
            return el.get(attribute)

    def _set(self, element, attribute, value):
        el = self._xml.find(element)
        if el is not None:
            el.set(attribute, value)

    @property
    def interfaces(self):
        return self._interfaces

    @interfaces.setter
    def interfaces(self, other):
        """Only <source bridge/> and <target dev/> elements must be updated"""
        if len(self.interfaces) != len(other):
            raise RuntimeError("Source and dest have different number of "
                               "network interfaces allocated.")

        for other_iface in other:
            for this_iface in self.interfaces:
                identical = (this_iface.mac == other_iface.mac)
                if identical:
                    this_iface.source_iface = other_iface.source_iface
                    this_iface.target_iface = other_iface.target_iface
                    break

    def dump(self):
        self._set('.//disk/source', 'file', self.disk_file)
        self._set('.//serial/source', 'path', self.serial_file)
        self._set('.//console/source', 'path', self.console_file)

        xml_devices = self._xml.find('.//devices')
        xml_interfaces = self._xml.findall('.//devices/interface')
        for iface in xml_interfaces:
            xml_devices.remove(iface)

        for iface in self._interfaces:
            xml_devices.append(iface.element())

        return ElementTree.tostring(self._xml)
