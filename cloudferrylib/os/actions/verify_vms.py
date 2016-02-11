# Copyright (c) 2015 Mirantis Inc.
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


from cloudferrylib.base import exception
from cloudferrylib.base.action import action
from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


class VerifyVms(action.Action):
    """ Compare SRC and DST cloud resources. 'info' has DST resources. """
    def run(self, **kwargs):
        if not kwargs.get('info'):
            raise exception.AbortMigrationError(
                "No information from destination cloud."
                "Something has been broken on early steps."
            )
        dst_info = kwargs['info']
        search_opts = {'search_opts': kwargs.get('search_opts', {})}
        search_opts.update(kwargs.get('search_opts_tenant', {}))
        src_info = kwargs['info_backup']
        old_ids = set(dst_inst['meta']['old_id']
                      for dst_inst in dst_info['instances'].values())
        dst_cmp_info = {}
        inst_cnt = 0
        for dst_inst in dst_info['instances'].values():
            old_id = dst_inst['meta']['old_id']
            dst_cmp_info[old_id] = {}
            dst_inst_ = dst_inst['instance']
            dst_cmp_info[old_id].update(
                {'name': dst_inst_['name']})
            dst_cmp_info[old_id].update(
                {'flav_details': dst_inst_['flav_details']})
            dst_cmp_info[old_id].update(
                {'key_name': dst_inst_['key_name']})
            dst_cmp_info[old_id].update(
                {'interfaces': dst_inst_['interfaces']})
            dst_volumes = dst_inst['meta']['volume']
            new_dst_volumes = []
            for dst_vol in dst_volumes:
                new_dst_volumes.append(dst_vol['volume'])
            dst_cmp_info[old_id].update(
                {'volumes': new_dst_volumes})

            dst_cmp_info[old_id].update(
                {'server_group': dst_inst_['server_group']})

            inst_cnt += 1
        failed_vms = []
        for src_inst_id in src_info['instances']:
            if ((src_inst_id not in old_ids) or
                    (src_inst_id not in dst_cmp_info)):
                failed_vms.append(src_inst_id)
            else:
                dst_cmp_inst = dst_cmp_info[src_inst_id]
                src_inst_info = src_info['instances'][src_inst_id]['instance']
                if src_inst_info['name'] != dst_cmp_inst['name']:
                    LOG.warning("Wrong name of instance %s on DST",
                                src_inst_id)
                    failed_vms.append(src_inst_id)
                if (src_inst_info['flav_details'] !=
                        dst_cmp_inst['flav_details']):
                    LOG.warning("Wrong flav_details of instance %s on DST",
                                src_inst_id)
                if src_inst_info['key_name'] != dst_cmp_inst['key_name']:
                    LOG.warning("Wrong key_name of instance %s on DST",
                                src_inst_id)
                    failed_vms.append(src_inst_id)
                if (sorted(src_inst_info['interfaces']) !=
                        sorted(dst_cmp_inst['interfaces'])):
                    LOG.warning("Wrong interfaces of instance %s on DST",
                                src_inst_id)
                    failed_vms.append(src_inst_id)
                if src_inst_info['volumes'] != dst_cmp_inst['volumes']:
                    LOG.warning("Wrong volumes of instance %s on DST",
                                src_inst_id)

                # Verify that migrated VM belongs to correct server group
                if (src_inst_info['server_group'] !=
                        dst_cmp_inst['server_group']):
                    LOG.warning("Wrong server group of instance '%s' on DST! "
                                "SRC server group: '%s', "
                                "DST server group: '%s'.",
                                src_inst_id,
                                src_inst_info['server_group'],
                                dst_cmp_inst['server_group'])

        if failed_vms:
            LOG.warning("Instances were not migrated:")
            for vm in failed_vms:
                LOG.warning("%s", vm)
            return False
        LOG.debug("Compared instance names, flavors, "
                  "interfaces, volumes and key names. "
                  "Number of migrated instances: %s", inst_cnt)
        return True
