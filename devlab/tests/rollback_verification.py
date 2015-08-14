# Copyright (c) 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

"""
This is module to verify if rollback procedure was executed correctly. Basically
two dictionaries are being compared:
    - pre_data: data collected from SRC and DST clusters, is being stored in
                file with name which is described in config file.
    - data_after: data collected from SRC and DST clusters using data_collector
                  module, it is being stored in memory as dictionary.
"""

import os
import yaml

import config
import functional_test
from data_collector import DataCollector


class RollbackVerification(functional_test.FunctionalTest):

    def setUp(self):
        data_collector = DataCollector()

        self.data_after = data_collector.data_collector()

        path = 'devlab/tests'
        file_name = config.rollback_params['data_file_names']['PRE']
        pre_file_path = os.path.join(data_collector.main_folder, path,
                                     file_name)
        with open(pre_file_path, "r") as f:
            self.pre_data = yaml.load(f)

    def test_verify_rollback(self):
        self.maxDiff = None
        self.assertEqual(self.data_after, self.pre_data)
