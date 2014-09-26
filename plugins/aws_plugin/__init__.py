from oslo.config import cfg
__author__ = 'mirrorcoder'

migrate = cfg.OptGroup(name='migrate',
                       title='Credetionals and general '
                             'config for source cloud')

migrate_opts = [
    cfg.StrOpt('pol', default="os",
               help='os - OpenStack Cloud'),
    cfg.StrOpt('keep_user_passwords', default="no",
               help='yes - keep user passwords, no - not keep user passwords')

]

cfg_for_reg = [
    (migrate, migrate_opts)
]