from tests import test
from cloudferry.condensation import vm
import mock


class VmTest(test.TestCase):

    def test_link_node(self):
        node = mock.Mock()
        node.link_vm = mock.Mock()
        flavor = mock.Mock()
        flavor.link_vm = mock.Mock()
        vm_obj = vm.Vm(node, "uuid", flavor)
        vm_obj.link_node(node)
        self.assertEqual(node, vm_obj.node)

    def test_link_flavor(self):
        node = mock.Mock()
        node.link_vm = mock.Mock()
        flavor = mock.Mock()
        flavor.link_vm = mock.Mock()
        vm_obj = vm.Vm(node, "uuid", flavor)
        vm_obj.link_flavor(flavor)
        self.assertEqual(flavor, vm_obj.flavor)
