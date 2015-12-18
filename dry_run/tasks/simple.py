from cloudferrylib.scheduler import task
from cloudferrylib.utils import log


LOG = log.getLogger(__name__)


class AddNumbers(task.Task):

    def __init__(self, a, b):
        super(task.Task, self).__init__()
        self.a = a
        self.b = b

    def run(self, *args, **kwargs):
        LOG.debug("adding '%d' to '%d'", self.a, self.b)
        return {'res1': self.a + self.b}


class DivideNumbers(task.Task):

    def __init__(self, a, b):
        super(task.Task, self).__init__()
        self.a = a
        self.b = b

    def run(self, *args, **kwargs):
        LOG.debug("dividing '%d' by '%d'", self.a, self.b)
        return {'res2': self.a / self.b}


class MultiplyNumbers(task.Task):

    def __init__(self, a, b):
        super(task.Task, self).__init__()
        self.a = a
        self.b = b

    def run(self, *args, **kwargs):
        LOG.debug("multiplying '%d' by '%d'", self.a, self.b)
        return {'res2': self.a * self.b}


class DivisionByZero(task.Task):

    def run(self, *args, **kwargs):
        LOG.debug("dividing by zero (special case to fail execution)")
        1 / 0
        return{}
