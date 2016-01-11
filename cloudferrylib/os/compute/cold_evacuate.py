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
import cfglib
import contextlib
import time
import os
from Crypto.PublicKey import RSA

from novaclient import exceptions as nova_exc

from cloudferrylib.base import exception
from cloudferrylib.utils import proxy_client
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import log

LOG = log.getLogger(__name__)

# How many times to take calling function successfully before giving up
# by default
RETRY_ON_EXCEPTION_DEFAULT_MAX_ATTEMPTS = 5

# TODO: create module with constants from cold_evacuate and nova_compute
INSTANCE_HOST_ATTRIBUTE = 'OS-EXT-SRV-ATTR:host'
INSTANCE_NAME_ATTRIBUTE = 'OS-EXT-SRV-ATTR:instance_name'
NOVA_SERVICE = 'nova-compute'
SERVICE_DISABLED = 'disabled'
SERVICE_ENABLED = 'enabled'

ACTIVE = 'active'
SHUTOFF = 'shutoff'
VERIFY_RESIZE = 'verify_resize'
SUSPENDED = 'suspended'
PAUSED = 'paused'
ERROR = 'error'

SUPPORTED_FINAL_STATES = [
    ACTIVE, SUSPENDED, PAUSED, SHUTOFF, VERIFY_RESIZE, ERROR
]


@contextlib.contextmanager
def disable_all_nova_compute_services(compute_api):
    """
    Disable all nova-compute services before decorated function will execute
    and enable previously disabled services after.
    :param compute_api: NovaClient instance
    :return:
    """
    LOG.debug("Disabling ALL nova-compute services.")
    services = compute_api.services.list(binary=NOVA_SERVICE)
    temporary_disabled_services = []
    for service in services:
        if service.status == SERVICE_DISABLED:
            continue
        temporary_disabled_services.append(service.host)
        compute_api.services.disable(service.host, NOVA_SERVICE)

    try:
        yield
    finally:
        LOG.debug("Enabling previously disabled nova-compute services.")
        for service_host in temporary_disabled_services:
            compute_api.services.enable(service_host, NOVA_SERVICE)


@contextlib.contextmanager
def enable_nova_compute_services(compute_api, *hosts):
    """
    Disable nova-compute services on hosts listed in *hosts before decorated
    function will execute and disable previously enabled services after.
    :param compute_api:
    :param hosts:
    :return:
    """
    LOG.debug("Enabling %s nova-compute services.", ', '.join(hosts))
    services = compute_api.services.list(binary=NOVA_SERVICE)
    temporary_enabled_services = []
    for service in services:
        if service.host not in hosts:
            continue
        if service.status == SERVICE_ENABLED:
            continue
        temporary_enabled_services.append(service.host)
        compute_api.services.enable(service.host, NOVA_SERVICE)

    try:
        yield
    finally:
        LOG.debug("Disabling %s nova-compute services.",
                  ', '.join(temporary_enabled_services))
        for service_host in temporary_enabled_services:
            compute_api.services.disable(service_host, NOVA_SERVICE)


def is_vm_deleted(client, instance_id):
    """
    Returns True when there is no VM with ID provided in first argument.
    """
    try:
        with proxy_client.expect_exception(nova_exc.NotFound):
            client.servers.get(instance_id)
        return False
    except nova_exc.NotFound:
        return True


def is_vm_status_in(client, instance_id, statuses):
    """
    Returns True when nova instance with ID that is equal to instance_id
    argument have status that is equal to status argument.
    """
    statuses = [s.lower() for s in statuses]
    try:
        with proxy_client.expect_exception(nova_exc.NotFound):
            instance = client.servers.get(instance_id)
        status = instance.status.lower()
        if status == ERROR:
            raise RuntimeError("VM in error status")
        return status in statuses
    except nova_exc.NotFound:
        return False


# TODO: move following function to utils and reuse in other parts of CloudFerry
def wait_for_condition(condition_fn, *args, **kwargs):
    """
    Periodically calls condition_fn function passing args as positional
    arguments and kwargs as keyword arguments and terminate when this function
    will return True.
    If after timeout seconds function didn't terminate, TimeoutException is
    raised.
    :param condition_fn: predicate function
    :param timeout: for how many seconds to wait for condition_fn to return
                    True before raising TimeoutException
    :raise TimeoutException: when function didn't terminate after timeout
                             seconds
    """
    timeout = kwargs.pop('timeout', 60)
    delay = 1
    while delay <= timeout:
        if condition_fn(*args, **kwargs):
            break
        time.sleep(delay)
        delay *= 2
    else:
        raise exception.TimeoutException(None, None, "Timeout exp")


