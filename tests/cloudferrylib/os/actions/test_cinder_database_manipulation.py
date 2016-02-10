"""Cinder database manipulation tests."""
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

import mock
from mock.mock import call, ANY

from tests import test
from cloudferrylib.os.actions import cinder_database_manipulation
from cloudferrylib.utils import utils


SRC_CINDER_HOST = "src_cinder"
DST_CINDER_HOST = "dst_cinder"
SRC = 'src'
RSYNC_CMD = cinder_database_manipulation.RSYNC_CMD
TENANTS = TN1, TN2 = (
    {'id': 'tn1_id', 'name': 'tn1'},
    {'id': 'tn2_id', 'name': 'tn2'},
)
DST_TN = {
    TN1['id']: 'dst_tn1',
    TN2['id']: 'dst_tn2',
}


def volume_size(*_):
    return 1048580


def free_space(*_):
    return 2048580


def get_dst_mount(fake_dst_data):
    dst_mount = {
        'nfs1_dst_id': {
            ('/var/lib/cinder/dstdir1a', '/var/exports/dst1a'),
        },
        'nfs_other_id': {
            ('/var/lib/cinder/dstdir2a', '/var/exports/dst2a'),
        },
        'nfs3_dst_id': {
            ('/var/lib/cinder/dstdir3a', '/var/exports/dst3a'),
        },
    }
    if 'volume_types' not in fake_dst_data:
        dst_mount['default'] = {
            ('/var/lib/cinder/dstdir0a', '/var/exports/dst0a'),
        }
    return dst_mount


def find_dir(fake_dst_data):
    def find_dir_func(_, paths, v):
        if not paths:
            return None
        p = sorted(list(paths))[0]

        dst_mount = get_dst_mount(fake_dst_data)

        fake_dst_paths = [
            line[0] for t in dst_mount for line in dst_mount[t]
        ]

        if p in fake_dst_paths:
            return None
        return '%s/volume-%s' % (p, v['id'])
    return find_dir_func


def mount_dirs(_, vt=None):
    if vt:
        vt_map = {
            'nfs1': {
                '/var/lib/cinder/dir1a',
            },
            'nfs2': {
                '/var/lib/cinder/dir2a',
            },
            'nfs3': {
                '/var/lib/cinder/dir3a',
            },
        }
        return vt_map[vt['name']]
    return ['/var/lib/cinder/80a8c674d115b2a3c20f1e959bd1f20f']


