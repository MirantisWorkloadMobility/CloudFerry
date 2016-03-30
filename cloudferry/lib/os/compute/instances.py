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

from cloudferry.lib.base import clients
from cloudferry.lib.utils import log


LOG = log.getLogger(__name__)


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


class FlavorAccess(object):
    def __init__(self, flavor_id=None, tenant_id=None):
        self.flavor_id = flavor_id
        self.tenant_id = tenant_id

    @classmethod
    def from_db(cls, db_record):
        return cls(flavor_id=db_record['flavorid'],
                   tenant_id=db_record['project_id'])

    @classmethod
    def from_novaclient_object(cls, nc_flavor_access):
        return cls(flavor_id=nc_flavor_access.flavor_id,
                   tenant_id=nc_flavor_access.tenant_id)


def get_flavor_access_list_from_db(db, flavor_id):
    sql = ("SELECT it.flavorid, itp.project_id "
           "FROM instance_types it "
           "RIGHT JOIN instance_type_projects itp "
           "ON it.id = itp.instance_type_id "
           "WHERE it.flavorid = :flavor_id AND it.deleted = 0;")
    return db.execute(sql, flavor_id=flavor_id)


def nova_live_migrate_vm(nova_client, config, vm_id, dest_host):
    LOG.info("migrating %s to %s using nova live migrate", vm_id, dest_host)
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
    LOG.info("migrating %s to %s using Cobalt", vm_id, dest_host)

    host_string = "{user}@{host}".format(
        user=config.cloud.ssh_user, host=config.cloud.ssh_host)

    with settings(warn_only=True,
                  host_string=host_string,
                  key_filename=config.migrate.key_filename,
                  connection_attempts=config.migrate.ssh_connection_attempts):
        migrate_cmd = clients.os_cli_cmd(config.cloud, "nova",
                                         "cobalt-migrate", vm_id,
                                         "--dest", dest_host)

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
