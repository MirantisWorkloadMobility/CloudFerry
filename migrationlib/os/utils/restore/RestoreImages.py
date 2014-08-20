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
from RestoreState import RestoreState
from Report import *
__author__ = 'mirrorcoder'


class RestoreImages(RestoreState):
    def restore(self, diff_snapshot):
        report = Report()
        images = diff_snapshot.convert_to_dict()['images']
        for id_obj in images:
            report.addImage(id_obj, self.__fix(id_obj, images[id_obj]))
        return report

    def __fix_add(self, id_obj, obj):
        return ReportObjConflict(id_obj, obj, "Fix via delete", FIX)

    def __fix_delete(self, id_obj, obj):
        return None

    def __fix_change(self, id_obj, obj):
        return None