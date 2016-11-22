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
import itertools
import logging
import os
import traceback

import futurist
from taskflow import engines
from taskflow import exceptions
from taskflow.listeners import base
from taskflow.patterns import graph_flow
from taskflow.persistence import backends
from taskflow.persistence import models
from taskflow import states
from taskflow import task

LOG = logging.getLogger(__name__)
TASK_DATABASE_FILE = os.environ.get('CF_TASK_DB', './tasks.db')
LOGBOOK_ID = 'primary'
MAX_WORKERS = int(os.environ.get('CF_MAX_WORKERS', 4))
STARTING_STATES = frozenset((states.RUNNING, states.REVERTING))
FINISHED_STATES = frozenset((states.SUCCESS, states.REVERTED))
WATCH_STATES = frozenset(itertools.chain(FINISHED_STATES, STARTING_STATES))


def _ensure_db_initialized(conn, flow):
    conn.upgrade()

    need_save = False
    try:
        logbook = conn.get_logbook(LOGBOOK_ID)
    except exceptions.NotFound:
        logbook = models.LogBook(LOGBOOK_ID, uuid=LOGBOOK_ID)
        need_save = True

    flow_detail = logbook.find(flow.name)
    if flow_detail is None:
        flow_detail = models.FlowDetail(flow.name, flow.name)
        logbook.add(flow_detail)
        need_save = True

    if need_save:
        conn.save_logbook(logbook)

    return logbook, flow_detail


def _workaround_reverted_reset(flow_detail):
    have_revert_failures = False
    for task_detail in flow_detail:
        if task_detail.state == 'REVERT_FAILURE':
            old_intention = task_detail.intention
            task_detail.reset('SUCCESS')
            task_detail.intention = old_intention
            have_revert_failures = True

    if have_revert_failures:
        return

    for task_detail in flow_detail:
        if task_detail.state == 'REVERTED':
            task_detail.reset('PENDING')


def execute_flow(flow):
    """
    Create all necessary prerequisites like task database and thread pool and
    execute TaskFlow flow.
    :param flow: TaskFlow flow instance
    """
    backend = backends.fetch({
        'connection': 'sqlite:///' + TASK_DATABASE_FILE,
        'isolation_level': 'SERIALIZABLE'
    })
    executor = futurist.ThreadPoolExecutor(max_workers=MAX_WORKERS)
    conn = backend.get_connection()
    logbook, flow_detail = _ensure_db_initialized(conn, flow)
    engine = engines.load(
        flow, flow_detail=flow_detail, backend=backend, book=logbook,
        engine='parallel', executor=executor)

    engine.compile()
    _workaround_reverted_reset(flow_detail)
    with MetadataSavingListener(engine, flow_detail):
        try:
            engine.run()
        except exceptions.WrappedFailure as wf:
            for failure in wf:
                if failure.exc_info is not None:
                    traceback.print_exception(*failure.exc_info)
                else:
                    print failure


def create_graph_flow(name, objs, subflow_factory_fn, *args, **kwargs):
    """
    Walk over model instances passed in ``objs`` list and their dependencies
    and create graph flow using ``subflow_factory_fn`` function in order to
    create subflow for each object and/or dependency.
    :param name: name of resulting flow
    :param objs: iterable of objects
    :param subflow_factory_fn: function that will create subflows
    :param args: additional positional arguments that will be passed to subflow
                 factory function
    :param kwargs: additional named arguments that will be passed to subflow
                   factory function
    :return: graph flow instance
    """
    def _create_and_link_subflow(obj):
        obj_id = obj.primary_key
        if obj_id in created:
            return created[obj_id]
        subflow = subflow_factory_fn(obj, *args, **kwargs)
        if subflow is None:
            return None
        graph.add(subflow)
        created[obj_id] = subflow
        for dep in obj.dependencies():
            dep_subflow = _create_and_link_subflow(dep)
            if dep_subflow is not None:
                graph.link(dep_subflow, subflow)
        return subflow

    created = {}
    graph = graph_flow.Flow(name)
    for obj in objs:
        _create_and_link_subflow(obj)
    return graph


def object_name(obj):
    """
    Create unique object name based on object type and primary key.
    :param obj: model instance
    :return: unique name (string)
    """
    object_id = obj.primary_key
    return '{typename}_{cloud}_{uuid}'.format(
        typename=obj.get_class_qualname(),
        cloud=object_id.cloud,
        uuid=object_id.id)


class Conditional(task.Task):
    """
    Task that will execute subtask only if required parameter is evaluated to
    True.
    """

    def __init__(self, parameter_name, subtask):
        requires = subtask.requires
        if parameter_name not in requires:
            requires = list(requires)
            requires.append(parameter_name)
        super(Conditional, self).__init__(subtask.name, requires=requires,
                                          provides=subtask.provides)
        self.parameter_name = parameter_name
        self.task = subtask

    def execute(self, *args, **kwargs):
        if kwargs.pop(self.parameter_name, False):
            LOG.debug('Running %s because \'%s\' is True', self.task.name,
                      self.parameter_name)
            return self.task.execute(*args, **kwargs)
        else:
            LOG.debug('Not running %s because \'%s\' is False', self.task.name,
                      self.parameter_name)
            return [None] * len(self.task.provides)


class MetadataSavingListener(base.Listener):
    """Listener that store task internal state to storage as metadata."""

    def __init__(self, engine, flow_detail):
        self.flow_detail = flow_detail
        super(MetadataSavingListener, self).__init__(
            engine, task_listen_for=WATCH_STATES)

    def _task_receiver(self, state, details):
        task_name = details['task_name']
        task_uuid = details['task_uuid']

        engine = self._engine
        storage = engine.storage
        hierarchy = engine.compilation.hierarchy

        node = hierarchy.find_first_match(lambda x: x.item.name == task_name)
        if node is None:
            LOG.warning('Could not find task with name "%s"', task_name)
            return

        the_task = node.item
        if state in FINISHED_STATES:
            if not hasattr(the_task, 'save_internal_state'):
                return
            internal_state = the_task.save_internal_state()
            if internal_state is None:
                return
            storage.update_atom_metadata(task_name,
                                         {'internal_state': internal_state})
        elif state in STARTING_STATES:
            if hasattr(the_task, 'restore_internal_state'):
                atom_detail = self.flow_detail.find(task_uuid)
                if not atom_detail:
                    return
                internal_state = atom_detail.meta.get('internal_state')
                if not internal_state:
                    return
                the_task.restore_internal_state(internal_state)
