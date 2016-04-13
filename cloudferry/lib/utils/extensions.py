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

import importlib
import inspect
import logging
import os
import pkgutil
import threading

LOG = logging.getLogger(__name__)


_extensions_cache = {}
_extensions_lock = threading.Lock()


def available_extensions(base_class, path):
    """ Dynamically loading modules and searching the extensions

    :param base_class: The class of extensions to be loaded.
    :param path: The path of root package.
    :return: The list of the extensions
    """

    with _extensions_lock:
        key = (base_class, path)
        if key in _extensions_cache:
            return _extensions_cache[key]

        def print_log(m, e=None):
            LOG.warning("Cannot import module '%s'", m)
            if e is not None:
                LOG.debug(e, exc_info=True)

        extensions = []
        LOG.debug("Scanning available '%s' extensions for %s",
                  base_class, path)
        root_module = importlib.import_module(path)
        module_path = os.path.dirname(root_module.__file__)
        packages = pkgutil.walk_packages(
            path=[module_path],
            prefix=path + '.',
            onerror=print_log)
        for _, name, is_pkg in packages:
            if not is_pkg:
                try:
                    module = importlib.import_module(name)
                except Exception:  # pylint: disable=broad-except
                    print_log(name)
                    continue
                members = inspect.getmembers(module, inspect.isclass)
                for item, klass in members:
                    if klass != base_class and issubclass(klass, base_class):
                        LOG.debug("Extension '%s' found!", item)
                        extensions.append(klass)

        if extensions:
            _extensions_cache[key] = extensions
        else:
            LOG.error("Extensions not found")

        return extensions
