.. _filter-configuration:

===============================
Filtering objects for migration
===============================

Filters allow user to specify objects to be migrated. Following filters are
supported:

- Filter by tenant ID (currently only one tenant ID is supported)
- Filter by object ID, where object is one or more of:
    - VM
    - cinder volume
    - glance image

Filter file is specified in :ref:`primary-config-file`::

    [migrate]
    filter_path = <path to filter file>

Filter file is a standard YAML file with following syntax::

    tenants:
        tenant_id:
            - <tenant_id>
    instances:
        id:
            - <server_id1>
            - <server_id2>
    images:
        images_list:
            - <image_id1>
            - <image_id2>
        #exclude_images_list:
        #    - <image_id1>
        #    - <image_id2>
        dont_include_public_and_members_from_other_tenants: False
    volumes:
        volumes_list:
            - <volume_id1>
            - <volume_id2>

In the config file you can specify either ``images_list`` or
``exclude_images_list`` in the images section. If you specified
``images_list`` only images specified in this list will be migrated.
If you specified ``exclude_images_list`` all images exclude images in
the list will be migrated.

When :dfn:`dont_include_public_and_members_from_other_tenants` is set to
``True`` (to which it is set by default), all the public images and images
which have membership in the tenant specified in :dfn:`tenant_id` are not
included in migration list. In other words, only images which directly belong
to :dfn:`tenant_id` are migrated, all the dependencies are ignored.
See more in :ref:`glance-image-migration`.
