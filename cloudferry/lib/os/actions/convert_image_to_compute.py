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

from cloudferry.lib.base.action import action
import copy


class ConvertImageToCompute(action.Action):

    def run(self, images_info=None, compute_ignored_images=None, **kwargs):
        images_info = copy.deepcopy(images_info)
        instance_info = {'instances': compute_ignored_images or {}}
        for image in images_info['images'].itervalues():
            if 'instance' not in image['meta']:
                continue
            instances = image['meta']['instance']
            for instance in instances:
                if image['image']:
                    instance['instance']['image_id'] = image['image']['id']
                else:
                    instance['instance']['image_id'] = None
                instance_info['instances'][
                    instance['instance']['id']] = instance
        return {'info': instance_info}
