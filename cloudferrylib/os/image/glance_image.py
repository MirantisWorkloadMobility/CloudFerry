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
import httplib
from itertools import ifilter
import json
import re

from fabric.api import run
from fabric.api import settings
from glanceclient import client as glance_client
from glanceclient import exc as glance_exceptions
from glanceclient.v1.images import CREATE_PARAMS
from keystoneclient import exceptions as keystone_exceptions
from OpenSSL import SSL as ssl

from cloudferrylib.base import exception
from cloudferrylib.base import image
from cloudferrylib.os.image import filters as glance_filters
from cloudferrylib.utils import file_proxy
from cloudferrylib.utils import filters
from cloudferrylib.utils import log
from cloudferrylib.utils import proxy_client
from cloudferrylib.utils import retrying
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import sizeof_format
from cloudferrylib.utils import utils as utl

LOG = log.getLogger(__name__)


class GlanceImageProgessMigrationView(object):

    """ View to show the progress of image migration. """

    def __init__(self, images, dst_images):
        self.num_public, self.num_private, self.num_migrated = 0, 0, 0
        self.list_public, self.list_private, self.list_migrated = [], [], []
        self.total_size, self.migrated_size = 0, 0
        for image_id in images:
            img = images[image_id]['image']

            if not img:
                continue
            elif img['resource']:
                image_key = (img['name'], img['owner_name'], img['checksum'],
                             img['is_public'])
                dst_image = dst_images.get(image_key)
                if dst_image:
                    self.num_migrated += 1
                    self.migrated_size += dst_image.size or 0
                    self.list_migrated.append('%s (%s)' % (dst_image.name,
                                                           dst_image.id))
                    continue

            self.total_size += img.get('size', 0)

            if img.get('is_public'):
                self.num_public += 1
                self.list_public.append('%s (%s)' % (img['name'], img['id']))
            else:
                self.num_private += 1
                self.list_private.append('%s (%s)' % (img['name'], img['id']))
        self.cnt = 0
        self.progress = 0

    def show_info(self):
        LOG.info('Total number of images to be migrated: %d, '
                 'total size: %s\n'
                 'Number of private images: %d\n'
                 'Number of public images: %d\n'
                 'Number of already migrated images: %d, total size: %s',
                 self.num_private + self.num_public,
                 sizeof_format.sizeof_fmt(self.total_size), self.num_private,
                 self.num_public, self.num_migrated,
                 sizeof_format.sizeof_fmt(self.migrated_size))
        LOG.info('List of private images:\n%s', '\n'.join(self.list_private))
        LOG.info('List of public images:\n%s', '\n'.join(self.list_public))
        LOG.info('List of migrated images:\n%s', '\n'.join(self.list_migrated))

    def inc_progress(self, size):
        self.cnt += 1
        self.progress += size

    def show_progress(self, ):
        size_percentage = (self.progress * 100 / self.total_size
                           if self.total_size else 100)
        LOG.info('%(num_migrated)d of %(num_total_images)d images '
                 'migrated (%(size_percentage)d%% of %(size_total)s '
                 'total)',
                 {'num_migrated': self.cnt,
                  'num_total_images': self.num_private + self.num_public,
                  'size_percentage': size_percentage,
                  'size_total': sizeof_format.sizeof_fmt(self.total_size)})


