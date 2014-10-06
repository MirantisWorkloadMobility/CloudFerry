from cloudferrylib.base.action import Transporter


class IdentityTransporter(Transporter.Transporter):

    def __init__(self):
        super(IdentityTransporter, self).__init__()

    def run(self, src_cloud, dst_cloud):
        src_resource = src_cloud.resources['identity']
        dst_resource = dst_cloud.resources['identity']
        info = src_resource.read_info()
        dst_resource.deploy(info)

