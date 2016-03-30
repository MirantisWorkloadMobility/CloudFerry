from tests import test
from cloudferry.condensation import group
import mock


class GroupTest(test.TestCase):

    def test_add_groups(self):
        num = 4
        groups_to_be_added = [mock.Mock() for _ in range(num)]
        g = group.Group()
        initial_length = len(g.children)
        g.add_groups(groups_to_be_added)
        self.assertEqual(initial_length + num, len(g.children))

    def test_add_vms(self):
        num = 5
        vms_to_be_added = {i: mock.Mock() for i in range(5)}
        g = group.Group()
        initial_length = len(g.vms)
        g.add_vms(vms_to_be_added)
        self.assertEqual(initial_length + num, len(g.vms))

    def test_get_all_vms(self):
        # check type
        g = group.Group()
        self.assertEqual(list, type(g.get_all_vms()))

    def test_capacity(self):
        g = group.Group()
        self.assertEqual(tuple, type(g.capacity))

    def test_parent_count(self):
        g = group.Group()
        self.assertEqual(int, type(g.parent_count()))
