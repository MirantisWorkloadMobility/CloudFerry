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


from cloudferrylib.base import Storage
from cinderclient.v1 import client as cinderClient

__author__ = 'toha'


class CinderStorage(Storage.Storage):

    """
    The main class for working with Openstack cinder client
    """

    def __init__(self, config):
        self.config = config
        self.cinder_client = self.get_cinder_client(self.config)
        super(CinderStorage, self).__init__()

    def get_cinder_client(self, params):

        """ Getting cinder client """

        return cinderClient.Client(params["user"],
                                   params["password"],
                                   params["tenant"],
                                   "http://" + params["host"] + ":35357/v2.0/")
