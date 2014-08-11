from scheduler.SuperTask import SuperTask

__author__ = 'mirrorcoder'


class SuperTaskImportResource(SuperTask):

    def run(self, res_importer=None, resources={}, **kwargs):
        algorithm = res_importer.upload(data=resources).get_tasks()
        return algorithm