
from cloudferrylib.base.action import action
from fabric.api import run, settings


class ConvertFileToImage(action.Action):

    def run(self, cfg=None, file_path=None, image_format=None, image_name=None):
        with settings(host_string=cfg['host']):
            out = run(("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                       "--os-auth-url=http://%s:35357/v2.0 " +
                       "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                       "grep id") %
                      (cfg['user'],
                       cfg['password'],
                       cfg['tenant'],
                       cfg['host'],
                       image_name,
                       image_format,
                       file_path))
            id = out.split("|")[2].replace(' ', '')
            return id
