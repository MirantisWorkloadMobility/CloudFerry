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
import time
__author__ = 'mirrorcoder'

FIX = "fix"
CONFLICT = "conflict"


class ReportObjConflict:
    def __init__(self, id_obj, obj, msg_conflict, status):
        self.id_obj = id_obj
        self.obj = obj
        self.msg_conflict = msg_conflict
        self.status = status

    def getStatus(self):
        return self.status
    

class Report:
    def __init__(self, report_dict={}):
        self.instances = {} if not report_dict else report_dict['instances']
        self.images = {} if not report_dict else report_dict['images']
        self.volumes = {} if not report_dict else report_dict['volumes']
        self.tenants = {} if not report_dict else report_dict['tenants']
        self.users = {} if not report_dict else report_dict['users']
        self.security_groups = {} if not report_dict else report_dict['security_groups']
        self.timestamp = time.time() if not report_dict else report_dict['timestamp']

    def add(self, id, category, report_obj):
        self.__dict__[category][id] = report_obj

    def addInstance(self, id, report_obj):
        self.instances[id] = report_obj

    def addImage(self, id, report_obj):
        self.images[id] = report_obj

    def addVolume(self, id, report_obj):
        self.volumes[id] = report_obj

    def addTenant(self, id, report_obj):
        self.tenants[id] = report_obj

    def addUser(self, id, report_obj):
        self.users[id] = report_obj

    def addSecurityGroup(self, id, report_obj):
        self.security_groups[id] = report_obj

    def union(self, snapshot, exclude=['timestamp']):
        report_dict = self.excluding_fields(snapshot.convert_to_dict(), exclude)
        for item in report_dict:
            self.__dict__[item].update(report_dict[item])

    def excluding_fields(self, report_dict, exclude):
        for item in exclude:
            if item in report_dict:
                del report_dict[item]
        return report_dict

    def convert_to_dict(self):
        return {
            'instances': self.instances,
            'images': self.images,
            'volumes': self.volumes,
            'tenants': self.tenants,
            'users': self.users,
            'security_groups': self.security_groups,
            'timestamp': self.timestamp
        }