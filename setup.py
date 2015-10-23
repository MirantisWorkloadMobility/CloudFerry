#!/usr/bin/env python
# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from setuptools import setup
from setuptools import find_packages
from pip.req import parse_requirements

with open('version', 'r') as f:
    setup(name='CloudFerry',
          version=f.read().strip(),
          description='Openstack cloud workload migration tool',
          author='Mirantis Inc.',
          author_email='workloadmobility@mirantis.com',
          url='https://github.com/MirantisWorkloadMobility/CloudFerry',
          packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*"]),
          py_modules=['cloudferry', 'cfglib', 'data_storage', 'fabfile'],
          entry_points={
              'console_scripts': ['cloudferry = cloudferry:console']
          },
          install_requires=[str(ir.req) for ir in
                            parse_requirements('requirements.txt')
                            if ir.url is None],

          dependency_links=[str(req_line.url) for req_line in
                            parse_requirements('requirements.txt')
                            if req_line.url],
          package_data={'': ['*.ini', '*.yaml', '*.html']},
          include_package_data=True)
