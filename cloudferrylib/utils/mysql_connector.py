import sqlalchemy


class MysqlConnector():
    def __init__(self, config):
        self.config = config
        self.connection_url = self.compose_connection_url()

    def compose_connection_url(self):
        return '{}://{}:{}@{}/keystone'.format(self.config['connection'],
                                               self.config['user'],
                                               self.config['password'],
                                               self.config['host'])

    def execute(self, command, **kwargs):
        with sqlalchemy.create_engine(
                self.connection_url).begin() as connection:
            return connection.execute(sqlalchemy.text(command), **kwargs)