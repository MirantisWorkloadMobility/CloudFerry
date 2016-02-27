# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from cloudferrylib.base import exception
from cloudferrylib.os.storage.plugins import base
from cloudferrylib.os.storage.plugins import copy_mechanisms
from cloudferrylib.utils import extensions
from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


class InvalidCinderPluginError(exception.AbortMigrationError):
    pass


def get_cinder_backend(context):
    """:returns: instance of cinder plugin"""

    cloud = context.position
    storage_config = context.config['{cloud}_storage'.format(cloud=cloud)]
    configured_backend = storage_config.backend

    for plugin in extensions.available_extensions(base.CinderMigrationPlugin,
                                                  __name__):
        if configured_backend.lower() == plugin.PLUGIN_NAME:
            return plugin.from_context(context)

    msg = ("Invalid cinder plugin '{plugin}' specified in "
           "config".format(plugin=configured_backend))
    raise InvalidCinderPluginError(msg)


def copy_mechanism_from_plugin_names(src_plugin_name, dst_plugin_name):
    """Factory to build data copy mechanism from plugin names"""
    if src_plugin_name == "nfs" and dst_plugin_name == "nfs":
        return copy_mechanisms.RemoteFileCopy()
    elif src_plugin_name == "nfs" and dst_plugin_name == "iscsi-vmax":
        return copy_mechanisms.CopyRegularFileToBlockDevice()
    else:
        msg = "{src} to {dst} volume migration is not supported"
        raise NotImplementedError(msg.format(src=src_plugin_name,
                                             dst=dst_plugin_name))
