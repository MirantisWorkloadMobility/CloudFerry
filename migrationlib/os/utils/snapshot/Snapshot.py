import time

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

    def getStatus(self):
        return self.status

    def isAdd(self):
        return self.status == ADD

    def isChange(self):
        return self.status == CHANGE

    def isDelete(self):
        return self.status == DELETE


class Snapshot:
    def __init__(self):
        self.instances = {}
        self.images = {}
        self.volumes = {}
        self.tenants = {}
        self.users = {}
        self.security_groups = {}
        self.timestamp = time.time()

    def add(self, id, category, diff_obj):
        self.__dict__[category][id] = diff_obj

    def addInstance(self, id, diff_obj=None, **kwargs):
        self.instances[id] = kwargs if not diff_obj else diff_obj

    def addImage(self, id, diff_obj=None, **kwargs):
        self.images[id] = kwargs if not diff_obj else diff_obj

    def addVolume(self, id, diff_obj=None, **kwargs):
        print "volumes=", kwargs
        self.volumes[id] = kwargs if not diff_obj else diff_obj

    def addTenant(self, id, diff_obj=None, **kwargs):
        self.tenants[id] = kwargs if not diff_obj else diff_obj

    def addUser(self, id, diff_obj=None, **kwargs):
        self.users[id] = kwargs if not diff_obj else diff_obj

    def addSecurityGroup(self, id, diff_obj=None, **kwargs):
        self.security_groups[id] = kwargs if not diff_obj else diff_obj

    def union(self, snapshot, exclude=['timestamp']):
        snapshot_dict = self.excluding_fields(snapshot.convert_to_dict(), exclude)
        for item in snapshot_dict:
            self.__dict__[item].update(snapshot_dict[item])

    @staticmethod
    def excluding_fields(snapshot_dict, exclude):
        for item in exclude:
            if item in snapshot_dict:
                del snapshot_dict[item]
        return snapshot_dict

    def convert_to_dict(self):
        return {
            'instances': self.instances,
            'images': self.images,
            'volumes': self.volumes,
            'tenants': self.tenants,
            'users': self.users,
            'security_groups': self.security_groups,
            'timestamp': self.timestamp
        }