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

from cloudferrylib.utils import qemu_img

from tests import test


class FakeQemuImgInfoParser(qemu_img.QemuImgInfoParser):
    def parse(self, img_info_output):
        return img_info_output


class QemuImgInfoParserTestCase(test.TestCase):
    def setUp(self):
        super(QemuImgInfoParserTestCase, self).setUp()
        self.info = {'format': 'fake_format',
                     'backing-filename': 'fake_filename'}
        self.parser = FakeQemuImgInfoParser(self.info)

    def test_info(self):
        self.assertEqual(self.info, self.parser.info)

    def test_backing_filename(self):
        self.assertEqual('fake_filename', self.parser.backing_filename)

    def test_none_backing_filename(self):
        del(self.parser.info['backing-filename'])
        self.assertIsNone(self.parser.backing_filename)

    def test_format(self):
        self.assertEqual('fake_format', self.parser.format)


class JsonQemuImgInfoParserTestCase(test.TestCase):
    def setUp(self):
        super(JsonQemuImgInfoParserTestCase, self).setUp()
        m = mock.patch('json.loads', return_value='fake')
        self.loads = m.start()
        self.addCleanup(m.stop)
        self.parser = qemu_img.JsonQemuImgInfoParser('fake_output')

    def test_parse(self):
        self.loads.assert_called_once_with('fake_output')
        self.assertEqual('fake', self.parser.info)


class TextQemuImgInfoParserTestCase(test.TestCase):

    def test_backing_file_without_actual_path_gets_parsed(self):
        expected_backing_file = '/path/to/backing/file'

        qemu_img_output = """
        image: disk
        file format: qcow2
        virtual size: 39M (41126400 bytes)
        disk size: 712K
        cluster_size: 65536
        backing file: {backing_file}
        Format specific information:
            compat: 1.1
            lazy refcounts: false
        """.format(backing_file=expected_backing_file)

        actual = (qemu_img.TextQemuImgInfoParser(qemu_img_output).
                  backing_filename)

        self.assertEqual(expected_backing_file, actual)

    def test_backing_file_with_actual_path_gets_parsed(self):
        expected_backing_file = '/path/to/backing/file'
        actual_path = '/some/other/path/to/backing/file'

        qemu_img_output = """
        image: disk
        file format: qcow2
        virtual size: 39M (41126400 bytes)
        disk size: 712K
        cluster_size: 65536
        backing file: {backing_file} (actual path: {actual_path})
        Format specific information:
            compat: 1.1
            lazy refcounts: false
        """.format(backing_file=expected_backing_file, actual_path=actual_path)

        actual = (qemu_img.TextQemuImgInfoParser(qemu_img_output).
                  backing_filename)

        self.assertEqual(expected_backing_file, actual)

    def test_returns_none_in_case_of_error(self):
        unexpected_output = """
        some unexpected
        items here
        to test
        """

        actual = (qemu_img.TextQemuImgInfoParser(unexpected_output).
                  backing_filename)

        self.assertIsNone(actual)

    def test_parses_path_with_whitespaces(self):
        expected_backing_file = '/path/to/backing/file with whitespace'
        actual_path = '/some/other/path/to/backing with whitespace/file'

        qemu_img_output = """
        image: disk
        file format: qcow2
        virtual size: 39M (41126400 bytes)
        disk size: 712K
        cluster_size: 65536
        backing file: {backing_file} (actual path: {actual_path})
        Format specific information:
            compat: 1.1
            lazy refcounts: false
        """.format(backing_file=expected_backing_file, actual_path=actual_path)

        actual = (qemu_img.TextQemuImgInfoParser(qemu_img_output).
                  backing_filename)

        self.assertEqual(expected_backing_file, actual)


class QemuImgCommandsTestCase(test.TestCase):
    @mock.patch("cloudferrylib.utils.qemu_img.QemuImg.execute")
    def test_backing_file_returns_none_if_not_available(self, _):
        cloud = mock.Mock()
        config = mock.Mock()
        host = mock.Mock()
        ephemeral = mock.Mock()

        qi = qemu_img.QemuImg(cloud, config, host)
        backing_file = qi.detect_backing_file(ephemeral, host)
        self.assertIsNone(backing_file)

    @mock.patch("cloudferrylib.utils.qemu_img.QemuImg.execute")
    def test_backing_file_returned_for_good_ephemeral(self, mock_execute):
        cloud = mock.Mock()
        config = mock.Mock()
        host = "host1"
        ephemeral = "disk"
        expected_backing = "/path/to/backing/file"

        # dict is based on the actual output of qemu-img utility
        mock_execute.return_value = """{{
            "virtual-size": 1073741824,
            "filename": "disk",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 1974272,
            "format-specific": {{
                "type": "qcow2",
                "data": {{
                    "compat": "1.1",
                    "lazy-refcounts": false
                }}
            }},
            "backing-filename": "{backing_file}",
            "dirty-flag": false
        }}""".format(backing_file=expected_backing)

        qi = qemu_img.QemuImg(cloud, config, host)

        actual_backing = qi.detect_backing_file(ephemeral, host)

        self.assertEqual(expected_backing, actual_backing)