class GlanceImage(image.Image):

    """ The main class for working with Openstack Glance Image Service. """

    def __init__(self, config, cloud):
        self.config = config
        self.ssh_host = config.cloud.ssh_host
        self.cloud = cloud
        self.identity_client = cloud.resources['identity']
        self.filter_tenant_id = None
        self.filter_image = []
        # get mysql settings
        self.mysql_connector = cloud.mysql_connector('glance')
        self.runner = remote_runner.RemoteRunner(self.ssh_host,
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
        """ Getting glance client. """
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
            token=self.identity_client.get_auth_token_from_user(),
            insecure=self.config.cloud.insecure
        )

    def required_tenants(self, filter_tenant_id=None):
        old_filter_tenant_id = self.filter_tenant_id
        self.filter_tenant_id = filter_tenant_id

        tenants = set()

        for i in self.get_image_list():
            tenants.add(i.owner)
            for entry in self.glance_client.image_members.list(image=i.id):
                name = self.identity_client.try_get_tenant_name_by_id(
                    entry.member_id, default=self.config.cloud.tenant)
                tenant_id = self.identity_client.get_tenant_id_by_name(name)
                tenants.add(tenant_id)

        self.filter_tenant_id = old_filter_tenant_id

        return list(tenants)

    def get_image_raw(self, image_id):
        return self.glance_client.images.get(image_id)

    def image_exists(self, image_id):
        with proxy_client.expect_exception(glance_exceptions.HTTPNotFound):
            try:
                self.get_image_raw(image_id)
                return True
            except glance_exceptions.HTTPNotFound:
                return False

    def get_image_list(self):
        images = self.glance_client.images.list(filters={"is_public": None})

        if self.cloud.position == 'src':
            for f in self.get_image_filter().get_filters():
                images = ifilter(f, images)
            images = [i for i in images]
            LOG.info("Filtered images: %s",
                     ", ".join(('%s (%s)' % (i.name, i.id) for i in images)))

        return images

    def get_matching_image(self, uuid, name, size, checksum):
        for img in self.get_image_list():
            image_matches = (
                img.id == uuid or
                img.name == name and
                img.size == size and
                img.checksum == checksum)
            if image_matches:
                return img

    def create_image(self, **kwargs):
        image_id = kwargs.get('id')
        if image_id is not None and self.image_exists(image_id):
            LOG.warning("Image ID will not be kept for source image "
                        "'%(name)s' (%(id)s), image ID is already present "
                        "in destination (perhaps was deleted previously).",
                        {'name': kwargs.get('name'), 'id': image_id})
            del kwargs['id']
        return self.glance_client.images.create(**kwargs)

    def delete_image(self, image_id):
        # Change protected property to false before delete
        self.glance_client.images.update(image_id, protected=False)
        self.glance_client.images.delete(image_id)

    def get_image_by_id(self, image_id):
        try:
            return self.glance_client.images.get(image_id)
        except glance_exceptions.NotFound:
            LOG.warning('Image %s not found on %s', image_id,
                        self.cloud.position)
            return None

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

    @staticmethod
    def get_resp(data):
        """Get _resp property.

        :return: _resp

        """
        return getattr(data, '_resp')

    def get_ref_image(self, image_id):
        try:
            # ssl.ZeroReturnError happens because a size of an image is zero
            with proxy_client.expect_exception(
                glance_exceptions.NotFound,
                glance_exceptions.HTTPInternalServerError,
                ssl.ZeroReturnError
            ):
                return self.get_resp(self.glance_client.images.data(image_id))
        except (glance_exceptions.HTTPInternalServerError,
                glance_exceptions.HTTPNotFound,
                ssl.ZeroReturnError):
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
        image_dict = glance_image.to_dict()
        gl_image = {k: image_dict.get(k) for k in CREATE_PARAMS}
        # we need to pass resource to destination to copy image
        gl_image['resource'] = resource

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

    @staticmethod
    def is_snapshot(img):
        # snapshots have {'image_type': 'snapshot"} in "properties" field
        return img.to_dict().get("properties", {}).get(
            'image_type') == 'snapshot'

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

    def read_info(self, **_):
        """Get info about images or specified image.

        :returns: Dictionary containing images data

        """

        info = {'images': {}}

        for glance_image in self.get_image_list():
            info = self.make_image_info(glance_image, info)

        info.update({
            "tags": {},
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
                        LOG.warning("Ignoring multi locations for image %s",
                                    glance_image.name)
                        break
                    img_loc = row[0]

                info['images'][glance_image.id] = {
                    'image': gl_image,
                    'meta': {
                        'img_loc': img_loc
                    },
                }
                LOG.debug("Find image with ID %s(%s)",
                          glance_image.id, glance_image.name)
            else:
                LOG.warning("Image %s was not migrated according to "
                            "status = %s, (expected status = active)",
                            glance_image.id, glance_image.status)
        else:
            LOG.error('Image has not been found')

        return info

    def _dst_images(self):
        dst_images = {}
        keystone = self.cloud.resources["identity"]
        LOG.info("Retrieving list of images from destination to make sure "
                 "images are not migrated twice. May take awhile, please be "
                 "patient.")
        for dst_image in self.get_image_list():
            LOG.debug("Working on destination image '%s (%s)'",
                      dst_image.name, dst_image.id)
            retryer = retrying.Retry(
                max_attempts=self.config.migrate.retry,
                reraise_original_exception=True)
            try:
                # Destination cloud sporadically fails with Unauthorized for
                # random images, thus this logic; see CF-385
                tenant_name = retryer.run(
                    keystone.try_get_tenant_name_by_id,
                    dst_image.owner,
                    default=self.cloud.cloud_config.cloud.tenant)
                image_key = (dst_image.name, tenant_name, dst_image.checksum,
                             dst_image.is_public)
                dst_images[image_key] = dst_image
            except keystone_exceptions.Unauthorized:
                LOG.warning("Authorization failed in destination keystone, "
                            "image '%s (%s)' may be migrated twice later!")
        return dst_images

    def identical(self, src_image, dst_image):
        """Compare images."""
        for field in ('name', 'checksum', 'is_public'):
            if src_image.get(field, None) != dst_image.get(field, None):
                return False
        migrated = self.cloud.migration[utl.IDENTITY_RESOURCE]
        return migrated.identical(src_image['owner'], dst_image['owner'],
                                  resource_type=utl.TENANTS_TYPE)

    def deploy(self, info, *args, **kwargs):
        LOG.info("Glance images deployment started...")
        info = copy.deepcopy(info)
        created_images = []
        delete_container_format, delete_disk_format = [], []
        empty_image_list = {}

        # List for obsolete/broken images IDs, that will not be migrated
        obsolete_images_ids_list = []
        dst_images = self._dst_images()

        view = GlanceImageProgessMigrationView(info['images'], dst_images)
        view.show_info()
        for image_id_src in info['images']:
            img = info['images'][image_id_src]['image']
            meta = info['images'][image_id_src]['meta']
            if img and img['resource']:
                checksum_current = img['checksum']
                name_current = img['name']
                tenant_name = img['owner_name']
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

                view.show_progress()
                view.inc_progress(img['size'])

                LOG.debug("Updating owner '%s' of image '%s'",
                          tenant_name, img["name"])
                img["owner"] = \
                    self.identity_client.get_tenant_id_by_name(tenant_name)

                if img["properties"]:
                    # update snapshot metadata
                    metadata = img["properties"]
                    if "owner_id" in metadata:
                        # update tenant id
                        LOG.debug("Updating snapshot metadata for field "
                                  "'owner_id' for image %s", img["id"])
                        metadata["owner_id"] = img["owner"]
                    if "user_name" in metadata:
                        # update user id by specified name
                        LOG.debug("Updating snapshot metadata for field "
                                  "'user_id' for image %s", img["id"])
                        try:
                            ks_client = self.identity_client.keystone_client
                            metadata["user_id"] = ks_client.users.find(
                                username=metadata["user_name"]).id
                            del metadata["user_name"]
                        except keystone_exceptions.NotFound:
                            LOG.warning("Cannot update user name for image %s",
                                        img['name'])
                if img["checksum"] is None:
                    LOG.warning("re-creating image %s from original source "
                                "URL", img["id"])
                    if meta['img_loc'] is not None:
                        self.create_image(
                            id=img['id'],
                            name=img['name'],
                            disk_format=img['disk_format'] or "qcow2",
                            location=meta['img_loc'],
                            container_format=img['container_format'] or 'bare',
                        )

                        recreated_image = utl.ext_dict(
                            name=img["name"]
                        )
                        created_images.append((recreated_image, meta))
                    else:
                        raise exception.AbortMigrationError(
                            "image information has no original source URL")
                    continue

                LOG.debug("Creating image '%s' (%s)", img["name"], img['id'])
                # we can face situation when image has no
                # disk_format and container_format properties
                # this situation appears, when image was created
                # with option --copy-from
                # glance-client cannot create image without this
                # properties, we need to create them artificially
                # and then - delete from database

                try:
                    file_obj = img['resource'].get_ref_image(img['id'])
                    data_proxy = file_proxy.FileProxy(
                        file_obj,
                        name="image %s ('%s')" % (img['name'], img['id']),
                        size=img['size'])

                    created_image = self.create_image(
                        id=img['id'],
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
                    LOG.debug("new image ID %s", created_image.id)
                    self.update_membership(created_image.id, image_members)
                    created_images.append((created_image, meta))
                except (exception.ImageDownloadError,
                        httplib.IncompleteRead,
                        glance_exceptions.HTTPInternalServerError) as e:
                    LOG.debug(e, exc_info=True)
                    LOG.warning("Unable to reach image's data due to "
                                "Glance HTTPInternalServerError. Skipping "
                                "image: %s (%s)", img['name'], img["id"])
                    obsolete_images_ids_list.append(img["id"])
                    continue

                if not img["container_format"]:
                    delete_container_format.append(created_image.id)
                if not img["disk_format"]:
                    delete_disk_format.append(created_image.id)
            elif img['resource'] is None:
                recreated_image = utl.ext_dict(name=img["name"])
                created_images.append((recreated_image, meta))
            elif not img:
                empty_image_list[image_id_src] = info['images'][image_id_src]

        view.show_progress()
        if obsolete_images_ids_list:
            LOG.warning('List of broken images: %s', obsolete_images_ids_list)
            # Remove obsolete/broken images from info
            for img_id in obsolete_images_ids_list:
                info['images'].pop(img_id)

        return self._new_info(created_images, empty_image_list,
                              delete_disk_format, delete_container_format)

    def _new_info(self, created_images, empty_image_list, delete_disk_format,
                  delete_container_format):
        new_info = {'images': {}}
        if created_images:
            im_name_list = [(im.name, tmp_meta) for (im, tmp_meta) in
                            created_images]
            LOG.debug("images on destination: %s",
                      [im for (im, tmp_meta) in im_name_list])
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
            with settings(host_string=self.ssh_host,
                          connection_attempts=ssh_attempts):
                out = json.loads(
                    run("rbd -p images info %s --format json" % image_id))
                image_from_glance.update(size=out["size"])
