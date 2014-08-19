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

    def add(self, id, category, diff_obj):
        self.__dict__[category][id] = diff_obj

    def addInstance(self, id, diff_obj=None, **kwargs):
        self.instances[id] = kwargs if not diff_obj else diff_obj

    def addImage(self, id, diff_obj=None, **kwargs):
        self.images[id] = kwargs if not diff_obj else diff_obj

    def addVolume(self, id, diff_obj=None, **kwargs):
        print kwargs
        self.volumes[id] = kwargs if not diff_obj else diff_obj

    def addTenant(self, id, diff_obj=None, **kwargs):
        self.tenants[id] = kwargs if not diff_obj else diff_obj

    def addUser(self, id, diff_obj=None, **kwargs):
        self.users[id] = kwargs if not diff_obj else diff_obj

    def addSecurityGroup(self, id, diff_obj=None, **kwargs):
        self.security_groups[id] = kwargs if not diff_obj else diff_obj

    def convert_to_dict(self):
        return {
            'instances': self.instances,
            'images': self.images,
            'volumes': self.volumes,
            'tenants': self.tenants,
            'users': self.users,
            'security_groups': self.security_groups
        }