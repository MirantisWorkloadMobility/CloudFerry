# Copyright (c) 2014 Mirantis Inc.
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


from cloudferry.cloud import cloud
from cloudferry.cloud import cloud_ferry
from cloudferry.lib.base import migration
from cloudferry.lib.os.compute import nova_compute
from cloudferry.lib.os.identity import keystone
from cloudferry.lib.os.image import glance_image
from cloudferry.lib.os.network import neutron
from cloudferry.lib.os.object_storage import swift_storage
from cloudferry.lib.os.storage import cinder_storage
from cloudferry.lib.scheduler import cursor
from cloudferry.lib.scheduler import namespace
from cloudferry.lib.scheduler import scheduler
from cloudferry.lib.utils import utils as utl


class OS2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(OS2OSFerry, self). __init__(config)
        resources = {'identity': keystone.KeystoneIdentity,
                     'image': glance_image.GlanceImage,
                     'storage': cinder_storage.CinderStorage,
                     'network': neutron.NeutronNetwork,
                     'compute': nova_compute.NovaCompute,
                     'objstorage': swift_storage.SwiftStorage}
        self.src_cloud = cloud.Cloud(resources, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources, cloud.DST, config)
        self.src_cloud.migration = {
            resource: migration.Migration(self.src_cloud, self.dst_cloud,
                                          resource)
            for resource in resources
        }
        self.dst_cloud.migration = {
            resource: migration.Migration(self.src_cloud, self.dst_cloud,
                                          resource)
            for resource in resources
        }
        self.init = {
            'src_cloud': self.src_cloud,
            'dst_cloud': self.dst_cloud,
            'cfg': self.config,
        }
        self.scenario = None

    def migrate(self, scenario=None):
        self.scenario = scenario
        namespace_scheduler = namespace.Namespace({
            '__init_task__': self.init,
            'info_result': {
                utl.INSTANCES_TYPE: {}
            }
        })
        # "process_migration" is dict with 3 keys:
        #    "preparation" - is cursor that points to tasks must be processed
        #                    before migration i.e - taking snapshots,
        #                    figuring out all services are up
        #    "migration" - is cursor that points to the first
        #                  task in migration process
        #    "rollback" - is cursor that points to tasks must be processed
        #                 in case of "migration" failure
        scenario.init_tasks(self.init)
        scenario.load_scenario()
        process_migration = {k: cursor.Cursor(v)
                             for k, v in scenario.get_net().items() if v}
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler,
                                             **process_migration)
        scheduler_migr.start()
        return scheduler_migr.status_error
