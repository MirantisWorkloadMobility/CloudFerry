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


class TimeoutException(Exception):
    def __init__(self, status_obj, exp_status, msg):
        self.status_obj = status_obj
        self.exp_status = exp_status
        self.msg = msg


class RestoreInstances(RestoreState):
    def restore(self, diff_snapshot):
        report = Report()
        instances = diff_snapshot.convert_to_dict()['instances']
        for id_obj in instances:
            report.addInstance(id_obj, self.fix(id_obj, instances[id_obj]))
        return report

    def fix(self, id_obj, instance):
        return super(RestoreInstances, self).fix(id_obj, instance)

    def fix_add(self, id_obj, obj):
        self.nova_client.servers.get(id_obj).delete()
        return ReportObjConflict(id_obj, obj, "Fix via delete", FIX)

    def fix_delete(self, id_obj, obj):
        return ReportObjConflict(id_obj, obj, "Delete instance. Need help of user", CONFLICT)

    def fix_change(self, id_obj, obj):
        res = []

        for was_prop in obj.value.was:
            res.append({
                'status': self.__fix_change_status,
                'name': self.__fix_change_name
            }[was_prop](id_obj, obj))
        return res

    def __fix_change_status(self, id_obj, obj):
        was = obj.value.was['status'].lower()
        curr = obj.value.curr['status'].lower()
        fix_report = ReportObjConflict(id_obj, obj, "Change status %s -> %s" % (obj.value.curr['status'],
                                                                                obj.value.was['status']), FIX)
        error_report = ReportObjConflict(id_obj, obj, "Error restore %s -> %s" % (obj.value.curr['status'],
                                                                                  obj.value.was['status']), CONFLICT)
        func_restore = {
            'start': lambda instance: instance.start(),
            'stop': lambda instance: instance.stop(),
            'resume': lambda instance: instance.resume(),
            'paused': lambda instance: instance.pause(),
            'unpaused': lambda instance: instance.unpause(),
            'suspend': lambda instance: instance.suspend(),
            'status': lambda status: lambda instance: self.__wait_for_status(self.nova_client.servers,
                                                                             instance.id,
                                                                             status)
        }
        map_status = {
            'paused': {
                'active': (func_restore['unpaused'],
                           func_restore['status']('active')),
                'shutoff': (func_restore['stop'],
                            func_restore['status']('shutoff')),
                'suspend': (func_restore['unpaused'],
                            func_restore['status']('active'),
                            func_restore['suspend'],
                            func_restore['status']('suspend'))
            },
            'suspend': {
                'active': (func_restore['resume'],
                           func_restore['status']('active')),
                'shutoff': (func_restore['stop'],
                            func_restore['status']('shutoff')),
                'paused': (func_restore['resume'],
                           func_restore['status']('active'),
                           func_restore['paused'],
                           func_restore['status']('paused'))
            },
            'active': {
                'paused': (func_restore['paused'],
                           func_restore['status']('paused')),
                'suspend': (func_restore['suspend'],
                            func_restore['status']('suspend')),
                'shutoff': (func_restore['stop'],
                            func_restore['status']('shutoff'))
            },
            'shutoff': {
                'active': (func_restore['start'],
                           func_restore['status']('active')),
                'paused': (func_restore['start'],
                           func_restore['status']('active'),
                           func_restore['paused'],
                           func_restore['status']('paused')),
                'suspend': (func_restore['start'],
                            func_restore['status']('active'),
                            func_restore['suspend'],
                            func_restore['status']('suspend'))
            }
        }
        if was != curr:
            instance = self.nova_client.servers.get(id_obj)
            try:
                reduce(lambda res, f: f(instance), map_status[curr][was], None)
            except TimeoutException as e:
                return error_report
            if curr in map_status:
                return fix_report
            else:
                return error_report
        else:
            return ReportObjConflict(id_obj, obj, "No change property", FIX)

    def __wait_for_status(self, getter, id, status, limit_retry=60):
        count = 0
        while getter.get(id).status.lower() != status.lower():
            time.sleep(1)
            count += 1
            if count > limit_retry:
                raise TimeoutException(getter.get(id).status.lower(), status, "Timeout exp")

    def __fix_change_name(self, id_obj, obj):
        # TODO: Restore name
        return ReportObjConflict(id_obj, obj, "Error restore name instance %s -> %s" % (obj.value.curr['status'],
                                                                                        obj.value.was['status']),
                                 CONFLICT)
