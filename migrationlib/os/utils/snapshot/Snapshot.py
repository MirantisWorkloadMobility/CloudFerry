__author__ = 'mirrorcoder'

ADD = "add"
CHANGE = "change"
DELETE = "delete"


class DiffValue:
    def __init__(self, was, curr):
        self.was = was
        self.curr = curr


class DiffObject:
    def __init__(self, status, value):
        self.status = status
        self.value = value


class Snapshot:
    def __init__(self):
        self.instances = {}
        self.images = {}
        self.volumes = {}
        self.tenants = {}
        self.users = {}
        self.security_groups = {}

    def addInstance(self, id, **kwargs):
        self.instances[id] = kwargs

    def addImage(self, id, **kwargs):
        self.images[id] = kwargs

    def addVolume(self, id, **kwargs):
        self.volumes[id] = kwargs

    def addTenant(self, id, **kwargs):
        self.tenants[id] = kwargs

    def addUser(self, id, **kwargs):
        self.users[id] = kwargs

    def addSecurityGroup(self, id, **kwargs):
        self.security_groups[id] = kwargs

    def convert_to_dict(self):
        return {
            'instances': self.instances,
            'images': self.images,
            'volumes': self.volumes,
            'tenants': self.tenants,
            'users': self.users,
            'security_groups': self.security_groups
        }