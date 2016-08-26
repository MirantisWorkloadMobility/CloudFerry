# Copyright 2016 Mirantis Inc.
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
import abc
import logging
import pickle
import threading
import uuid

from oslo_utils import reflection
from taskflow import retry
from taskflow import task
from taskflow.patterns import linear_flow

from cloudferry import discover
from cloudferry import model
from cloudferry.lib.utils import override
from cloudferry.lib.utils import taskflow_utils
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)


class AbortMigration(Exception):
    """
    Exception that should be raised to abort migration of single resource.
    """

    def __init__(self, message, *args):
        super(AbortMigration, self).__init__(message, *args)

    def __str__(self):
        try:
            return self.args[0] % self.args[1:]
        except Exception:  # pylint: disable=broad-except
            return '{} % {}'.format(repr(self.args[0]), repr(self.args[1:]))


class MigrationFlowFactory(object):
    """
    Base class for migration task flow factories. Class deriving from
    MigrationFlowFactory should define ``migrated_class`` class attribute
    which should be assigned to model class the factory will create migration
    flows for and ``create_flow`` method that should return list of task
    objects.

    Example::

        class TenantMigrationFlowFactory(base.MigrationFlowFactory):
            migrated_class = keystone.Tenant

            def create_flow(self, config, migration, obj):
                return [
                    CreateTenant(obj, config, migration),
                    base.RememberMigration(obj),
                ]
    """

    __metaclass__ = abc.ABCMeta

    migrated_class = None

    @abc.abstractmethod
    def create_flow(self, config, migration, obj):
        """
        Implementing methods should return list of TaskFlow task objects.
        :param config: cloudferry configuration
        :param migration: migration configuration
        :param obj: object to migrate
        :return: list of taskflow.task.Task instances
        """
        return []


class InjectSourceObject(task.Task):
    default_provides = ['source_obj']

    def __init__(self, obj, **kwargs):
        super(InjectSourceObject, self).__init__(
            name='InjectSourceObject_{}'.format(
                taskflow_utils.object_name(obj)),
            **kwargs)
        self.source_obj = obj

    def execute(self, *args, **kwargs):
        LOG.info('Starting to migrate %s with id %s',
                 utils.qualname(self.source_obj.get_class()),
                 self.source_obj.primary_key)
        return [
            {
                'type': self.source_obj.get_class_qualname(),
                'object': self.source_obj.dump(),
            }
        ]

    def revert(self, *args, **kwargs):
        LOG.error('Failed to migrate %s with id %s',
                  utils.qualname(self.source_obj.get_class()),
                  self.source_obj.primary_key)


class MigrationTask(task.Task):
    """
    Base class for object migration tasks that make it easier to write object
    migration tasks by skipping serialization/deserialization of model.Model
    instances.

    Instead of implementing ``execute`` method, tasks deriving from this class
    should implement migrate method.
    """

    def __init__(self, config, migration, obj, name_suffix=None, requires=None,
                 **kwargs):
        name = '{0}_{1}'.format(utils.qualname(self.__class__),
                                taskflow_utils.object_name(obj))
        if name_suffix is not None:
            name += '_' + name_suffix
        if requires is None:
            requires = []
        else:
            requires = list(requires)
        requires.extend(reflection.get_callable_args(self.migrate))

        super(MigrationTask, self).__init__(name=name, requires=requires,
                                            **kwargs)
        self.src_cloud = config.clouds[migration.source]
        self.dst_cloud = config.clouds[migration.destination]
        self.config = config
        self.migration = migration
        self.created_object = None

    @abc.abstractmethod
    def migrate(self, *args, **kwargs):
        """
        Perform any operations necessary for migration and return any objects
        that the task should provide.
        """
        pass

    def rollback(self, *args, **kwargs):
        pass

    def execute(self, *args, **kwargs):
        return self._call(self.migrate, *args, **kwargs)

    def revert(self, *args, **kwargs):
        super(MigrationTask, self).revert(*args, **kwargs)
        self.rollback(
            *[self._deserialize(arg) for arg in args],
            **{key: self._deserialize(value) for key, value in kwargs.items()})

    def _call(self, fn, *args, **kwargs):
        result = fn(
            *[self._deserialize(arg) for arg in args],
            **{key: self._deserialize(value)
               for key, value in kwargs.items()})
        if isinstance(result, list):
            return [self._serialize(val) for val in result]
        elif isinstance(result, dict):
            return [self._serialize(result[key]) for key in self.provides]
        else:
            return result

    @staticmethod
    def _serialize(obj):
        if not hasattr(obj, 'get_class_qualname') or not hasattr(obj, 'dump'):
            return obj
        return {
            'type': obj.get_class_qualname(),
            'object': obj.dump(),
        }

    @staticmethod
    def _deserialize(obj_dict):
        if not isinstance(obj_dict, dict):
            return obj_dict
        if 'type' not in obj_dict:
            return obj_dict
        try:
            model_cls = model.get_model(obj_dict['type'])
        except ImportError:
            return obj_dict
        if not issubclass(model_cls, model.Model):
            return obj_dict
        return model_cls.load(obj_dict['object'])

    def load_from_cloud(self, model_class, cloud, data):
        """
        Returns new model instance based on data from cloud.
        :param model_class: model.Model derived class
        :param cloud: config.Cloud instance
        :param data: data from OpenStack client
        :return: model_class instance
        """
        return discover.load_from_cloud(self.config, cloud, model_class, data)

    def override(self, obj):
        model_class = obj.get_class()
        overrides = self.migration.overrides
        if model_class not in overrides:
            return obj
        return override.OverrideProxy(obj, overrides[model_class])


