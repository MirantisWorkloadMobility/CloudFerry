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
import jmespath
import jmespath.exceptions

from cloudferrylib.os.discovery import model


class DictSubQuery(object):
    """
    Simplified query that use JMESPath queries as dictionary keys to get value
    from tested object and then compare it to list of objects specified in
    value.

    Example:

        objects:
          images:
            - tenant.name: demo
              container_format: bare

    This query will select all images with owner named 'demo' and container
    format 'bare'

    Adding !in front of query will negate match result. For example:

        objects:
          vms:
            - !tenant.name: rally_test

    This query will select all VMs in cloud except for rally_test tenant
    """

    def __init__(self, pattern):
        assert isinstance(pattern, dict)
        self.pattern = [self._compile_query(k, v) for k, v in pattern.items()]

    def search(self, values):
        """
        Return subset of values that match query parameters.
        :param values: list of objects that have get method
        :return: list of objects that matched query
        """
        return [v for v in values if self._matches(v)]

    def _matches(self, value):
        return all(match(value) for match in self.pattern)

    @staticmethod
    def _compile_query(key, expected):
        assert isinstance(key, basestring)

        negative = False
        if key.startswith('!'):
            negative = True
            key = key[1:]
        try:
            query = jmespath.compile(key)

            def match(value):
                return negative ^ (query.search(value) in expected)
            return match
        except jmespath.exceptions.ParseError as ex:
            raise AssertionError(
                'Failed to compile "{0}": {1}'.format(key, str(ex)))


class Query(object):
    """
    Parsed and compiled query using which it is possible to filter instances of
    model.Model class stored in database.
    """

    def __init__(self, query):
        """
        Accept dict as specified in configuration, compile all the JMESPath
        queries, and store it as internal immutable state.
        :param query: query dictionary
        """

        assert isinstance(query, dict)

        self.queries = {}
        for type_name, subqueries in query.items():
            cls = model.get_model(type_name)
            for subquery in subqueries:
                if isinstance(subquery, basestring):
                    subquery = jmespath.compile(subquery)
                else:
                    subquery = DictSubQuery(subquery)
                cls_queries = self.queries.setdefault(cls, [])
                cls_queries.append(subquery)

    def search(self, session, cloud=None, cls=None):
        """
        Search through list of objects from database of class that specified
        in cls argument (if cls is none, then all classes are considered) that
        are collected from cloud specified in cloud argument (if cloud is none,
        then all clouds are considered) for objects matching this query.

        :param session: active model.Session instance
        :param cloud: cloud name
        :param cls: class object
        :return: list of objects that match query
        """
        result = set()
        if cls is None:
            for cls, queries in self.queries.items():
                objects = session.list(cls, cloud)
                for query in queries:
                    result.update(query.search(objects))
            return result
        else:
            queries = self.queries.get(cls)
            if queries is None:
                return []
            objects = session.list(cls, cloud)
            for query in queries:
                result.update(query.search(objects))
            return result
