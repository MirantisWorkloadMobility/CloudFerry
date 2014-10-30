import sqlalchemy


class MysqlConnector():
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.connection_url = self.compose_connection_url()

    def compose_connection_url(self):
        return '{}://{}:{}@{}/{}'.format(self.config['connection'],
                                         self.config['user'],
                                         self.config['password'],
                                         self.config['host'],
                                         self.db)

    def execute(self, command, **kwargs):
        with sqlalchemy.create_engine(
                self.connection_url).begin() as connection:
            return connection.execute(sqlalchemy.text(command), **kwargs)
