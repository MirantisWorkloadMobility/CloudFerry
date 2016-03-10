from oslo_config import cfg

__author__ = 'mirrorcoder'

migrate = cfg.OptGroup(name='migrate',
                       title='Credetionals and general '
                             'config for source cloud')

migrate_opts = [
    cfg.StrOpt('pol', default="os",
               help='os - OpenStack Cloud'),
    cfg.BoolOpt('keep_user_passwords', default=False,
                help='True - keep user passwords, '
                     'False - not keep user passwords')

]

cfg_for_reg = [
    (migrate, migrate_opts)
]