class Destructor(object):
    @staticmethod
    def get_class_qualname():
        return utils.qualname(Destructor)

    def dump(self):
        return pickle.dumps(self, protocol=-1).encode('base64')

    @classmethod
    def load(cls, data):
        return pickle.loads(data.decode('base64'))

    def run(self, cfg, migration):
        """
        Run the destruction process
        :param cfg: CloudFerry configuration
        :param migration: migration in effect
        :return:
        """
        raise NotImplementedError()

    def get_signature(self):
        """
        Must return hashable object using which it is possible to identify
        destructed object.
        """
        raise NotImplementedError()


class SingletonMigrationTaskMetaclass(abc.ABCMeta):
    def __new__(mcs, name, parents, dct):
        dct['_LOCK'] = threading.Lock()
        dct['_results'] = {}
        return super(SingletonMigrationTaskMetaclass, mcs).__new__(
            mcs, name, parents, dct)


class SingletonMigrationTask(MigrationTask):
    """
    Migration task that execute self.migrate(...) function only once for each
    migration and set of values returned by ``get_singleton_key`` and provides
    destructor object that will be executed in the end of migration.
    """

    # pylint: disable=abstract-method
    __metaclass__ = SingletonMigrationTaskMetaclass

    def __init__(self, config, migration, obj, **kwargs):
        self._is_executed = False
        self.destructor_var = 'destructor_{0}'.format(uuid.uuid4())

        provides = kwargs.pop('provides', [])
        provides.append(self.destructor_var)

        super(SingletonMigrationTask, self).__init__(
            config, migration, obj, provides=provides, **kwargs)

    def execute(self, *args, **kwargs):
        # pylint: disable=no-member
        with self._LOCK:
            key = self._call(self.get_singleton_key, *args, **kwargs)
            if key in self._results:
                return self._results[key]
            self._is_executed = True
            result = super(SingletonMigrationTask, self).execute(*args,
                                                                 **kwargs)
            self._results[key] = result
            return result

    def revert(self, *args, **kwargs):
        # pylint: disable=no-member
        with self._LOCK:
            if self._is_executed:
                super(SingletonMigrationTask, self).revert(*args, **kwargs)
                self._is_executed = False

    def get_singleton_key(self, *args, **kwargs):
        # pylint: disable=unused-argument
        return ()


class DestructorTask(task.Task):
    """
    Task that collect all destructor objects produced by migrations and execute
    them.
    """

    def __init__(self, cfg, migration, requires):
        super(DestructorTask, self).__init__(
            name='GlobalDestructorTask',
            requires=requires)
        self.config = cfg
        self.migration = migration

    def execute(self, *args, **kwargs):
        # pylint: disable=broad-except
        LOG.info('Executing destructors')
        executed_destructors = set()
        for require in self.requires:
            data = kwargs.get(require)
            if not isinstance(data, dict):
                if data is not None:
                    LOG.error('Data for require %s is not dict: %s',
                              require, repr(data))
                continue
            if data.get('type') != Destructor.get_class_qualname():
                LOG.error('Data for require %s is not of destructor type: %s',
                          require, data.get('type'))
                continue
            try:
                destructor = Destructor.load(data['object'])
                signature = (destructor.__class__, destructor.get_signature())
                if signature not in executed_destructors:
                    LOG.debug('Executing destructor %s', repr(destructor))
                    destructor.run(self.config, self.migration)
                    executed_destructors.add(signature)
                else:
                    LOG.debug('Destructor with signature %r already executed.',
                              signature)
            except Exception:
                LOG.error('Failed to run destructor for %s', require,
                          exc_info=True)


class RememberMigration(MigrationTask):
    """
    Task that will store migrated object on destination cloud to local database
    and save link between original and destination object.
    """

    def migrate(self, source_obj, dst_object, *args, **kwargs):
        LOG.debug('Remebering migration: %s -> %s', source_obj, dst_object)
        with model.Session() as session:
            source_obj.link_to(dst_object)
            session.store(dst_object)
            session.store(source_obj)
        LOG.info('Finished migrating %s with id %s to %s',
                 utils.qualname(source_obj.get_class()),
                 source_obj.primary_key, dst_object.primary_key)


def create_migration_flow(obj, config, migration):
    """
    Creates migration flow for object ``obj`` based on configuration ``config``
    migration ``migration``.
    :param obj: model.Model instance
    :param config: configuration
    :param migration: migration (part of configuration)
    :return: migration flow for an object
    """

    if obj.find_link(config.clouds[migration.destination]) is not None:
        return None
    cls = obj.get_class()
    flow_factories = migration.migration_flow_factories
    if cls not in flow_factories:
        raise RuntimeError('Failed to find migration flow factory for ' +
                           repr(cls))
    else:
        flow = linear_flow.Flow('top_level_' + taskflow_utils.object_name(obj),
                                retry=retry.AlwaysRevert())
        factory = flow_factories[cls]()
        migration_tasks = factory.create_flow(config, migration, obj)
        flow.add(InjectSourceObject(obj), *migration_tasks)
        return flow


def add_destructor_task(cfg, migration, graph):
    destructor_requires = []
    for provide in graph.provides:
        if provide.startswith('destructor_'):
            destructor_requires.append(provide)

    destructor_task = DestructorTask(cfg, migration, destructor_requires)

    graph.add(destructor_task)
    for node, _ in graph.iter_nodes():
        if node.name == destructor_task.name:
            continue
        print node
        graph.link(node, destructor_task)
