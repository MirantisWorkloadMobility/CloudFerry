from tests import test
from condensation import flavor
import mock


class FlavorTest(test.TestCase):

    def test_reduce_resources(self):
        ram, core = 100, 20
        ram_factor, core_factor = 5, 2
        fl = flavor.Flavor("2", "tiny", ram, core)
        fl.reduce_resources(ram_factor, core_factor)
        self.assertEqual(ram / ram_factor, fl.reduced_ram)
        self.assertEqual(core / core_factor, fl.reduced_core)

    def test_link_vm(self):
        fl = flavor.Flavor("2", "tiny", 100, 20)
        initial_length = len(fl.vms)
        vm = mock.Mock()
        fl.link_vm(vm)
        self.assertEqual(initial_length + 1, len(fl.vms))
