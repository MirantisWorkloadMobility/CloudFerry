# Test module. Delete when it is any useful unittest


from tests import test


def answer():
    """
    The answer to the ultimate question of life the universe and everything.
    """
    return 42


class ExampleTestCase(test.TestCase):
    def setUp(self):
        super(ExampleTestCase, self).setUp()
        # some setup

    def test_first_unittest(self):
        # some actions
        self.assertEqual(42, answer())

    def test_second_unittest(self):
        # some another actions
        self.assertIn(3, [1, 2, 3, 4])
        self.assertNotIn('5', 'hello_cloudferry1234')
