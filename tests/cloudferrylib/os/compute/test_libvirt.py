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
import mock

from cloudferrylib.os.compute import libvirt

from tests import test


class LibvirtTestCase(test.TestCase):
    def test_backing_file_returns_expected_value(self):
        qemu_img_info = """{
            "virtual-size": 41126400,
            "filename": "disk",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 1122304,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false
                }
            },
            "backing-filename": "/var/lib/nova/instances/_base/migrationDisk",
            "dirty-flag": false
        }"""
        remote_runner = mock.Mock()
        remote_runner.run.return_value = qemu_img_info
        lv = libvirt.Libvirt(remote_runner)
        backing_file = lv.get_backing_file('inst-id')
        self.assertEqual(backing_file,
                         "/var/lib/nova/instances/_base/migrationDisk")

    def test_backing_file_does_not_fail_if_json_has_no_such_file(self):
        json = """{
            "virtual-size": 7516192768,
            "filename": "/var/lib/nova/instances/6a475e2d-993a-453a-a8be-
                         b1ab549f54a7/disk",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 19398656,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false
                }
            },
            "dirty-flag": false
        }"""
        remote_runner = mock.Mock()
        remote_runner.run.return_value = json
        lv = libvirt.Libvirt(remote_runner)
        try:
            backing_file = lv.get_backing_file('inst-id')
            self.assertIsNone(backing_file)
        except:
            self.fail("get_backing_file should return None if backing file is "
                      "not present in qemu-img")

    def test_backing_file_returns_none_in_case_of_error(self):
        remote_runner = mock.Mock()
        remote_runner.run.return_value = None
        lv = libvirt.Libvirt(remote_runner)
        try:
            backing = lv.get_backing_file("some-id")
            self.assertIsNone(backing)
        except Exception:
            self.fail("get_backing_volume should return None in case of "
                      "failure")


grizzly_xml = """<domain type='qemu'>
  <name>instance-00000008</name>
  <uuid>7f9cfeab-05c6-4dcc</uuid>
  <memory unit='KiB'>524288</memory>
  <currentMemory unit='KiB'>524288</currentMemory>
  <vcpu placement='static'>1</vcpu>
  <sysinfo type='smbios'>
    <system>
      <entry name='manufacturer'>OpenStack Foundation</entry>
      <entry name='product'>OpenStack Nova</entry>
      <entry name='version'>2013.1.5</entry>
      <entry name='serial'>72827a02-9e88-41b9-82de-ec2ae162a93c</entry>
      <entry name='uuid'>7f9cfeab-05c6-4dcc</entry>
    </system>
  </sysinfo>
  <os>
    <type arch='x86_64' machine='pc-i440fx-trusty'>hvm</type>
    <boot dev='hd'/>
    <smbios mode='sysinfo'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-model'>
    <model fallback='allow'/>
  </cpu>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2' cache='none'/>
      <source file='/var/lib/nova/instances/7f9cfeab-05c6-4dcc/disk'/>
      <target dev='vda' bus='virtio'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x06' function='0x0'/>
    </disk>
    <controller type='usb' index='0'>
      <address type='pci' domain='0x0' bus='0x00' slot='0x01' function='0x2'/>
    </controller>
    <controller type='pci' index='0' model='pci-root'/>
    <interface type='bridge'>
      <mac address='fa:16:3e:62:33:5e'/>
      <source bridge='qbr77e94452-48'/>
      <target dev='tap77e94452-48'/>
      <model type='virtio'/>
      <driver name='qemu'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x03' function='0x0'/>
    </interface>
    <interface type='bridge'>
      <mac address='fa:16:3e:d2:0b:1f'/>
      <source bridge='qbrcec0ca6c-5b'/>
      <target dev='tapcec0ca6c-5b'/>
      <model type='virtio'/>
      <driver name='qemu'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x04' function='0x0'/>
    </interface>
    <interface type='bridge'>
      <mac address='fa:16:3e:31:ff:fc'/>
      <source bridge='qbrfc3ffd58-07'/>
      <target dev='tapfc3ffd58-07'/>
      <model type='virtio'/>
      <driver name='qemu'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x05' function='0x0'/>
    </interface>
    <serial type='file'>
      <source path='/var/lib/nova/instances/7f9cfeab-05c6-4dcc/console.log'/>
      <target port='0'/>
    </serial>
    <serial type='pty'>
      <target port='1'/>
    </serial>
    <console type='file'>
      <source path='/var/lib/nova/instances/7f9cfeab-05c6-4dcc/console.log'/>
      <target type='serial' port='0'/>
    </console>
    <input type='tablet' bus='usb'/>
    <input type='mouse' bus='ps2'/>
    <input type='keyboard' bus='ps2'/>
    <graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0' keymap='en'>
      <listen type='address' address='0.0.0.0'/>
    </graphics>
    <video>
      <model type='cirrus' vram='9216' heads='1'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x02' function='0x0'/>
    </video>
    <memballoon model='virtio'>
      <address type='pci' domain='0x0' bus='0x00' slot='0x07' function='0x0'/>
    </memballoon>
  </devices>
</domain>"""


