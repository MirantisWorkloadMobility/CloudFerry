# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from fabric.api import run
from fabric.api import settings


from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


def update_user_ids_for_instance(db, instance_id, user_id):
    sql = ("UPDATE nova.instances "
           "SET nova.instances.user_id = '{user_id}' "
           "WHERE nova.instances.uuid = '{instance_id}';").format(
        user_id=user_id, instance_id=instance_id)
    db.execute(sql)


def get_flav_details(db, instance_id):
    sql = ("SELECT vcpus,memory_mb,root_gb,ephemeral_gb "
           "FROM nova.instances "
           "WHERE nova.instances.uuid = '{instance_id}' "
           "AND NOT nova.instances.vm_state = 'deleted';").format(
        instance_id=instance_id)
    res = db.execute(sql)
    for row in res:
        return {'vcpus': row['vcpus'],
                'memory_mb': row['memory_mb'],
                'root_gb': row['root_gb'],
                'ephemeral_gb': row['ephemeral_gb']}


def nova_live_migrate_vm(nova_client, config, vm_id, dest_host):
    LOG.info("migrating {vm} to {host} using nova live migrate".format(
        vm=vm_id,
        host=dest_host
    ))
    nova_client.servers.live_migrate(
        server=vm_id,
        host=dest_host,
        block_migration=config.compute.block_migration,
        disk_over_commit=config.compute.disk_overcommit
    )


def cobalt_live_migrate_vm(config, vm_id, dest_host):
    """Cobalt live migration is implemented as nova extension, so it's not
    reachable through standard `novaclient.v1_1.Client()` instance
    (or at least I was unable to find a way in a reasonable timeframe). Thus
    running it as a CLI command."""
    LOG.info("migrating {vm} to {host} using Cobalt".format(
        vm=vm_id,
        host=dest_host
    ))

    host_string = "{user}@{host}".format(
        user=config.cloud.ssh_user, host=config.cloud.ssh_host)

    with settings(warn_only=True, host_string=host_string,
                  key_filename=config.migrate.key_filename):
        migrate_cmd = ("nova "
                       "--os-tenant-name={tenant} "
                       "--os-username={username} "
                       "--os-password={password} "
                       "--os-auth-url={auth_url} "
                       "cobalt-migrate {vm_id} "
                       "--dest {dest_host}").format(
            tenant=config.cloud.tenant,
            username=config.cloud.user,
            password=config.cloud.password,
            auth_url=config.cloud.auth_url,
            vm_id=vm_id,
            dest_host=dest_host
        )

        LOG.debug(migrate_cmd)

        run(migrate_cmd)


def incloud_live_migrate(nova_client, config, vm_id, destination_host):
    migration_tool = config.migrate.incloud_live_migration
    if migration_tool == 'nova':
        nova_live_migrate_vm(nova_client, config, vm_id, destination_host)
    elif migration_tool == 'cobalt':
        cobalt_live_migrate_vm(config, vm_id, destination_host)
    else:
        raise NotImplementedError(
            "You're trying to use live migration tool "
            "which is not available: '%s'", migration_tool)