def _action(fake_src_data, fake_dst_data, fake_deployed_data):
    fake_config = utils.ext_dict(
        migrate=utils.ext_dict({
            'ssh_connection_attempts': 3,
            'key_filename': 'key_filename',
        }),
        src=utils.ext_dict({'ssh_user': 'src_user',
                            'ssh_sudo_password': 'src_passwd',
                            'ssh_host': SRC_CINDER_HOST,
                            }),
        dst=utils.ext_dict({'ssh_user': 'dst_user',
                            'ssh_sudo_password': 'dst_passwd',
                            'ssh_host': DST_CINDER_HOST,
                            'conf': '/etc/cinder.conf',
                            }),
        src_storage=utils.ext_dict({'conf': '/etc/cinder.conf'}),
        dst_storage=utils.ext_dict({'conf': '/etc/cinder.conf'}),
    )

    fake_src_cloud = mock.Mock()
    fake_src_storage = mock.Mock()
    fake_src_storage.read_db_info = \
        mock.Mock(return_value=fake_src_data)
    fake_img_res = mock.Mock()

    fake_src_cloud.migration = {
        'image': FakeMigration('image'),
        'identity': None,
    }
    fake_src_cloud.resources = {
        'storage': fake_src_storage,
        'image': fake_img_res,
    }
    fake_src_images = {
        'images':
        {
            'img1': {
                'image': {
                    'id': 'img1',
                    'name': 'img1_name',
                    'checksum': 'fake_checksum1',
                }
            }
        }
    }
    fake_img_res.read_db_info = \
        mock.Mock(return_value=fake_src_images)

    fake_dst_cloud = mock.Mock()
    fake_dst_storage = mock.Mock()
    fake_dst_storage.read_db_info = \
        mock.Mock(return_value=fake_dst_data)
    fake_dst_storage.reread = \
        mock.Mock(return_value=fake_deployed_data)

    fake_dst_storage.deploy = mock.Mock(side_effect=no_modify)
    fake_dst_img_res = mock.Mock()
    fake_dst_cloud.resources = {
        'storage': fake_dst_storage,
        'image': fake_dst_img_res,
    }
    fake_dst_images = {
        'images':
        {
            'dst_img1': {
                'image': {
                    'id': 'dst_img1',
                    'name': 'img1_name',
                    'checksum': 'fake_checksum1',
                }
            }
        }
    }
    fake_dst_img_res.read_db_info = \
        mock.Mock(return_value=fake_dst_images)

    fake_init = {
        'src_cloud': fake_src_cloud,
        'dst_cloud': fake_dst_cloud,
        'cfg': fake_config
    }

    action = cinder_database_manipulation.WriteVolumesDb(fake_init)

    action.cp_volumes.dst_mount = get_dst_mount(fake_dst_data)

    action.cp_volumes.mount_dirs = mock.MagicMock(side_effect=mount_dirs)

    action.cp_volumes.find_dir = mock.MagicMock(
        side_effect=find_dir(fake_dst_data))

    action.cp_volumes.volume_size = mock.MagicMock(side_effect=volume_size)

    action.cp_volumes.free_space = mock.MagicMock(side_effect=free_space)

    action.cp_volumes.dst_volumes = mock.MagicMock(return_value=[])

    action.cp_volumes.dst_hosts = [
        'dst_cinder',
        'dst_cinder@nfs1',
        'dst_cinder@nfs2',
        'dst_cinder@nfs3',
    ]

    action.cp_volumes.run_repeat_on_errors = mock.Mock()

    def not_rsync(_, src, dst):
        return action.cp_volumes.run_rsync(src, dst)
    action.cp_volumes.rsync_if_enough_space = \
        mock.MagicMock(side_effect=not_rsync)

    return action, {
        cinder_database_manipulation.NAMESPACE_CINDER_CONST:
        fake_src_data
    }


