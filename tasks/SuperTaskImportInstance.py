from scheduler.SuperTask import SuperTask

__author__ = 'mirrorcoder'


class SuperTaskImportInstance(SuperTask):

    def run(self, data_export_inst=None, inst_importer=None, **kwargs):
        tasks_import = []
        importer_builder = inst_importer.upload(data_export_inst)
        tasks = importer_builder.get_tasks()
        tasks_import.extend(tasks)
        return tasks_import
