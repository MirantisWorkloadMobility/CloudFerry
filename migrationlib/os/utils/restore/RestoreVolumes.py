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


func_restore = {
    'detach': lambda volume: volume.start(),
    'attach': lambda instance_uuid, mountpoint: lambda volume: volume.attach(instance_uuid, mountpoint),
    'status': lambda status: lambda volume, client: __wait_for_status(client,
                                                                      volume.id,
                                                                      status)
}


def __wait_for_status(getter, id, status, limit_retry=60):
    count = 0
    while getter.get(id).status.lower() != status.lower():
        time.sleep(1)
        count += 1
        if count > limit_retry:
            raise TimeoutException(getter.get(id).status.lower(), status, "Timeout exp")


class TimeoutException(Exception):
    def __init__(self, status_obj, exp_status, msg):
        self.status_obj = status_obj
        self.exp_status = exp_status
        self.msg = msg


class RestoreVolumes(RestoreState):
    def restore(self, diff_snapshot):
        report = Report()
        volumes = diff_snapshot.convert_to_dict()['volumes']
        for id_obj in volumes:
            report.addVolume(id_obj, self.fix(id_obj, volumes[id_obj]))
        return report

    def fix(self, id_obj, instance):
        return super(RestoreVolumes, self).fix(id_obj, instance)

    def fix_add(self, id_obj, obj):
        self.cinder_client.volumes.delete(id_obj)
        return ReportObjConflict(id_obj, obj, "Fix via delete", FIX)

    def fix_delete(self, id_obj, obj):
        return ReportObjConflict(id_obj, obj, "Delete instance. Need help of user", CONFLICT)

    def fix_change(self, id_obj, obj):
        res = []
        for was_prop in obj.value.was:
            res.append({
                'status': self.__fix_change_status,
                'attachments': self.__fix_change_attachments
            }[was_prop](id_obj, obj))
        return res

    def __fix_change_status(self, id_obj, obj):
        pass

    def __fix_change_attachments(self, id_obj, obj):
        was_attachment = {}
        for attach in obj.value.was['attachments']:
            was_attachment[attach['id']] = attach
        curr_attachment = {}
        for attach in obj.value.curr['attachments']:
            curr_attachment[attach['id']] = attach
        for attach in curr_attachment:
            if not attach in was_attachment:
                volume = self.cinder_client.volumes.get(attach)
                func_restore['detach'](volume)
        for attach in was_attachment:
            if not attach in curr_attachment:
                try:
                    volume = self.cinder_client.volumes.get(attach)
                    func_restore['attach'](was_attachment[attach]['server_id'], was_attachment[attach]['device'])(volume)
                    func_restore['status']('in-use')(volume, self.cinder_client.volumes)
                except TimeoutException as e:
                    return ReportObjConflict(id_obj, obj, "Error restore attachments",
                                             CONFLICT)
        return ReportObjConflict(id_obj, obj, "Attachments restore", FIX)

    def __fix_change_status(self, id_obj, obj):
        was = obj.value.was['status'].lower()
        curr = obj.value.curr['status'].lower()
        fix_report = ReportObjConflict(id_obj, obj, "Change status %s -> %s" % (obj.value.curr['status'],
                                                                                obj.value.was['status']), FIX)
        error_report = ReportObjConflict(id_obj, obj, "Error restore %s -> %s" % (obj.value.curr['status'],
                                                                                  obj.value.was['status']), CONFLICT)
        map_status = {
            'in-use': {
                'available': (func_restore['detach'],
                              func_restore['status']('available', self.cinder_client.servers))
            },
            'available': {
                'in-use': (lambda volume: True, )
            }
        }
        if was != curr:
            volume = self.cinder_client.servers.get(id_obj)
            try:
                reduce(lambda res, f: f(volume), map_status[curr][was], None)
            except TimeoutException as e:
                return error_report
            if curr in map_status:
                return fix_report
            else:
                return error_report
        else:
            return ReportObjConflict(id_obj, obj, "No change property", FIX)