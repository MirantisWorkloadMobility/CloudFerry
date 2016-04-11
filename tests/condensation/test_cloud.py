from tests import test
from cloudferry.condensation import cloud
import mock


class CloudTest(test.TestCase):

    def test_add_nodes(self):
        test_dict = {i: mock.Mock() for i in range(5)}
        c = cloud.Cloud("test")
        c.add_nodes(test_dict)
        self.assertEqual(c.nodes, test_dict)
