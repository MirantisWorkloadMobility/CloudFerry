__author__ = 'mirrorcoder'

import ConfigParser

config = ConfigParser.ConfigParser()
config.read("test.ini")
username = config.get('client', 'username')
password = config.get('client', 'password')
hostname = config.get('client', 'url')
config.
print username
print password
print hostname