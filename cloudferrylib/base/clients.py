# Copyright 2015 Mirantis Inc.
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

"""
Keeps logic for Openstack Clients used in CF
"""


def os_cli_cmd(config, client, *args):
    """
    Builds Openstack CLI command based on arguments and configuration used.

    :arg config: CF primary configuration object
    :arg client: Openstack CLI client (neutron, nova, glance, etc)
    :arg args: positional arguments passed to Openstack client, will be
    appended to the end of the generated command
    :returns: string with full CLI command
    """

    opts = {
        "--os-tenant-name": config.tenant,
        "--os-username": config.user,
        "--os-password": config.password,
        "--os-auth-url": config.auth_url,
    }

    if config.region:
        opts["--os-region-name"] = config.region

    client_opts = " ".join([" ".join([k, v]) for k, v in opts.iteritems()])
    arguments = " ".join(args)

    cmd = "{client} {options} {arguments}".format(
        client=client,
        options=client_opts,
        arguments=arguments
    )

    return cmd
