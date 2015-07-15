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
import datetime
import json
import re
import time

from fabric.api import run
from fabric.api import settings

from glanceclient import client as glance_client
from glanceclient import exc
from glanceclient.v1.images import CREATE_PARAMS

from cloudferrylib.base import exception
from cloudferrylib.base import image
from cloudferrylib.utils import mysql_connector
from cloudferrylib.utils import file_like_proxy
from cloudferrylib.utils import utils as utl


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
        self.mysql_connector = self.get_db_connection()
        super(GlanceImage, self).__init__(config)

    @property
    def glance_client(self):
        return self.proxy(self.get_client(), self.config)

    def get_db_connection(self):
        if not hasattr(
                self.cloud.config,
                self.cloud.position + '_image'):
            LOG.debug('running on default mysql settings')
            return mysql_connector.MysqlConnector(
                self.config.mysql, 'glance')
        else:
            LOG.debug('running on custom mysql settings')
            my_settings = getattr(
                self.cloud.config,
                self.cloud.position + '_image')
            return mysql_connector.MysqlConnector(
                my_settings, my_settings.database_name)

    def get_client(self):
        """ Getting glance client """

        endpoint_glance = self.identity_client.get_endpoint_by_service_type(
            service_type='image',
            endpoint_type='publicURL')

        # we can figure out what version of client to use from url
        # check if we have "v1" or "v2" in the end of url
        m = re.search("(.*)/v(\d)", endpoint_glance)
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

    def get_image_list(self):
        # let's get all public images and all tenant's images
        get_img_list = self.glance_client.images.list
        if self.cloud.position == 'src' and self.filter_tenant_id:
            image_list = []
            # getting images if tenant is owner
            filters = {'is_public': None, 'owner': self.filter_tenant_id}
            for img in get_img_list(filters=filters):
                LOG.debug("append tenant's image ID {}".format(img.id))
                image_list.append(img)
            filters = {'is_public': None}
            img_list = get_img_list(filters=filters)
            # getting images if tenant is member
            for img in self.glance_client.image_members.list(member=self.filter_tenant_id):
                for i in img_list:
                    if i.id == img.image_id:
                        LOG.debug("append image(by member) ID {}".format(i.id))
                        image_list.append(i)
            # getting public images
            for img in get_img_list(filters=filters):
                if img.is_public or (img.id in self.filter_image):
                    LOG.debug("append public image ID {}".format(img.id))
                    image_list.append(img)
            return list(set(image_list))
        # by some reason - guys from community decided to create that strange
        # option to get images of all tenants
        filters = {"is_public": None}
        return get_img_list(filters=filters)

    def create_image(self, **kwargs):
        return self.glance_client.images.create(**kwargs)

    def delete_image(self, image_id):
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
        except exc.HTTPInternalServerError:
            raise exception.ImageDownloadError

    def get_image_checksum(self, image_id):
        return self.get_image_by_id(image_id).checksum

    @staticmethod
    def convert(glance_image, cloud):
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

        if resource.is_snapshot(glance_image):
            # for snapshots we need to write snapshot username to namespace
            # to map it later to new user id
            user_id = gl_image["properties"].get("user_id")
            usr = keystone.try_get_user_by_id(user_id=user_id)
            if usr:
                gl_image["properties"]["user_name"] = usr.name
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
            for entry in self.glance_client.image_members.list(image=img):
                if img not in result:
                    result[img] = {}

                # change tenant_id to tenant_name
                tenant_name = self.identity_client.try_get_tenant_name_by_id(
                    entry.member_id,
                    default=self.config.cloud.tenant)

                result[img][tenant_name] = entry.can_share
        return result

    def create_member(self, image_id, tenant_name, can_share):
        # change tenant_name to tenant_id
        tenant_id = self.identity_client.get_tenant_id_by_name(tenant_name)
        self.glance_client.image_members.create(
            image_id,
            tenant_id,
            can_share)

    def read_info(self, **kwargs):
        """Get info about images or specified image.

        :param image_id: Id of specified image
        :param image_name: Name of specified image
        :param images_list: List of specified images
        :param images_list_meta: Tuple of specified images with metadata in
                                 format [(image, meta)]
        :param date: date object. snapshots updated after this date will be
                     dropped
        :rtype: Dictionary with all necessary images info
        """

        info = {'images': {}}

        if kwargs.get('tenant_id'):
            self.filter_tenant_id = kwargs['tenant_id'][0]

        def image_valid(img, date):
            """ Check if image was updated recently """
            updated = datetime.datetime.strptime(
                img.updated_at,
                "%Y-%m-%dT%H:%M:%S")
            return date <= updated.date()

        if kwargs.get('date'):
            for img in self.get_image_list():
                if (not self.is_snapshot(img)) or image_valid(
                        img, kwargs.get('date')):
                    self.make_image_info(img, info)

        if kwargs.get('image_id'):
            self.filter_image = kwargs['image_id']
            glance_image = self.get_image_by_id(self.filter_image)
            info = self.make_image_info(glance_image, info)

        elif kwargs.get('image_name'):
            glance_image = self.get_image_by_name(kwargs['image_name'])
            info = self.make_image_info(glance_image, info)

        elif kwargs.get('images_list'):
            self.filter_image = kwargs['images_list']
            for im in self.filter_image:
                glance_image = self.get_image(im)
                info = self.make_image_info(glance_image, info)

        elif kwargs.get('images_list_meta'):
            for (im, meta) in kwargs['images_list_meta']:
                glance_image = self.get_image(im)
                info = self.make_image_info(glance_image, info)
                info['images'][glance_image.id]['meta'] = meta

        else:
            for glance_image in self.get_image_list():
                info = self.make_image_info(glance_image, info)

        info.update({
            "tags": self.get_tags(),
            "members": self.get_members(info['images'])
        })

        return info

    def make_image_info(self, glance_image, info):
        if glance_image:
            if glance_image.status == "active":
                gl_image = self.convert(glance_image, self.cloud)

                info['images'][glance_image.id] = {'image': gl_image,
                                                   'meta': {},
                                                   }
            else:
                LOG.warning("image {img} was not migrated according to "
                            "status = {status}, (expected status "
                            "= active)".format(
                                img=glance_image.id,
                                status=glance_image.status))
        else:
            LOG.error('Image has not been found')

        return info

    def deploy(self, info, callback=None):
        info = copy.deepcopy(info)
        new_info = {'images': {}}
        migrate_images_list = []
        delete_container_format, delete_disk_format = [], []
        empty_image_list = {}

        # List for obsolete/broken images IDs, that will not be migrated
        obsolete_images_ids_list = []

        for image_id_src, gl_image in info['images'].iteritems():
            if gl_image['image']:
                dst_img_checksums = {x.checksum: x for x in
                                     self.get_image_list()}
                dst_img_names = [x.name for x in self.get_image_list()]
                checksum_current = gl_image['image']['checksum']
                name_current = gl_image['image']['name']
                meta = gl_image['meta']
                if checksum_current in dst_img_checksums and (
                        name_current) in dst_img_names:
                    migrate_images_list.append(
                        (dst_img_checksums[checksum_current], meta))
                    continue

                LOG.debug("updating owner of image {image}".format(
                    image=gl_image["image"]["owner"]))
                gl_image["image"]["owner"] = \
                    self.identity_client.get_tenant_id_by_name(
                    gl_image["image"]["owner_name"])
                del gl_image["image"]["owner_name"]

                if gl_image["image"]["properties"]:
                    # update snapshot metadata
                    metadata = gl_image["image"]["properties"]
                    if "owner_id" in metadata:
                        # update tenant id
                        LOG.debug("updating snapshot metadata for field "
                                  "'owner_id' for image {image}".format(
                                      image=gl_image["image"]["id"]))
                        metadata["owner_id"] = gl_image["image"]["owner"]
                    if "user_id" in metadata:
                        # update user id by specified name
                        LOG.debug("updating snapshot metadata for field "
                                  "'user_id' for image {image}".format(
                                      image=gl_image["image"]["id"]))
                        metadata["user_id"] = \
                            self.identity_client.keystone_client.users.find(
                                username=metadata["user_name"]).id
                        del metadata["user_name"]

                LOG.debug("migrating image {image}".format(
                    image=gl_image["image"]["id"]))
                # we can face situation when image has no
                # disk_format and container_format properties
                # this situation appears, when image was created
                # with option --copy-from
                # glance-client cannot create image without this
                # properties, we need to create them artificially
                # and then - delete from database

                try:
                    migrate_image = self.create_image(
                        name=gl_image['image']['name'],
                        container_format=(gl_image['image']['container_format']
                                          or "bare"),
                        disk_format=gl_image['image']['disk_format'] or "qcow2",
                        is_public=gl_image['image']['is_public'],
                        protected=gl_image['image']['protected'],
                        owner=gl_image['image']['owner'],
                        size=gl_image['image']['size'],
                        properties=gl_image['image']['properties'],
                        data=file_like_proxy.FileLikeProxy(
                            gl_image['image'],
                            callback,
                            self.config['migrate']['speed_limit']))
                except exception.ImageDownloadError:
                    LOG.warning("Unable to reach image's data due to "
                                "Glance HTTPInternalServerError. Skipping "
                                "image: (id = %s)", gl_image["image"]["id"])
                    obsolete_images_ids_list.append(gl_image["image"]["id"])
                    continue

                migrate_images_list.append((migrate_image, meta))
                if not gl_image["image"]["container_format"]:
                    delete_container_format.append(migrate_image.id)
                if not gl_image["image"]["disk_format"]:
                    delete_disk_format.append(migrate_image.id)
            else:
                empty_image_list[image_id_src] = gl_image

        # Remove obsolete/broken images from info
        [info['images'].pop(img_id) for img_id in obsolete_images_ids_list]

        if migrate_images_list:
            im_name_list = [(im.name, tmp_meta) for (im, tmp_meta) in
                            migrate_images_list]
            new_info = self.read_info(images_list_meta=im_name_list)
        new_info['images'].update(empty_image_list)
        # on this step we need to create map between source ids and dst ones
        LOG.debug("creating map between source and destination image ids")
        image_ids_map = {}
        dst_img_checksums = {x.checksum: x.id for x in self.get_image_list()}
        for image_id_src, gl_image in info['images'].iteritems():
            cur_image = gl_image["image"]
            image_ids_map[cur_image["id"]] = \
                dst_img_checksums[cur_image["checksum"]]
        LOG.debug("deploying image members")
        for image_id, data in info.get("members", {}).items():
            for tenant_name, can_share in data.items():
                LOG.debug("deploying image member for image {image}"
                          " tenant {tenant}".format(
                              image=image_id,
                              tenant=tenant_name))
                self.create_member(
                    image_ids_map[image_id],
                    tenant_name,
                    can_share)
        self.delete_fields('disk_format', delete_disk_format)
        self.delete_fields('container_format', delete_container_format)
        return new_info

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

    def wait_for_status(self, id_res, status):
        while self.glance_client.images.get(id_res).status != status:
            time.sleep(1)

    def patch_image(self, backend_storage, image_id):
        if backend_storage == 'ceph':
            image_from_glance = self.get_image_by_id(image_id)
            with settings(host_string=self.cloud.getIpSsh()):
                out = json.loads(
                    run("rbd -p images info %s --format json" % image_id))
                image_from_glance.update(size=out["size"])
