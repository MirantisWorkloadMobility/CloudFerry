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


import copy
import json
import re
from itertools import ifilter

from fabric.api import run
from fabric.api import settings

from glanceclient import client as glance_client
from glanceclient import exc as glance_exceptions
from glanceclient.v1.images import CREATE_PARAMS

from keystoneclient import exceptions as keystone_exceptions

from cloudferrylib.base import exception
from cloudferrylib.base import image
from cloudferrylib.utils import filters
from cloudferrylib.os.image import filters as glance_filters
from cloudferrylib.utils import file_like_proxy
from cloudferrylib.utils import utils as utl
from cloudferrylib.utils import remote_runner


LOG = utl.get_log(__name__)


class GlanceImage(image.Image):

    """
    The main class for working with Openstack Glance Image Service.

    """

    def __init__(self, config, cloud):
        self.config = config
        self.host = config.cloud.host
        self.cloud = cloud
        self.identity_client = cloud.resources['identity']
        self.filter_tenant_id = None
        self.filter_image = []
        # get mysql settings
        self.mysql_connector = cloud.mysql_connector('glance')
        self.runner = remote_runner.RemoteRunner(self.host,
                                                 self.config.cloud.ssh_user)
        self._image_filter = None
        super(GlanceImage, self).__init__(config)

    def get_image_filter(self):
        if self._image_filter is None:
            with open(self.config.migrate.filter_path, 'r') as f:
                filter_yaml = filters.FilterYaml(f)
                filter_yaml.read()

            self._image_filter = glance_filters.GlanceFilters(
                self.glance_client, filter_yaml)

        return self._image_filter

    @property
    def glance_client(self):
        return self.proxy(self.get_client(), self.config)

    def get_client(self):
        """ Getting glance client """
        endpoint_glance = self.identity_client.get_endpoint_by_service_type(
            service_type='image',
            endpoint_type='publicURL')

        # we can figure out what version of client to use from url
        # check if we have "v1" or "v2" in the end of url
        m = re.search(r"(.*)/v(\d)", endpoint_glance)
        if m:
            endpoint_glance = m.group(1)
            # for now we always use 1 version of client
            version = 1  # m.group(2)
        else:
            version = 1
        return glance_client.Client(
            version,
            endpoint=endpoint_glance,
            token=self.identity_client.get_auth_token_from_user())

    def required_tenants(self):
        image_owners = set()

        for i in self.get_image_list():
            image_owners.add(i.owner)

        return list(image_owners)

    def get_image_list(self):
        images = self.glance_client.images.list(filters={"is_public": None})

        filtering_enabled = self.cloud.position == 'src'

        if filtering_enabled:
            for f in self.get_image_filter().get_filters():
                images = ifilter(f, images)
            images = [i for i in images]

            LOG.info("Filtered images: %s",
                     ", ".join((str(i.name) for i in images)))

        return images

    def create_image(self, **kwargs):
        return self.glance_client.images.create(**kwargs)

    def delete_image(self, image_id):
        # Change protected property to false before delete
        self.glance_client.images.update(image_id, protected=False)
        self.glance_client.images.delete(image_id)

    def get_image_by_id(self, image_id):
        for glance_image in self.get_image_list():
            if glance_image.id == image_id:
                return glance_image

    def get_image_by_name(self, image_name):
        for glance_image in self.get_image_list():
            if glance_image.name == image_name:
                return glance_image

    def get_img_id_list_by_checksum(self, checksum):
        l = []
        for glance_image in self.get_image_list():
            if glance_image.checksum == checksum:
                l.append(glance_image.id)
        return l

    def get_image(self, im):
        """ Get image by id or name. """

        for glance_image in self.get_image_list():
            if im in (glance_image.name, glance_image.id):
                return glance_image

    def get_image_status(self, image_id):
        return self.get_image_by_id(image_id).status

    def get_ref_image(self, image_id):
        try:
            return self.glance_client.images.data(image_id)._resp
        except (glance_exceptions.HTTPInternalServerError,
                glance_exceptions.HTTPNotFound):
            raise exception.ImageDownloadError

    def get_image_checksum(self, image_id):
        return self.get_image_by_id(image_id).checksum

    def convert(self, glance_image, cloud):
        """Convert OpenStack Glance image object to CloudFerry object.

        :param glance_image:    Direct OS Glance image object to convert,
        :param cloud:           Cloud object.
        """

        resource = cloud.resources[utl.IMAGE_RESOURCE]
        keystone = cloud.resources["identity"]
        gl_image = {
            k: w for k, w in glance_image.to_dict().items(
            ) if k in CREATE_PARAMS}
        # we need to pass resource to destination to copy image
        gl_image.update({'resource': resource})

        # at this point we write name of owner of this tenant
        # to map it to different tenant id on destination
        gl_image.update(
            {'owner_name': keystone.try_get_tenant_name_by_id(
                glance_image.owner, default=cloud.cloud_config.cloud.tenant)})
        gl_image.update({
            "members": self.get_members({gl_image['id']: {'image': gl_image}})
        })

        if self.is_snapshot(glance_image):
            # for snapshots we need to keep only image_type
            # because other properties related to src cloud and cause
            # Can not find requested image (HTTP 400) error
            gl_image["properties"] = {'image_type': 'snapshot'}

        return gl_image

    def is_snapshot(self, img):
        # snapshots have {'image_type': 'snapshot"} in "properties" field
        return img.to_dict().get("properties", {}).get(
            'image_type') == 'snapshot'

    def get_tags(self):
        return {}

    def get_members(self, images):
        # members structure {image_id: {tenant_name: can_share}}
        result = {}
        for img in images:
            if images[img]['image']['is_public']:
                # public images cannot have members
                continue
            for entry in self.glance_client.image_members.list(image=img):
                if img not in result:
                    result[img] = {}

                tenant_name = self.identity_client.try_get_tenant_name_by_id(
                    entry.member_id, default=self.config.cloud.tenant)
                result[img][tenant_name] = entry.can_share
        return result

    def create_member(self, image_id, tenant_name, can_share):
        # change tenant_name to tenant_id
        tenant_id = self.identity_client.get_tenant_id_by_name(tenant_name)
        self.glance_client.image_members.create(
            image_id,
            tenant_id,
            can_share)

    def _convert_images_with_metadata(self, image_list_metadata):
        info = {'images': {}}
        for (im, meta) in image_list_metadata:
            glance_image = self.get_image(im)
            if glance_image:
                info = self.make_image_info(glance_image, info)
                info['images'][glance_image.id]['meta'] = meta
        return info

    def read_info(self, **kwargs):
        """Get info about images or specified image.

        :returns: Dictionary containing images data
        """

        info = {'images': {}}

        for glance_image in self.get_image_list():
            info = self.make_image_info(glance_image, info)

        info.update({
            "tags": self.get_tags(),
            "members": self.get_members(info['images'])
        })

        LOG.info("Read images: %s",
                 ", ".join(("{name} ({uuid})".format(name=i['image']['name'],
                                                     uuid=i['image']['id'])
                            for i in info['images'].itervalues())))

        return info

    def get_image_by_id_converted(self, image_id):
        info = {'images': {}}
        i = self.get_image_by_id(image_id)
        return self.make_image_info(i, info)

    def make_image_info(self, glance_image, info):
        if glance_image:
            if glance_image.status == "active":
                LOG.debug("Image '%s' status is active.", glance_image.name)
                gl_image = self.convert(glance_image, self.cloud)

                command = ("SELECT value FROM image_locations "
                           "WHERE image_id=\"{}\" AND deleted=\"0\";"
                           .format(glance_image.id))
                res = self.mysql_connector.execute(command)
                img_loc = None
                for row in res:
                    if img_loc is not None:
                        LOG.warning("ignoring multi locations for image {}"
                                    .format(glance_image.name))
                        break
                    img_loc = row[0]

                info['images'][glance_image.id] = {
                    'image': gl_image,
                    'meta': {
                        'img_loc': img_loc
                    },
                }
                LOG.debug("find image with ID {}({})"
                          .format(glance_image.id, glance_image.name))
            else:
                LOG.warning("image {img} was not migrated according to "
                            "status = {status}, (expected status "
                            "= active)".format(
                                img=glance_image.id,
                                status=glance_image.status))
        else:
            LOG.error('Image has not been found')

        return info

    def deploy(self, info):
        LOG.info("Glance images deployment started...")
        info = copy.deepcopy(info)
        new_info = {'images': {}}
        created_images = []
        delete_container_format, delete_disk_format = [], []
        empty_image_list = {}
        keystone = self.cloud.resources["identity"]

        # List for obsolete/broken images IDs, that will not be migrated
        obsolete_images_ids_list = []
        dst_images = {}
        for dst_image in self.get_image_list():
            tenant_name = keystone.try_get_tenant_name_by_id(
                dst_image.owner, default=self.cloud.cloud_config.cloud.tenant)
            image_key = (dst_image.name, tenant_name, dst_image.checksum,
                         dst_image.is_public)
            dst_images[image_key] = dst_image

        for image_id_src, gl_image in info['images'].iteritems():
            img = gl_image['image']
            if img and img['resource']:
                checksum_current = img['checksum']
                name_current = img['name']
                tenant_name = img['owner_name']
                meta = gl_image['meta']
                image_key = (name_current, tenant_name, checksum_current,
                             img['is_public'])

                if image_key in dst_images:
                    existing_image = dst_images[image_key]
                    created_images.append((existing_image, meta))
                    image_members = img['members'].get(img['id'], {})
                    self.update_membership(existing_image.id, image_members)
                    LOG.info("Image '%s' is already present on destination, "
                             "skipping", img['name'])
                    continue

                LOG.debug("Updating owner '%s' of image '%s'",
                          tenant_name, img["name"])
                img["owner"] = \
                    self.identity_client.get_tenant_id_by_name(tenant_name)

                if img["properties"]:
                    # update snapshot metadata
                    metadata = img["properties"]
                    if "owner_id" in metadata:
                        # update tenant id
                        LOG.debug("updating snapshot metadata for field "
                                  "'owner_id' for image {image}".format(
                                      image=img["id"]))
                        metadata["owner_id"] = img["owner"]
                    if "user_name" in metadata:
                        # update user id by specified name
                        LOG.debug("updating snapshot metadata for field "
                                  "'user_id' for image {image}".format(
                                      image=img["id"]))
                        try:
                            ks_client = self.identity_client.keystone_client
                            metadata["user_id"] = ks_client.users.find(
                                username=metadata["user_name"]).id
                            del metadata["user_name"]
                        except keystone_exceptions.NotFound:
                            LOG.warning("Cannot update user name for image "
                                        "{}".format(img['name']))
                if img["checksum"] is None:
                    LOG.warning("re-creating image {} "
                                "from original source URL"
                                .format(img["id"]))
                    if meta['img_loc'] is not None:
                        self.glance_img_create(
                            img['name'],
                            img['disk_format'] or "qcow2",
                            meta['img_loc']
                        )
                        recreated_image = utl.ext_dict(
                            name=img["name"]
                        )
                        created_images.append(
                            (recreated_image, gl_image['meta'])
                        )
                    else:
                        raise exception.AbortMigrationError(
                            "image information has no original source URL")
                    continue

                LOG.debug("Creating image '{image}' ({image_id})".format(
                    image=img["name"],
                    image_id=img['id']))
                # we can face situation when image has no
                # disk_format and container_format properties
                # this situation appears, when image was created
                # with option --copy-from
                # glance-client cannot create image without this
                # properties, we need to create them artificially
                # and then - delete from database

                try:
                    data_proxy = file_like_proxy.FileLikeProxy(
                        img, self.config['migrate']['speed_limit'])

                    created_image = self.create_image(
                        name=img['name'],
                        container_format=(img['container_format'] or "bare"),
                        disk_format=(img['disk_format'] or "qcow2"),
                        is_public=img['is_public'],
                        protected=img['protected'],
                        owner=img['owner'],
                        size=img['size'],
                        properties=img['properties'],
                        data=data_proxy)

                    image_members = img['members'].get(img['id'], {})
                    LOG.debug("new image ID {}".format(created_image.id))
                    self.update_membership(created_image.id, image_members)
                    created_images.append((created_image, meta))
                except exception.ImageDownloadError:
                    LOG.warning("Unable to reach image's data due to "
                                "Glance HTTPInternalServerError. Skipping "
                                "image: (id = %s)", img["id"])
                    obsolete_images_ids_list.append(img["id"])
                    continue

                if not img["container_format"]:
                    delete_container_format.append(created_image.id)
                if not img["disk_format"]:
                    delete_disk_format.append(created_image.id)
            elif img['resource'] is None:
                recreated_image = utl.ext_dict(name=img["name"])
                created_images.append((recreated_image, gl_image['meta']))
            elif not img:
                empty_image_list[image_id_src] = gl_image

        # Remove obsolete/broken images from info
        for img_id in obsolete_images_ids_list:
            info['images'].pop(img_id)

        if created_images:
            im_name_list = [(im.name, tmp_meta) for (im, tmp_meta) in
                            created_images]
            LOG.debug("images on destination: {}".format(
                [im for (im, tmp_meta) in im_name_list]))
            new_info = self._convert_images_with_metadata(im_name_list)
        new_info['images'].update(empty_image_list)
        self.delete_fields('disk_format', delete_disk_format)
        self.delete_fields('container_format', delete_container_format)
        LOG.info("Glance images deployment finished.")
        return new_info

    def update_membership(self, image_id, image_members):
        client = self.glance_client
        existing_members = {m.member_id: m
                            for m in client.image_members.list(image=image_id)}
        for tenant_name, can_share in image_members.iteritems():
            tenant_id = self.identity_client.get_tenant_id_by_name(tenant_name)
            LOG.debug("Deploying image member for image '%s' "
                      "tenant '%s'", image_id, tenant_name)
            if (tenant_id in existing_members and
                    existing_members[tenant_id].can_share != can_share):
                client.image_members.delete(image_id, tenant_id)
                client.image_members.create(image_id, tenant_id, can_share)
            if tenant_id not in existing_members:
                client.image_members.create(image_id, tenant_id, can_share)

    def delete_fields(self, field, list_of_ids):
        if not list_of_ids:
            return
        # this command sets disk_format, container_format to NULL
        command = ("UPDATE images SET {field}=NULL"
                   " where id in ({id_list})".format(
                       field=field,
                       id_list=",".join(
                           [" '{0}' ".format(i) for i in list_of_ids])))
        self.mysql_connector.execute(command)

    def get_status(self, res_id):
        return self.glance_client.images.get(res_id).status

    def patch_image(self, backend_storage, image_id):
        ssh_attempts = self.cloud.cloud_config.migrate.ssh_connection_attempts

        if backend_storage == 'ceph':
            image_from_glance = self.get_image_by_id(image_id)
            with settings(host_string=self.cloud.getIpSsh(),
                          connection_attempts=ssh_attempts):
                out = json.loads(
                    run("rbd -p images info %s --format json" % image_id))
                image_from_glance.update(size=out["size"])

    def glance_img_create(self, img_name, img_format, file_path):
        cfg = self.cloud.cloud_config.cloud
        cmd = image.glance_image_create_cmd(cfg, img_name, img_format,
                                            file_path)
        out = self.runner.run(cmd)
        image_id = out.split("|")[2].replace(' ', '')
        return image_id
