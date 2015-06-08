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

from cfglib import CONF


# we don't want to create connection to database on module import - so that
# we will create it only on first database call
# also we don't want all users to install redis-client


CONNECTION = [None]


def redis_socket_to_kwargs(function):
    def wrapper(*args, **kwargs):
        if not CONNECTION[0]:
            import redis
            CONNECTION[0] = redis.StrictRedis(
                host=CONF.database.host,
                port=CONF.database.port)
        return function(*args, connection=CONNECTION[0], **kwargs)
    return wrapper


@redis_socket_to_kwargs
def put(key, value, connection):
    connection.set(key, value)


@redis_socket_to_kwargs
def get(key, connection):
    return connection.get(key)


@redis_socket_to_kwargs
def delete(key, connection):
    return connection.delete(key)

@redis_socket_to_kwargs
def delete_batch(keys, connection):
    pipe = connection.pipeline()
    for key in keys:
        pipe.delete(key)
    pipe.execute()

@redis_socket_to_kwargs
def keys(pattern, connection):
    return connection.keys(pattern)