# TODO: move following function to utils and reuse in other parts of CloudFerry
def retry_on_exception(func, *args, **kwargs):
    """
    Call func with args as positional arguments and kwargs as keyword arguments
    and return result.
    I function fails (e.g. raise an exception) then retry_on_error try to call
    it again up to max_attempts times until it succeeds.
    :param func: function to call
    :param args: positional arguments to pass when calling func
    :param kwargs: keyword arguments to pass when calling func
    :param max_attempts: maximum number of unsuccessful attempts before
                         giving up
    :return: whatever func will return
    """

    max_attempts = kwargs.pop('max_attempts',
                              RETRY_ON_EXCEPTION_DEFAULT_MAX_ATTEMPTS)
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as ex:  # pylint: disable=broad-except
            LOG.warning("Attempt #%d: failed to call function %s",
                        attempt, func.__name__, exc_info=True)
            if attempt == max_attempts:
                LOG.error("Giving up to successfully call %s after %d "
                          "attempts", func.__name__, attempt)
                raise ex


# TODO: move following function to utils and reuse in other parts of CloudFerry
def suppress_exceptions(func, *args, **kwargs):
    """
    Call func with args as positional arguments and kwargs as keyword arguments
    and return result suppressing any exception raised.
    :param func: function to call
    :param args: positional arguments to pass when calling func
    :param kwargs: keyword arguments to pass when calling func
    :return: whatever func will return
    """
    try:
        return func(*args, **kwargs)
    except Exception:  # pylint: disable=broad-except
        LOG.warning("Exception suppressed", exc_info=True)


def cold_evacuate(config, compute_api, instance_id, dst_host):
    """
    Evacuate VM by shutting it down, booting another VM with same ephemeral
    volume on different host and deleting original VM.

    :param config: CloudFerry configuration
    :param compute_api: Compute API client (NovaClient) instance
    :param instance_id: VM instance identifier to evacuate
    :param dst_host: destination host name
    """
    LOG.debug("Cold evacuating VM %s to %s", instance_id, dst_host)
    state_change_timeout = cfglib.CONF.evacuation.state_change_timeout
    migration_timeout = cfglib.CONF.evacuation.migration_timeout

    # Check instance status
    if not change_to_pre_migration_state(compute_api, instance_id):
        instance = compute_api.servers.get(instance_id)
        LOG.warning('Can\'t migrate VM in %s status', instance.status)
        return

    # Check if instance already on target host
    instance = compute_api.servers.get(instance_id)
    src_host = getattr(instance, INSTANCE_HOST_ATTRIBUTE)
    if src_host == dst_host:
        LOG.warning("Skipping migration to the same host")
        return

    # Turn off instance if it's running
    original_status = instance.status.lower()
    if original_status != SHUTOFF:
        compute_api.servers.stop(instance)
        wait_for_condition(is_vm_status_in, compute_api, instance,
                           [SHUTOFF], timeout=state_change_timeout)

    # Fix disk images broken by cobalt migrate
    fix_post_cobalt_ephemeral_disk(config, instance)

    with install_ssh_keys(config, src_host, dst_host):
        with disable_all_nova_compute_services(compute_api):
            with enable_nova_compute_services(compute_api, dst_host, src_host):
                compute_api.servers.migrate(instance)
                wait_for_condition(is_vm_status_in, compute_api, instance,
                                   [VERIFY_RESIZE],
                                   timeout=migration_timeout)
                compute_api.servers.confirm_resize(instance)
                wait_for_condition(is_vm_status_in, compute_api, instance,
                                   [ACTIVE], timeout=state_change_timeout)

    # Restore original status
    if original_status == SHUTOFF.lower():
        LOG.debug("Starting replacement VM %s", instance_id)
        compute_api.servers.stop(instance_id)


