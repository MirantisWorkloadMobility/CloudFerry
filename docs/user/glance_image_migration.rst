.. _glance-image-migration:

======================
Glance image migration
======================

Glance images have following attributes:

 - Private or public
     - Public images are accessible from ALL tenants, thus potentially any VM
       may be created from an image from another tenant.
 - Image memberships
     - Private images are allowed to have :dfn:`members` – other tenants
       which have access to an image.

With the above in mind and given that there is currently no support for
relationships between objects in CloudFerry (this is planned for future
releases), there are following ways of performing glance image migration:

 1. Copy all public images and images with memberships in other tenants, plus
    all associated tenants, or
 2. Copy only images which are specified in
    :ref:`filtering config <filter-configuration>`, that is either only
    images belonging to a tenant, or image IDs specified.

That behavior is controlled by
:dfn:`dont_include_public_and_members_from_other_tenants` option specified in
:ref:`filter file <filter-configuration>`.


Process
-------

 1. Download image from source cloud using glance APIs;
 2. Upload image to destination cloud using glance APIs;
 3. Glance image UUID will be kept in destination, unless an image with the
    same ID exists or existed previously.

.. note::

    Process above **does not** create extra copy of image anywhere, instead
    it redirects image from source cloud to destination using system streams.


Frequently Asked Questions
--------------------------

**Q**: I specified only 1 (one!) image in
:ref:`filter file <filter-configuration>`, but it tries to migrate all the
public images in the cloud! WTF???

**A**: This is happening because potentially VM may be booted from any public
image or image with membership in a migrated tenant. In case you're only
trying to migrate images, and no other resources (for example, you're using
:file:`3_get_and_transfer_images.yaml` as your scenario), than you can
override this behavior by making
:dfn:`dont_include_public_and_members_from_other_tenants` option
enabled in :ref:`filter file <filter-configuration>`. If it still tries to
migrate all the images - make sure you have :dfn:`act_get_filter` action
enabled in your scenario.


**Q**: Glance APIs allow specifying glance images IDs, but image I
migrated has different ID. WTF???

**A**: Glance image IDs are only kept if image with that ID does not exist or
existed previously in destination cloud. Glance keeps deleted images and their
IDs and does allow to create image with the ID already known to glance.
