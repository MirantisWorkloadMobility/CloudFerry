import mock

from cloudferry.cfglib import CONF
from cloudferry.condensation import node
from tests import test

# patch settings
CONF.condense = mock.Mock(
    core_reduction_coef=1,
    ram_reduction_coef=1
)


class NodeTest(test.TestCase):

    def test_link_vm(self):
        num = 3
        vms = [mock.Mock(id=i) for i in range(3)]
        n = node.Node(*range(7))
        initial_length = len(n.vms)
        map(n.link_vm, vms)
        self.assertEqual(initial_length + num, len(n.vms))

    def test_is_full(self):
        n = node.Node(*range(1, 8))
        self.assertEqual(bool, type(n.is_full))

    def test_free_resources(self):
        n = node.Node(*range(1, 8))
        self.assertEqual(tuple, type(n.free_resources))

    def test_utilization(self):
        n = node.Node(*range(1, 8))
        self.assertEqual(tuple, type(n.utilization))

    def test_potential_utilization(self):
        n = node.Node(*range(1, 8))
        self.assertEqual(tuple, type(n.potential_utilization({})))

    def test_calculate_flavors_required(self):
        n = node.Node(*range(1, 8))
        self.assertEqual(dict, type(n.calculate_flavors_required({})))