class WriteVolumesDbTest(test.TestCase):
    def test_run_no_volume_types(self):
        volumes = {
            "volumes": [
                {
                    "id": "vol-1",
                    "project_id": TN1['id'],
                    "display_name": "cinder_vol1",
                },
            ],
        }
        fake_dst_data = {
            "volumes": [],
        }
        fake_deployed = {
            "volumes": [
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol-1",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "provider_location": "/var/exports/dst0a",
                 "project_id": DST_TN[TN1['id']],
                 "size": 2,
                 }
            ],
            "volume_glance_metadata": [],
            "volume_metadata": [],
            "quotas": [
                {
                    'hard_limit': 10,
                    'resource': 'volumes',
                    'project_id': DST_TN[TN1['id']],
                }
            ],
        }
        action, args = _action(volumes, fake_dst_data, fake_deployed)
        data = action.run(**args)

        calls = [
            call(ANY,
                 ('%s '
                  '/var/lib/cinder/80a8c674d115b2a3c20f1e959bd1f20f/'
                  'volume-vol-1'
                  ' dst_user@dst_cinder:/var/lib/cinder/dstdir0a'
                  ) % RSYNC_CMD
                 ),
        ]
        action.cp_volumes.run_repeat_on_errors.assert_has_calls(calls)
        expected = {
            "volume_metadata": [],
            "volume_glance_metadata": [],
            "volumes": [
                {
                    "status": "available",
                    "volume_type_id": None,
                    "attach_status": "detached",
                    "provider_location": "/var/exports/dst0a",
                    "host": "dst_cinder",
                    "instance_uuid": None,
                    "mountpoint": None,
                    "id": "vol-1",
                    "size": 2,
                    "project_id": DST_TN[TN1['id']],
                }
            ],
            "quota_usages": [
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'volumes',
                 'in_use': 1,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'gigabytes',
                 'in_use': 2,
                 'reserved': 0,
                 },
            ],
            "quotas": [
                {
                    'hard_limit': 10,
                    'resource': 'volumes',
                    'project_id': DST_TN[TN1['id']],
                }
            ],
        }
        self.assertEqual(data, expected)

    def test_skip_existing_volumes(self):
        volumes = {
            "volumes": [
                {"id": "vol-1",
                 "project_id": TN1['id'],
                 "size": 1,
                 "display_name": "cinder_vol1",
                 },
                {"id": "vol-2",
                 "project_id": TN1['id'],
                 "display_name": "cinder_vol2",
                 },
                {"id": "vol-3",
                 "project_id": TN1['id'],
                 "display_name": "cinder_vol3",
                 },
            ]
        }
        fake_dst_data = {
            "volumes": [
                {"id": "vol-2",
                 "project_id": DST_TN[TN1['id']],
                 "size": 2,
                 "display_name": "cinder_vol2",
                 },
                {"id": "vol-3",
                 "project_id": DST_TN[TN1['id']],
                 "size": 20,
                 "display_name": "cinder_vol3",
                 },
            ]
        }
        fake_deployed = {
            "volume_metadata": [],
            "volume_glance_metadata": [],
            "quotas": [
                {
                    'hard_limit': 6,
                    'resource': 'volumes',
                    'project_id': DST_TN[TN2['id']],
                },
            ],
            "quota_usages": [
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'volumes',
                 'in_use': 2,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'gigabytes',
                 'in_use': 22,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'fake_resource',
                 'in_use': 109,
                 'reserved': 2,
                 },
            ],
            "volumes": [
                {
                    "status": "available",
                    "volume_type_id": None,
                    "attach_status": "detached",
                    "provider_location": "/var/exports/dst0a",
                    "host": "dst_cinder",
                    "instance_uuid": None,
                    "mountpoint": None,
                    "id": "vol-1",
                    "size": 1,
                    "project_id": DST_TN[TN1['id']],
                },
                {
                    "status": "available",
                    "volume_type_id": None,
                    "attach_status": "detached",
                    "provider_location": "/var/exports/dst0a",
                    "host": "dst_cinder",
                    "instance_uuid": None,
                    "mountpoint": None,
                    "id": "vol-2",
                    "size": 2,
                    "project_id": DST_TN[TN1['id']],
                },
                {
                    "status": "available",
                    "volume_type_id": None,
                    "attach_status": "detached",
                    "provider_location": "/var/exports/dst0a",
                    "host": "dst_cinder",
                    "instance_uuid": None,
                    "mountpoint": None,
                    "id": "vol-3",
                    "size": 20,
                    "project_id": DST_TN[TN1['id']],
                },
            ],
        }
        action, args = _action(volumes, fake_dst_data, fake_deployed)
        data = action.run(**args)

        calls = [
            call(ANY,
                 ('%s '
                  '/var/lib/cinder/80a8c674d115b2a3c20f1e959bd1f20f/'
                  'volume-vol-1'
                  ' dst_user@dst_cinder:/var/lib/cinder/dstdir0a'
                  ) % RSYNC_CMD
                 ),
        ]
        action.cp_volumes.run_repeat_on_errors.assert_has_calls(calls)
        expected = {
            "volume_metadata": [],
            "volume_glance_metadata": [],
            "volumes": [
                {
                    "status": "available",
                    "volume_type_id": None,
                    "attach_status": "detached",
                    "provider_location": "/var/exports/dst0a",
                    "host": "dst_cinder",
                    "instance_uuid": None,
                    "mountpoint": None,
                    "id": "vol-1",
                    "size": 1,
                    "project_id": DST_TN[TN1['id']],
                },
                {
                    "status": "available",
                    "volume_type_id": None,
                    "attach_status": "detached",
                    "provider_location": "/var/exports/dst0a",
                    "host": "dst_cinder",
                    "instance_uuid": None,
                    "mountpoint": None,
                    "id": "vol-2",
                    "size": 2,
                    "project_id": DST_TN[TN1['id']],
                },
                {
                    "status": "available",
                    "volume_type_id": None,
                    "attach_status": "detached",
                    "provider_location": "/var/exports/dst0a",
                    "host": "dst_cinder",
                    "instance_uuid": None,
                    "mountpoint": None,
                    "id": "vol-3",
                    "size": 20,
                    "project_id": DST_TN[TN1['id']],
                },
            ],
            "quotas": [
                {
                    'hard_limit': 6,
                    'resource': 'volumes',
                    'project_id': DST_TN[TN2['id']],
                },
            ],
            "quota_usages": [
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'volumes',
                 'in_use': 3,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'gigabytes',
                 'in_use': 23,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'fake_resource',
                 'in_use': 109,
                 'reserved': 2,
                 },
                {'project_id': DST_TN[TN2['id']],
                 'resource': 'volumes',
                 'in_use': 0,
                 'reserved': 0,
                 },
            ],
        }
        self.assertEqual(data, expected)

    def test_run_with_volume_types(self):
        fake_src_data = {
            "volumes": [
                {
                    "id": "vol-nfs1",
                    "volume_type_id": "nfs1_id",
                    "project_id": TN1['id'],
                    "display_name": "cinder_vol1",
                },
                {
                    "id": "vol-nfs2",
                    "volume_type_id": "nfs2_id",
                    "project_id": TN1['id'],
                    "display_name": "cinder_vol2",
                },
                {
                    "id": "vol-nfs3",
                    "volume_type_id": "nfs3_id",
                    "project_id": TN1['id'],
                    "display_name": "cinder_vol3",
                },
            ],
            "volume_types": [
                {
                    "id": "nfs1_id",
                    "name": "nfs1",
                },
                {
                    "id": "nfs2_id",
                    "name": "nfs2",
                },
                {
                    "id": "nfs3_id",
                    "name": "nfs3",
                },
            ]
        }
        fake_dst_data = {
            "volumes": [],
            "volume_types": [
                {
                    "id": "nfs1_dst_id",
                    "name": "nfs1",
                    "project_id": DST_TN[TN1['id']],
                },
                {
                    "id": "nfs_other_id",
                    "name": "nfs_other",
                    "project_id": DST_TN[TN1['id']],
                },
                {
                    "id": "nfs3_dst_id",
                    "name": "nfs3",
                    "project_id": DST_TN[TN1['id']],
                },
            ]
        }
        fake_deployed = {
            "volume_metadata": [],
            "volume_glance_metadata": [],
            "volumes": [
                {"volume_type_id": "nfs1_dst_id",
                 "host": "dst_cinder@nfs1",
                 "id": "vol-nfs1",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "size": 101,
                 "provider_location": "/var/exports/dst1a"},
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol-nfs2",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "size": 10,
                 "provider_location": "/var/exports/dst2a"},
                {"volume_type_id": "nfs3_dst_id",
                 "host": "dst_cinder@nfs3",
                 "id": "vol-nfs3",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "provider_location": "/var/exports/dst3a"},
            ]
        }

        action, args = _action(fake_src_data, fake_dst_data, fake_deployed)
        data = action.run(**args)

        calls = [
            call(ANY, ('%s '
                       '/var/lib/cinder/dir1a/volume-vol-nfs1 '
                       'dst_user@dst_cinder:/var/lib/cinder/dstdir1a'
                       ) % RSYNC_CMD
                 ),
            call(ANY, ('%s '
                       '/var/lib/cinder/dir2a/volume-vol-nfs2 '
                       'dst_user@dst_cinder:/var/lib/cinder/dstdir2a'
                       ) % RSYNC_CMD
                 ),
            call(ANY, ('%s '
                       '/var/lib/cinder/dir3a/volume-vol-nfs3 '
                       'dst_user@dst_cinder:/var/lib/cinder/dstdir3a'
                       ) % RSYNC_CMD
                 ),
        ]
        action.cp_volumes.run_repeat_on_errors.assert_has_calls(calls)

        expected = {
            "volume_metadata": [],
            "volume_glance_metadata": [],
            "volumes": [
                {"volume_type_id": "nfs1_dst_id",
                 "host": "dst_cinder@nfs1",
                 "id": "vol-nfs1",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "size": 101,
                 "provider_location": "/var/exports/dst1a"},
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol-nfs2",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "size": 10,
                 "provider_location": "/var/exports/dst2a"},
                {"volume_type_id": "nfs3_dst_id",
                 "host": "dst_cinder@nfs3",
                 "id": "vol-nfs3",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "provider_location": "/var/exports/dst3a"},
            ],
            "quota_usages": [
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'volumes',
                 'in_use': 3,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'gigabytes',
                 'in_use': 111,
                 'reserved': 0,
                 },
            ],
        }
        for k in data:
            self.assertEqual(data[k], expected[k])

    def test_run_no_src_volume_types(self):
        fake_src_data = {
            "volumes": [
                {
                    "id": "vol",
                    "project_id": TN1['id'],
                    "display_name": "cinder_vol",
                },
            ],
        }
        fake_dst_data = {
            "volumes": [],
            "volume_types": [
                {
                    "id": "nfs_other_id",
                    "name": "nfs_other",
                    "project_id": DST_TN[TN1['id']],
                },
            ]
        }
        fake_deployed = {
            "volume_metadata": [],
            "volume_glance_metadata": [],
            "volumes": [
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "provider_location": "/var/exports/dst2a",
                 }
            ]
        }

        action, args = _action(fake_src_data, fake_dst_data, fake_deployed)
        data = action.run(**args)

        calls = [
            call(ANY, ('%s '
                       '/var/lib/cinder/80a8c674d115b2a3c20f1e959bd1f20f/'
                       'volume-vol '
                       'dst_user@dst_cinder:/var/lib/cinder/dstdir2a'
                       ) % RSYNC_CMD
                 ),
        ]
        action.cp_volumes.run_repeat_on_errors.assert_has_calls(calls)

        expected = {
            "volume_metadata": [],
            "volume_glance_metadata": [],
            "volumes": [
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "provider_location": "/var/exports/dst2a",
                 }
            ],
            "quota_usages": [
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'volumes',
                 'in_use': 1,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'gigabytes',
                 'in_use': 0,
                 'reserved': 0,
                 },
            ],
        }
        self.assertEqual(data, expected)

    def test_volume_glance_metadata(self):
        fake_src_data = {
            "volumes": [
                {
                    "id": "vol",
                    "project_id": TN1['id'],
                    "display_name": "cinder_vol",
                },
            ],
            "volume_metadata": [],
            "volume_glance_metadata": [
                {
                    "id": 1,
                    "volume_id": "vol",
                    "key": "image_id",
                    "value": "img1",
                },
            ],
        }
        fake_dst_data = {
            "volumes": [],
            "volume_types": [
                {
                    "id": "nfs_other_id",
                    "name": "nfs_other",
                    "project_id": DST_TN[TN1['id']],
                },
            ]
        }
        fake_deployed = {
            "volumes": [
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "provider_location": "/var/exports/dst2a",
                 }
            ],
            "volume_metadata": [],
            "volume_glance_metadata": [
                {
                    "id": 1,
                    "volume_id": "vol",
                    "key": "image_id",
                    "value": "dst_img1",
                }
            ]
        }

        action, args = _action(fake_src_data, fake_dst_data, fake_deployed)
        data = action.run(**args)

        calls = [
            call(ANY, ('%s '
                       '/var/lib/cinder/80a8c674d115b2a3c20f1e959bd1f20f/'
                       'volume-vol '
                       'dst_user@dst_cinder:/var/lib/cinder/dstdir2a'
                       ) % RSYNC_CMD
                 ),
        ]
        action.cp_volumes.run_repeat_on_errors.assert_has_calls(calls)

        expected = {
            "volumes": [
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "project_id": DST_TN[TN1['id']],
                 "provider_location": "/var/exports/dst2a",
                 }
            ],
            "volume_metadata": [],
            "volume_glance_metadata": [
                {
                    "id": 1,
                    "volume_id": "vol",
                    "key": "image_id",
                    "value": "dst_img1",
                }
            ],
            "quota_usages": [
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'volumes',
                 'in_use': 1,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'gigabytes',
                 'in_use': 0,
                 'reserved': 0,
                 },
            ],
        }
        self.assertEqual(data, expected)

    def test_volume_metadata(self):
        fake_src_data = {
            "volumes": [
                {
                    "id": "vol",
                    "display_name": "cinder_vol",
                },
            ],
            "volume_metadata": [
                {
                    "id": 1,
                    "volume_id": "vol",
                    "key": "test",
                    "value": True,
                },
                {
                    "id": 2,
                    "volume_id": "vol",
                    "key": "how_are_you_doing",
                    "value": "Joe",
                },
                {
                    "id": 3,
                    "volume_id": "vol",
                    "key": "It_always_sunny",
                    "value": False,
                },
            ],
            "volume_glance_metadata": [],
        }
        fake_dst_data = {
            "volumes": [],
            "volume_types": [
                {
                    "id": "nfs_other_id",
                    "name": "nfs_other",
                },
            ]
        }
        fake_deployed = {
            "volumes": [
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "provider_location": "/var/exports/dst2a",
                 "project_id": DST_TN[TN1['id']],
                 }
            ],
            "volume_metadata": [
                {
                    "id": 1,
                    "volume_id": "vol",
                    "key": "test",
                    "value": True,
                },
                {
                    "id": 2,
                    "volume_id": "vol",
                    "key": "how_are_you_doing",
                    "value": "Joe",
                },
                {
                    "id": 3,
                    "volume_id": "vol",
                    "key": "It_always_sunny",
                    "value": False,
                },
            ],
            "volume_glance_metadata": [],
        }

        action, args = _action(fake_src_data, fake_dst_data, fake_deployed)
        data = action.run(**args)

        calls = [
            call(ANY, ('%s '
                       '/var/lib/cinder/80a8c674d115b2a3c20f1e959bd1f20f/'
                       'volume-vol '
                       'dst_user@dst_cinder:/var/lib/cinder/dstdir2a'
                       ) % RSYNC_CMD
                 ),
        ]
        action.cp_volumes.run_repeat_on_errors.assert_has_calls(calls)

        expected = {
            "volumes": [
                {"volume_type_id": None,
                 "host": "dst_cinder",
                 "id": "vol",
                 "status": "available",
                 "attach_status": "detached",
                 "instance_uuid": None,
                 "mountpoint": None,
                 "provider_location": "/var/exports/dst2a",
                 "project_id": DST_TN[TN1['id']],
                 }
            ],
            "volume_metadata": fake_src_data['volume_metadata'],
            "volume_glance_metadata": [],
            "quota_usages": [
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'volumes',
                 'in_use': 1,
                 'reserved': 0,
                 },
                {'project_id': DST_TN[TN1['id']],
                 'resource': 'gigabytes',
                 'in_use': 0,
                 'reserved': 0,
                 },
            ],
        }
        self.assertEqual(data, expected)


class FakeMigration(object):
    def __init__(self, resource):
        self.resource = resource

    @staticmethod
    def migrated_id(obj_id):
        return 'dst_%s' % obj_id


def no_modify(data):
    return data
