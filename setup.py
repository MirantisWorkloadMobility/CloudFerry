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

import os
from pip import req
import setuptools


all_reqs = req.parse_requirements('requirements.txt', session=False)
test_reqs = req.parse_requirements('test-requirements.txt', session=False)
version = open(os.path.join(os.path.dirname(__file__),
                            'version.txt')).read().strip()

setuptools.setup(
    name='CloudFerry',
    version=version,
    description='Openstack cloud workload migration tool',
    author='Mirantis Inc.',
    author_email='workloadmobility@mirantis.com',
    license='Apache',
    url='https://github.com/MirantisWorkloadMobility/CloudFerry',
    packages=['cloudferry'],
    entry_points={'console_scripts': ['cloudferry = cloudferry:console'],
                  'oslo.config.opts': ['cloudferry = cfglib:list_opts']},
    install_requires=[str(r .req) for r in all_reqs],
    tests_require=[str(r.req) for r in test_reqs],
    package_data={'cloudferry.templates': ['*.html']},
    include_package_data=True)
