__author__ = 'toha'

from jinja2 import Environment, FileSystemLoader



env = Environment(loader=FileSystemLoader('templates'))
template = env.get_template('info.html')
output_from_parsed_template = template.render(tenants='bla - tenants', users='test-users', roles='test-roles')
print output_from_parsed_template

with open("my_new_file.html", "wb") as fh:
    fh.write(output_from_parsed_template)