icehouse_xml = """<domain type='qemu' id='4'>
  <name>instance-00000008</name>
  <uuid>7f9cfeab-05c6-4dcc</uuid>
  <memory unit='KiB'>524288</memory>
  <currentMemory unit='KiB'>524288</currentMemory>
  <vcpu placement='static'>1</vcpu>
  <resource>
    <partition>/machine</partition>
  </resource>
  <sysinfo type='smbios'>
    <system>
      <entry name='manufacturer'>OpenStack Foundation</entry>
      <entry name='product'>OpenStack Nova</entry>
      <entry name='version'>2013.1.5</entry>
      <entry name='serial'>72827a02-9e88-41b9-82de-ec2ae162a93c</entry>
      <entry name='uuid'>7f9cfeab-05c6-4dcc</entry>
    </system>
  </sysinfo>
  <os>
    <type arch='x86_64' machine='pc-i440fx-trusty'>hvm</type>
    <boot dev='hd'/>
    <smbios mode='sysinfo'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-model'>
    <model fallback='allow'/>
    <feature policy='require' name='rdtscp'/>
    <feature policy='require' name='ht'/>
    <feature policy='require' name='vme'/>
  </cpu>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2' cache='none'/>
      <source file='/var/lib/nova/instances/d7ca499b-42be-4234-beaf/disk'/>
      <target dev='vda' bus='virtio'/>
      <alias name='virtio-disk0'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x06' function='0x0'/>
    </disk>
    <controller type='usb' index='0'>
      <alias name='usb0'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x01' function='0x2'/>
    </controller>
    <controller type='pci' index='0' model='pci-root'>
      <alias name='pci.0'/>
    </controller>
    <interface type='bridge'>
      <mac address='fa:16:3e:62:33:5e'/>
      <source bridge='qbr4b1a363b-f6'/>
      <target dev='tap4b1a363b-f6'/>
      <model type='virtio'/>
      <driver name='qemu'/>
      <alias name='net0'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x03' function='0x0'/>
    </interface>
    <interface type='bridge'>
      <mac address='fa:16:3e:d2:0b:1f'/>
      <source bridge='qbrdb0f4c8f-28'/>
      <target dev='tapdb0f4c8f-28'/>
      <model type='virtio'/>
      <driver name='qemu'/>
      <alias name='net1'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x04' function='0x0'/>
    </interface>
    <interface type='bridge'>
      <mac address='fa:16:3e:31:ff:fc'/>
      <source bridge='qbr47d651c7-24'/>
      <target dev='tap47d651c7-24'/>
      <model type='virtio'/>
      <driver name='qemu'/>
      <alias name='net2'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x05' function='0x0'/>
    </interface>
    <serial type='file'>
      <source path='/var/lib/nova/instances/d7ca499b-42be-4234/console.log'/>
      <target port='0'/>
      <alias name='serial0'/>
    </serial>
    <serial type='pty'>
      <source path='/dev/pts/0'/>
      <target port='1'/>
      <alias name='serial1'/>
    </serial>
    <console type='file'>
      <source path='/var/lib/nova/instances/d7ca499b-42be-4234/console.log'/>
      <target type='serial' port='0'/>
      <alias name='serial0'/>
    </console>
    <input type='tablet' bus='usb'>
      <alias name='input0'/>
    </input>
    <input type='mouse' bus='ps2'/>
    <input type='keyboard' bus='ps2'/>
    <graphics type='vnc' port='59' autoport='yes' listen='0.0.0.0' keymap='en'>
      <listen type='address' address='0.0.0.0'/>
    </graphics>
    <video>
      <model type='cirrus' vram='9216' heads='1'/>
      <alias name='video0'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x02' function='0x0'/>
    </video>
    <memballoon model='virtio'>
      <alias name='balloon0'/>
      <address type='pci' domain='0x0' bus='0x00' slot='0x07' function='0x0'/>
    </memballoon>
  </devices>
  <seclabel type='dynamic' model='apparmor' relabel='yes'>
    <label>libvirt-7f9cfeab-05c6-4dcc</label>
    <imagelabel>libvirt-7f9cfeab-05c6-4dcc</imagelabel>
  </seclabel>
</domain>"""


