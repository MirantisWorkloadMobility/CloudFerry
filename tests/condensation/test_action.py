from tests import test
from condensation import action
import mock


class ActionTest(test.TestCase):

    def test_key_creation(self):
        """
            This test checks naming rule for action group
        """
        iteration = 4
        test_string = "test_string"
        a = action.Actions(test_string)
        a.iteration = iteration
        self.assertEqual("_".join([str(iteration), test_string]), a.key)

    def test_new_step(self):
        """
            This tests checks if action data reset to default after new step
        """
        a = action.Actions("")
        data = {}
        a.data = data
        a.new_step()
        self.assertNotEqual(a.data, data)

    def test_add_migration_action(self):
        a = action.Actions("")
        initial_length = len(a.data[action.MIGRATE])
        vm = mock.Mock(vm_id=u"uuid")
        target_node = mock.Mock()
        target_node.name = u"name"
        a.add_migration_action(vm, target_node)
        self.assertEqual(initial_length + 1, len(a.data[action.MIGRATE]))

    def test_add_transfer_action(self):
        a = action.Actions("")
        initial_length = len(a.data[action.TRANSFER])
        a.add_transfer_action(u"test")
        self.assertEqual(initial_length + 1, len(a.data[action.TRANSFER]))

    def test_condensation_action(self):
        a = action.Actions("")
        vm = mock.Mock(vm_id=u"uuid")
        source_node = mock.Mock()
        source_node.name = u"name"
        target_node = mock.Mock()
        target_node.name = u"name"
        initial_length = len(a.data[action.CONDENSE])
        a.add_condensation_action(vm, source_node, target_node)
        self.assertEqual(initial_length + 1, len(a.data[action.CONDENSE]))
