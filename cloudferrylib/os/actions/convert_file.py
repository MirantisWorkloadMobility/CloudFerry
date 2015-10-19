from fabric.api import run, settings, env
from cloudferrylib.base.action import action
from cloudferrylib.utils.utils import forward_agent
from cloudferrylib.utils import utils as utl

INSTANCES = 'instances'


class ConvertFile(action.Action):
    def run(self, info=None, **kwargs):
        cfg = self.cloud.cloud_config.cloud
        image_res = self.cloud.resources[utl.IMAGE_RESOURCE]
        if image_res.config.image.convert_to_raw:
            return {}
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            image_id = \
                info[INSTANCES][instance_id][utl.INSTANCE_BODY]['image_id']
            images = image_res.get_image_by_id_converted(image_id=image_id)
            image = images[utl.IMAGES_TYPE][image_id]
            disk_format = image[utl.IMAGE_BODY]['disk_format']
            base_file = "%s/%s" % (cfg.temp, "temp%s_base" % instance_id)
            if disk_format.lower() != utl.RAW:
                self.convert_file_to_raw(cfg.ssh_host, disk_format, base_file)
        return {}

    @staticmethod
    def convert_file_to_raw(host, disk_format, filepath):
        with settings(host_string=host,
                      connection_attempts=env.connection_attempts):
            with forward_agent(env.key_filename):
                run("qemu-img convert -f %s -O raw %s %s.tmp" %
                    (disk_format, filepath, filepath))
                run("mv -f %s.tmp %s" % (filepath, filepath))