class LibvirtXmlTestCase(test.TestCase):
    def test_returns_disk_file_from_xml(self):
        expected = ("/var/lib/nova/instances/"
                    "7f9cfeab-05c6-4dcc/disk")
        lxml = libvirt.LibvirtXml(grizzly_xml)
        self.assertIsInstance(lxml.disk_file, str)
        self.assertEqual(expected, lxml.disk_file)

    def test_updates_disk_file(self):
        lxml = libvirt.LibvirtXml(grizzly_xml)
        expected = "new value"
        lxml.disk_file = expected
        self.assertEqual(lxml.disk_file, expected)

    def test_interfaces_return_list(self):
        lxml = libvirt.LibvirtXml(grizzly_xml)
        self.assertIsInstance(lxml.interfaces, list)

    def test_console_file_allows_update(self):
        lxml = libvirt.LibvirtXml(grizzly_xml)
        self.assertIsInstance(lxml.console_file, str)
        self.assertEqual('/var/lib/nova/instances/7f9cfeab-05c6-4dcc/'
                         'console.log', lxml.console_file)
        expected = "new value"
        lxml.console_file = expected
        self.assertEqual(lxml.console_file, expected)

    def test_serial_file_allows_update(self):
        lxml = libvirt.LibvirtXml(grizzly_xml)
        expected = "new value"
        old_value = ("/var/lib/nova/instances/"
                     "7f9cfeab-05c6-4dcc/console.log")

        self.assertIsInstance(lxml.serial_file, str)
        self.assertEqual(lxml.serial_file, old_value)

        lxml.serial_file = expected
        self.assertIsInstance(lxml.serial_file, str)
        self.assertEqual(lxml.serial_file, expected)

    def test_updating_object_generates_correct_xml(self):
        src_vm_xml = libvirt.LibvirtXml(grizzly_xml)
        dst_vm_xml = libvirt.LibvirtXml(icehouse_xml)

        src_vm_xml.disk_file = dst_vm_xml.disk_file
        src_vm_xml.serial_file = dst_vm_xml.serial_file
        src_vm_xml.console_file = dst_vm_xml.console_file
        src_vm_xml.interfaces = dst_vm_xml.interfaces

        src_raw_xml = src_vm_xml.dump()

        lxml = libvirt.LibvirtXml(src_raw_xml)

        self.assertEqual(len(lxml.interfaces), len(dst_vm_xml.interfaces))
        for i in xrange(len(dst_vm_xml.interfaces)):
            self.assertEqual(lxml.interfaces[i], dst_vm_xml.interfaces[i])

        self.assertEqual(lxml.disk_file, dst_vm_xml.disk_file)
        self.assertEqual(lxml.serial_file, dst_vm_xml.serial_file)
        self.assertEqual(lxml.console_file, dst_vm_xml.console_file)


class InstanceDestroyerTestCase(test.TestCase):
    def test_instance_is_destroyed_from_nova_on_rollback(self):
        dest_libvirt = mock.Mock()
        dest_nova = mock.Mock()
        libvirt_instance_name = "instance name"
        nova_instance_id = "nova uuid"

        with libvirt.DestNovaInstanceDestroyer(dest_libvirt,
                                               dest_nova,
                                               libvirt_instance_name,
                                               nova_instance_id):
            pass

        dest_libvirt.destroy_vm.assert_called_once_with(libvirt_instance_name)
        dest_nova.reset_state.assert_called_once_with(nova_instance_id)
        dest_nova.delete_vm_by_id.assert_called_once_with(nova_instance_id)
