# Copyright (c) 2015 Mirantis Inc.
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


import signal

DEFAULT_SIGNALS = [signal.SIGINT, signal.SIGTERM]


class BaseInterruptHandler(object):
    def __init__(self, sig_list=None):
        if sig_list is None:
            self.sig_list = DEFAULT_SIGNALS
        else:
            self.sig_list = (sig_list
                             if isinstance(sig_list, list) else [sig_list])
        self.released = None
        self.original_handler = None

    def __enter__(self):
        self.released = False
        self.original_handler = {}
        for sig in self.sig_list:
            self.original_handler[sig] = signal.getsignal(sig)
        self.enter()
        return self

    def enter(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        self.exit(exc_type, exc_value, traceback)

    def exit(self, exc_type, exc_value, traceback):
        pass

    def release(self):
        if not self.released:
            for sig in self.sig_list:
                signal.signal(sig, self.original_handler[sig])
            self.released = True


class IgnoreInterruptHandler(BaseInterruptHandler):
    def enter(self):
        for sig in self.sig_list:
            signal.signal(sig, signal.SIG_IGN)


class InterruptHandler(BaseInterruptHandler):
    def enter(self):
        def handler(signum, frame):  # pylint: disable=unused-argument
            raise InterruptedException("Execution was interrupted by signal")
        for sig in self.sig_list:
            signal.signal(sig, handler)


class InterruptedException(Exception):
    pass
