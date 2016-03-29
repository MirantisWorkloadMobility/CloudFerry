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


class StopService(object):
    def __init__(self, runner, service):
        self.runner = runner
        self.service = service

    def __enter__(self):
        cmd = 'service {service} stop'.format(service=self.service)
        self.runner.run(cmd)

    def __exit__(self, exc_type, exc_val, exc_tb):
        cmd = 'service {service} start'.format(service=self.service)
        self.runner.run(cmd)


class StopNovaCompute(StopService):
    def __init__(self, runner):
        super(StopNovaCompute, self).__init__(runner, 'nova-compute')

    def __exit__(self, exc_type, exc_val, exc_tb):
        super(StopNovaCompute, self).__exit__(exc_type, exc_val, exc_tb)
