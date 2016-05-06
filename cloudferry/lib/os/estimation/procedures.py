# Copyright (c) 2016 Mirantis Inc.
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

import collections
import heapq
import logging

from cloudferry.lib.os.discovery import model
from cloudferry.lib.utils import query
from cloudferry.lib.utils import sizeof_format

LOG = logging.getLogger(__name__)
G = sizeof_format.size_multiplier('G')


class ProcedureBase(object):
    def __init__(self, cfg, migration_name):
        self.migration = cfg.migrations[migration_name]
        self.src = self.migration.source
        self.dst = self.migration.destination

    def get_objects(self, model_name, exclude_objects=None):
        klass = model.get_model(model_name)
        with model.Session() as session:
            for obj in self.migration.query.search(session, self.src, klass):
                if (obj.find_link(self.dst) or
                        (exclude_objects is not None and
                         obj.object_id in exclude_objects)):
                    continue
                yield obj


class EstimateCopy(ProcedureBase):
    def run(self):
        images_size, images_count = 0, 0
        used_images = set()
        images_unused_size, images_unused_count = 0, 0
        volumes_size, volumes_count = 0, 0
        used_volumes = set()
        volumes_unused_size, volumes_unused_count = 0, 0
        ephemeral_size, ephemeral_count = 0, 0

        for server in self.get_objects('vms'):
            if server.image is not None:
                images_count += 1
                images_size += server.image.size
                used_images.add(server.image.object_id)
            for ephemeral_disk in server.ephemeral_disks:
                ephemeral_count += 1
                ephemeral_size += ephemeral_disk.size
            for volume in server.attached_volumes:
                volumes_count += 1
                volumes_size += volume.size * G
                used_volumes.add(volume.object_id)
        for image in self.get_objects('images', used_images):
            images_count += 1
            images_size += image.size
            images_unused_count += 1
            images_unused_size += image.size
        for volume in self.get_objects('volumes', used_volumes):
            size = volume.size * G
            volumes_count += 1
            volumes_size += size
            volumes_unused_count += 1
            volumes_unused_size += size

        return (
            ('Volumes', volumes_count,
             sizeof_format.sizeof_fmt(volumes_size, target_unit='G')),
            ('Unused volumes', volumes_unused_count,
             sizeof_format.sizeof_fmt(volumes_unused_size, target_unit='G')),
            ('Images', images_count,
             sizeof_format.sizeof_fmt(images_size, target_unit='G')),
            ('Unused images', images_unused_count,
             sizeof_format.sizeof_fmt(images_unused_size, target_unit='G')),
            ('Ephemeral disks', ephemeral_count,
             sizeof_format.sizeof_fmt(ephemeral_size, target_unit='G')),
            ('Total', volumes_count + images_count + ephemeral_count,
             sizeof_format.sizeof_fmt(volumes_size + images_size +
                                      ephemeral_size, target_unit='G'))
        )


class _Record(object):
    def __init__(self, object_id, object_name, object_size):
        self.id = object_id
        self.name = object_name
        self.size = object_size


class ShowObjects(ProcedureBase):
    FILTERS = ('servers', 'images', 'volumes', 'ephemeral-disks')

    def __init__(self, cfg, migration_name, filters, show_unused=False,
                 limit=None):
        super(ShowObjects, self).__init__(cfg, migration_name)
        self.filters = set(filters or self.FILTERS)
        self.show_unused = show_unused
        self.limit = limit
        self.used_objects = dict(images=set(), volumes=set())
        self.show_vms = 'servers' in self.filters
        self.show_ephemeral = 'ephemeral-disks' in self.filters

    def get_used_objects(self):
        for r in self.filters.intersection({'servers', 'ephemeral-disks'}):
            LOG.warning('%s cannot be showed because show_unused is '
                        'selected', r)
        for server in self.get_objects('vms'):
            if server.image is not None:
                self.used_objects['images'].add(server.image.object_id)
            for volume in server.attached_volumes:
                self.used_objects['volumes'].add(volume.object_id)

    def get_data(self):
        data = collections.defaultdict(list)
        if self.show_ephemeral or self.show_vms:
            for server in self.get_objects('vms'):
                if self.show_vms:
                    size = 0
                    if server.image is not None:
                        size += server.image.size
                    for volume in server.attached_volumes:
                        size += volume.size * G
                    for ephemeral_disk in server.ephemeral_disks:
                        size += ephemeral_disk.size
                    data['Server'].append(_Record(server.object_id.id,
                                                  server.name, size))
                if self.show_ephemeral:
                    for ephemeral_disk in server.ephemeral_disks:
                        data['Ephemeral disk'].append(
                            _Record('server.id %s' % server.object_id.id,
                                    'server.name %s' % server.name,
                                    ephemeral_disk.size))
        for f in self.filters.difference({'servers', 'ephemeral-disks'}):
            multiplier = G if f == 'volumes' else 1
            name = f.capitalize()
            for obj in self.get_objects(f, self.used_objects[f]):
                data[name].append(_Record(obj.object_id.id, obj.name,
                                          obj.size * multiplier))
        return data

    def run(self):
        if self.show_unused:
            self.get_used_objects()
            self.show_vms = False
            self.show_ephemeral = False

        data = self.get_data()

        result = []
        total_cnt = 0
        total_size = 0
        for k, records in data.iteritems():
            cnt = 0
            size = 0
            if self.limit:
                records = heapq.nlargest(self.limit, data,
                                         key=lambda o: o.size)
            else:
                records = sorted(records, key=lambda o: o.size, reverse=True)
            for r in records:
                result.append((k, r.id, r.name,
                               sizeof_format.sizeof_fmt(r.size)))
                cnt += 1
                size += r.size
            result.append((k, 'Total', cnt, sizeof_format.sizeof_fmt(size)))
            total_cnt += cnt
            total_size += size
        result.append(('Total', '', total_cnt,
                       sizeof_format.sizeof_fmt(total_size)))

        return result


def show_query(cloud_name, type_name, qry):
    data = []
    fields = model.get_model(type_name).get_schema().fields.keys()
    with model.Session() as session:
        for r in query.Query({type_name: [qry]}).search(session, cloud_name):
            data.append([str(getattr(r, f)) for f in fields])
    return fields, data
