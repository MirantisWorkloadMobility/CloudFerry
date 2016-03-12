# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from oslo_utils import importutils

from cloudferrylib import stage
from cloudferrylib.os.discovery import model

LOG = logging.getLogger(__name__)


class DiscoverStage(stage.Stage):
    def __init__(self):
        super(DiscoverStage, self).__init__()
        self.missing_clouds = None

    def invalidate(self, old_signature, new_signature, force=False):
        """
        Remove data related to any cloud that changed signature.
        """
        if force:
            with model.Session() as session:
                session.delete()
            return

        self.missing_clouds = []

        # Create set of cloud names that which data is not valid anymore
        old_clouds = set(old_signature.keys())
        invalid_clouds = old_clouds.difference(new_signature.keys())
        for name, signature in new_signature.items():
            if name not in old_signature:
                self.missing_clouds.append(name)
                continue
            if old_signature[name] != signature:
                self.missing_clouds.append(name)
                invalid_clouds.add(name)

        with model.Session() as session:
            for cloud in invalid_clouds:
                session.delete(cloud=cloud)

    def signature(self, config):
        """
        Discovery signature is based on configuration. Each configured cloud
        have it's own signature.
        """
        return {n: [c.credential.auth_url, c.credential.region_name]
                for n, c in config.clouds.items()}

    def execute(self, config):
        """
        Execute discovery.
        """
        if self.missing_clouds is None:
            self.missing_clouds = config.clouds.keys()

        for cloud_name in self.missing_clouds:
            cloud = config.clouds[cloud_name]
            for class_name in cloud.discover:
                cls = importutils.import_class(class_name)
                LOG.info('Starting discover %s objects in %s cloud',
                         cls.__name__, cloud_name)
                cls.discover(cloud)
                LOG.info('Done discovering %s objects in %s cloud',
                         cls.__name__, cloud_name)
