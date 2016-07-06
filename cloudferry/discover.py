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

from cloudferry import model
from cloudferry.lib.utils import bases
from cloudferry.lib.utils import retrying
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)


class NotFound(Exception):
    pass


class DiscovererNotFound(bases.ExceptionWithFormatting):
    """
    Exception that should be raised to abort migration of single resource.
    """

    def __init__(self, discoverer_class, *args):
        super(DiscovererNotFound, self).__init__(
            'Discoverer for % not found.',
            utils.qualname(discoverer_class), *args)


class Discoverer(object):
    __metaclass__ = abc.ABCMeta
    discovered_class = None

    def __init__(self, config, cloud):
        self.config = config
        self.cloud = cloud

    @abc.abstractmethod
    def discover_all(self):
        """
        Method should get list of all objects in the cloud, convert them to
        ``model.Model`` instances using ``load`` classmethod and store them to
        database.
        """
        return

    @abc.abstractmethod
    def discover_one(self, uuid):
        """
        Method should retrieve object from the cloud using it's unique
        identifier ``uuid``, convert it to ``model.Model`` instances using
        ``load`` classmethod and return it.
        """
        return

    @abc.abstractmethod
    def load_from_cloud(self, data):
        """
        Method should convert data retrieved using OpenStack client to
        ``model.Model`` instances using ``load`` classmethod and return it.
        """
        return

    def find_obj(self, model_class, uuid):
        """
        Find instance of ``model_class`` in local database or through single
        object discovery (if absent in local database).
        :param model_class: model class object
        :param uuid: object identifier
        :return: model class instance
        """
        model_qualname = utils.qualname(model_class)
        LOG.debug('Trying to find %s with ID %s in cloud %s',
                  model_qualname, uuid, self.cloud.name)
        if uuid is None:
            return None
        object_id = model.ObjectId(uuid, self.cloud.name)
        try:
            with model.Session() as session:
                if session.is_missing(model_class, object_id):
                    LOG.debug('Object %s with ID %s is stored as missing',
                              model_qualname, object_id)
                    return None
                return session.retrieve(model_class, object_id)
        except model.NotFound:
            LOG.debug('Object %s with ID %s not found in local database',
                      model_qualname, object_id)

        try:
            discoverer_class = self.cloud.discoverers.get(model_class)
            if discoverer_class is None:
                LOG.warning('Can\'t find discoverer class for %s',
                            model_qualname)
                raise DiscovererNotFound(model_class)
            LOG.debug('Trying to discover %s with ID %s using %s',
                      model_qualname, object_id,
                      utils.qualname(discoverer_class))
            discoverer = discoverer_class(self.config, self.cloud)
            return discoverer.discover_one(uuid)
        except NotFound:
            LOG.warning('Object %s with uuid %s not found in cloud %s',
                        model_class.get_class_qualname(), uuid,
                        self.cloud.name)
            with model.Session() as session:
                session.store_missing(
                    model_class, model.ObjectId(uuid, self.cloud.name))
        except model.ValidationError as e:
            LOG.warning('Invalid %s with uuid %s in cloud %s: %s',
                        model_class.get_class_qualname(), uuid,
                        self.cloud.name, e)
            return None

    def find_ref(self, model_class, uuid):
        """
        Find instance of ``model_class`` in local database or through single
        object discovery (if absent in local database) and return serialized
        form of reference.
        :param model_class: model class object
        :param uuid: object identifier
        :return: dictionary
        """
        obj = self.find_obj(model_class, uuid)
        if obj is None:
            return None
        else:
            return obj.primary_key.to_dict(obj.get_class())

    def make_id(self, uuid):
        """
        Returns serialized form of identifier for objects that are discovered
        by discoverer.
        :param uuid: object unique identifier
        :return: dictionary
        """
        return self.make_ref(self.discovered_class, uuid)

    def make_ref(self, model_class, uuid):
        """
        Returns serialized form of identifier for objects that are referenced
        by discovered objects.
        :param model_class: referenced object class
        :param uuid: object unique identifier
        :return: dictionary
        """
        return {
            'id': uuid,
            'cloud': self.cloud.name,
            'type': model_class.get_class_qualname(),
        }

    def retry(self, func, *args, **kwargs):
        """
        Call function passed as first argument passing any remaining arguments
        and keyword arguments. If function fail with exception, it is called
        again after waiting for few seconds (specified by
        ``OpenstackCloud.request_attempts`` configuration parameter). It stops
        retrying after ``OpenstackCloud.request_failure_sleep`` unsuccessful
        attempts were made.
        :param func: function, bound method or some other callable
        :param expected_exceptions: tuple/list of exceptions that are expected
                                    and handled, e.g. there is no need to retry
                                    if such exception is caught
        :param returns_iterable: set it to True if func is expected to return
                                 iterable
        :return: whatever func returns
        """
        expected_exceptions = kwargs.pop('expected_exceptions', None)
        returns_iterable = kwargs.pop('returns_iterable', False)

        retry = retrying.Retry(
            max_attempts=self.cloud.request_attempts,
            timeout=self.cloud.request_failure_sleep,
            expected_exceptions=expected_exceptions,
            reraise_original_exception=True)
        if returns_iterable:
            return retry.run(lambda *a, **kw: [x for x in func(*a, **kw)],
                             *args, **kwargs)
        else:
            return retry.run(func, *args, **kwargs)


def discover_all(cfg, cloud):
    """
    Discovers all objects using discoverers specified for the cloud.
    :param cfg: config.Configuration instance
    :param cloud: config.Cloud instance
    """
    for discoverer_class in cloud.discoverers.values():
        LOG.debug('Starting discovering %s using %s',
                  utils.qualname(discoverer_class.discovered_class),
                  utils.qualname(discoverer_class))
        discoverer = discoverer_class(cfg, cloud)
        discoverer.discover_all()
        LOG.debug('Finished discovering %s using %s',
                  utils.qualname(discoverer_class.discovered_class),
                  utils.qualname(discoverer_class))


def load_from_cloud(cfg, cloud, model_class, data):
    discoverer_class = cloud.discoverers.get(model_class)
    if discoverer_class is None:
        LOG.error('Can\'t find discoverer for %s', utils.qualname(model_class))
        raise DiscovererNotFound(model_class)
    discoverer = discoverer_class(cfg, cloud)
    return discoverer.load_from_cloud(data)