@contextlib.contextmanager
def install_ssh_keys(config, *hosts):
    """
    Generate and put public and private SSH keys to hosts that are listed in
    hosts to make cold migration work.
    :param config: CloudFerry config
    :param hosts: list of hosts where to install keys
    """
    ssh_user = config.cloud.ssh_user
    ssh_password = config.cloud.ssh_sudo_password
    home_path = cfglib.CONF.evacuation.nova_home_path
    nova_user = cfglib.CONF.evacuation.nova_user
    ssh_config = '\\n'.join(['UserKnownHostsFile /dev/null',
                             'StrictHostKeyChecking no'])
    ssh_path = '/'.join([home_path, '.ssh'])
    ssh_backup_base = '/'.join([home_path, '.ssh_backup'])

    key = RSA.generate(2048, os.urandom)
    public_key = key.exportKey('OpenSSH').replace('\n', '\\n')
    private_key = key.exportKey('PEM').replace('\n', '\\n')

    ssh_backups = {}
    for host in hosts:
        runner = remote_runner.RemoteRunner(host, ssh_user,
                                            password=ssh_password,
                                            sudo=True)
        ssh_backup_path = '/'.join([ssh_backup_base,
                                    os.urandom(8).encode('hex')])
        try:
            runner.run('test -e "{path}"', path=ssh_path)
            runner.run('mkdir -p {backup_base}', backup_base=ssh_backup_base)
            runner.run('mv "{path}" "{backup_path}"', path=ssh_path,
                       backup_path=ssh_backup_path)
            ssh_backups[host] = ssh_backup_path
        except remote_runner.RemoteExecutionError:
            LOG.debug("Dot SSH directory not found, skipping backup")

        runner.run('mkdir -p "{path}"', path=ssh_path)
        runner.run('echo -e "{key}" > "{path}"', key=public_key,
                   path='/'.join([ssh_path, 'authorized_keys']))
        runner.run('echo -e "{key}" > "{path}"', key=private_key,
                   path='/'.join([ssh_path, 'id_rsa']))
        runner.run('echo -e "{config}" > "{path}"', config=ssh_config,
                   path='/'.join([ssh_path, 'config']))
        runner.run('chmod 0600 "{path}"', path='/'.join([ssh_path, 'id_rsa']))
        runner.run('chown -R "{user}:{user}" "{path}"',
                   user=nova_user, path=ssh_path)
    try:
        yield
    finally:
        for host in hosts:
            runner = remote_runner.RemoteRunner(host, ssh_user,
                                                password=ssh_password,
                                                sudo=True)
            runner.run('rm -rf "{path}"', path=ssh_path)
            ssh_backup_path = ssh_backups.get(host)
            if ssh_backup_path is not None:
                runner.run_ignoring_errors(
                    'mv "{backup_path}" "{path}"',
                    backup_path=ssh_backup_path, path=ssh_path)


# TODO: looks similar to .nova_compute.NovaCompute#change_status, refactor
def change_to_pre_migration_state(compute_api, instance_id):
    """
    Try to change instance status to one that is supported by nova migrate.
    :param compute_api: NovaClient instance
    :param instance_id: VM instance identifier
    :return:
    """
    state_change_timeout = cfglib.CONF.evacuation.state_change_timeout
    for _ in range(2):
        instance = compute_api.servers.get(instance_id)
        state = instance.status.lower()
        if state not in SUPPORTED_FINAL_STATES:
            try:
                LOG.debug('Waiting for VM %s to transit to one of folliwing '
                          'states: %s',
                          instance_id, ', '.join(SUPPORTED_FINAL_STATES))
                wait_for_condition(is_vm_status_in, compute_api, instance_id,
                                   SUPPORTED_FINAL_STATES,
                                   timeout=state_change_timeout)
            except exception.TimeoutException:
                return False
        if state in (ACTIVE, SHUTOFF):
            return True
        if state == ERROR:
            return False
        if state == VERIFY_RESIZE:
            compute_api.servers.confirm_resize(instance_id)
        if state == SUSPENDED:
            compute_api.servers.resume(instance_id)
        if state == PAUSED:
            compute_api.servers.unpause(instance_id)
    return False


def fix_post_cobalt_ephemeral_disk(config, instance):
    """
    Merge ephemeral disk chain if it was broken by cobalt migrate
    :param config: cloud configuration
    :param instance: VM instance (as returned by NovaClient)
    """

    host = getattr(instance, INSTANCE_HOST_ATTRIBUTE)
    instance_name = getattr(instance, INSTANCE_NAME_ATTRIBUTE)

    ssh_user = config.cloud.ssh_user
    ssh_password = config.cloud.ssh_sudo_password
    runner = remote_runner.RemoteRunner(host, ssh_user,
                                        password=ssh_password,
                                        sudo=True)
    blkinfo = runner.run('virsh domblklist {name}', name=instance_name)
    for line in blkinfo.splitlines():
        if instance.id not in line:
            continue
        tokens = line.split()
        if len(tokens) < 2:
            continue
        _, path = tokens[:2]
        if instance.id not in path:
            continue
        cobalt_base_path = path + '.base'
        info = runner.run('qemu-img info {input}', input=path)
        if cobalt_base_path not in info:
            continue
        merge_path = path + '.merge'
        runner.run('qemu-img convert -f qcow2 -O qcow2 {input} {output} &&'
                   'mv {output} {input}',
                   input=path, output=merge_path)
