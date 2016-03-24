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

from pip import req
import setuptools


def reqs(filename):
    return [str(r.req) for r in req.parse_requirements(filename,
                                                       session=False)]


TEST_REQS = reqs('test-requirements.txt')


setuptools.setup(
    name='CloudFerry',
    description='Openstack cloud workload migration tool',
    author='Mirantis Inc.',
    author_email='workloadmobility@mirantis.com',
    license='Apache',
    url='https://github.com/MirantisWorkloadMobility/CloudFerry',
    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    entry_points={
        'oslo.config.opts': [
            'cloudferry=cloudferry.cfglib:list_opts',
        ],
        'console_scripts': [
            'cloudferry = cloudferry.bin.main:main'
        ],
    },
    install_requires=reqs('requirements.txt'),
    extras_require={
        'docs': reqs('docs/doc-requirements.txt'),
        'tests': TEST_REQS,
    },
    tests_require=TEST_REQS,
    test_suite='nose.collector',
    package_data={'cloudferry.templates': ['*.html']},
    include_package_data=True,
)
