# Copyright (c) 2016 Mirantis Inc.
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
from cloudferrylib.utils import log


LOG = log.getLogger(__name__)


class UsageQuotaCompute(object):
    """
     - Change user_id
     - Decrement usage quotas:
        - instances
        - vcpus
        - RAM
        - Sec Grs
     - Increment usage quotas
        - instances
        - vcpus
        - RAM
        - Sec Grs
    """

    NOVA_INSTANCES = "nova.instances"
    NOVA_QUOTA_USAGES = "nova.quota_usages"
    NOVA_SEC_GRS = "nova.security_groups"

    @classmethod
    def change_usage_quota_instance(cls, sql_connector, flavor,
                                    old_user_id, user_id, tenant_id):

        vcpus = flavor['vcpus']
        ram = flavor['ram']
        quota = {'instances': 1,
                 'cores': vcpus,
                 'ram': ram}
        cls.dec_quota_usage(sql_connector, old_user_id,
                            tenant_id, quota)
        if not cls.check_resource(sql_connector,
                                  tenant_id,
                                  user_id,
                                  'security_groups'):
            if not cls.check_sec_groups(sql_connector, user_id, tenant_id):
                res = cls.get_sec_groups(sql_connector,
                                         old_user_id,
                                         tenant_id)
                if res.rowcount:
                    res = res.fetchall()
                    cls.insert_sec_gr(sql_connector,
                                      res[0],
                                      res[1],
                                      user_id,
                                      tenant_id)
                else:
                    LOG.info("No security group after create an instance")
                    LOG.info("USER ID = %s", user_id)
                    LOG.info("OLD USER ID = %s", old_user_id)
                    LOG.info("TENANT ID = %s", tenant_id)
            quota['security_groups'] = 1
        cls.inc_quota_usage(sql_connector, user_id,
                            tenant_id, quota)

    @classmethod
    def insert_sec_gr(cls, db, name, desc, user_id, project_id):
        sql = "INSERT INTO {nova_sec_grs}({columns}) VALUES ({values})"
        columns = "created_at,updated_at,name,description,user_id,project_id"
        values = "NOW(),NOW(),'{name}','{desc}','{user_id}','{project_id}'"\
            .format(project_id=project_id,
                    name=name,
                    user_id=user_id,
                    desc=desc)
        sql_render = sql.format(quota_usages=cls.NOVA_SEC_GRS,
                                columns=columns,
                                values=values)
        LOG.info("Insert new security group .... ")
        LOG.debug(sql_render)
        db.execute(sql_render)

    @classmethod
    def get_sec_groups(cls, db, user_id, project_id):
        sql = "SELECT name,description FROM {nova_sec_grs} " \
              "WHERE ({nova_sec_grs}.user_id='{user_id}') " \
              "AND ({nova_sec_grs}.project_id='{project_id}') "
        sql_render = sql.format(nova_sec_grs=cls.NOVA_SEC_GRS,
                                user_id=user_id,
                                project_id=project_id)
        LOG.info("Get security groups....")
        LOG.debug(sql_render)
        return db.execute(sql_render)

    @classmethod
    def check_sec_groups(cls, db, user_id, project_id):
        sql = "SELECT COUNT(*) FROM {nova_sec_grs} " \
              "WHERE ({nova_sec_grs}.user_id='{user_id}') " \
              "AND ({nova_sec_grs}.project_id='{project_id}') "
        sql_render = sql.format(nova_sec_grs=cls.NOVA_SEC_GRS,
                                user_id=user_id,
                                project_id=project_id)
        LOG.info("Check security groups....")
        LOG.debug(sql_render)
        return db.execute(sql_render).scalar

    @classmethod
    def change_user_owner_sec_grs(cls, db, security_group_id, new_user_id):
        sql = "UPDATE {sec_groups} SET " \
              "{sec_groups}.user_id = '{new_user_id}' " \
              "WHERE ({sec_groups}.id='{sec_gr_id}')"
        sql_render = sql.format(sec_gr_id=security_group_id,
                                new_user_id=new_user_id,
                                sec_groups=cls.NOVA_SEC_GRS)
        LOG.info("Change owner for security groups %s", security_group_id)
        LOG.debug(sql_render)
        db.execute(sql_render)

    @classmethod
    def dec_quota_usage(cls, db, user_id, tenant_id, quota):
        sql = "UPDATE {quota_usages} SET " \
              "{quota_usages}.in_use = {quota_usages}.in_use - " \
              "'{in_use}' WHERE ({quota_usages}.user_id='{user_id}')" \
              " and ({quota_usages}.resource='{resource}') and " \
              "({quota_usages}.project_id='{tenant_id}')"
        LOG.info("Decrement usages quota user '%s'", user_id)
        for res, value in quota.iteritems():
            sql_render = sql.format(quota_usages=cls.NOVA_QUOTA_USAGES,
                                    in_use=value, user_id=user_id,
                                    tenant_id=tenant_id, resource=res)
            LOG.debug(sql_render)
            db.execute(sql_render)

    @classmethod
    def inc_quota_usage(cls, db, user_id, tenant_id, quota):
        sql = "UPDATE {quota_usages} SET " \
              "{quota_usages}.in_use = {quota_usages}.in_use + " \
              "'{in_use}' WHERE ({quota_usages}.user_id='{user_id}')" \
              " and ({quota_usages}.resource='{resource}') and " \
              "({quota_usages}.project_id='{tenant_id}')"
        LOG.info("Increment usages quota user '%s'", user_id)
        for res, value in quota.iteritems():
            if not cls.check_resource(db, tenant_id, user_id, res):
                cls.insert_resource_usage(db, tenant_id, user_id, res)
            sql_render = sql.format(quota_usages=cls.NOVA_QUOTA_USAGES,
                                    in_use=value, user_id=user_id,
                                    tenant_id=tenant_id, resource=res)
            LOG.debug(sql_render)
            db.execute(sql_render)

    @classmethod
    def check_resource(cls, db, tenant_id, user_id, resource):
        sql = "SELECT COUNT(*) FROM {quota_usages} WHERE " \
              "({quota_usages}.project_id='{tenant_id}') and " \
              "({quota_usages}.user_id='{user_id}') and " \
              "({quota_usages}.resource='{resource}')"\
            .format(quota_usages=cls.NOVA_QUOTA_USAGES,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    resource=resource)
        LOG.info("Check resource .... ")
        LOG.debug(sql)
        res = db.execute(sql)
        return res.scalar()

    @classmethod
    def insert_resource_usage(cls, db, tenant_id, user_id, resource):
        sql = "INSERT INTO {quota_usages}({columns}) VALUES ({values})"
        columns = "created_at,updated_at,project_id," \
                  "resource,in_use,reserved,deleted,user_id"
        values = "NOW(),NOW(),'{project_id}','{resource}',0,0,0,'{user_id}'"\
            .format(project_id=tenant_id,
                    resource=resource,
                    user_id=user_id)
        sql_render = sql.format(quota_usages=cls.NOVA_QUOTA_USAGES,
                                columns=columns,
                                values=values)
        LOG.info("Insert new resource .... ")
        LOG.debug(sql_render)
        db.execute(sql_render)
