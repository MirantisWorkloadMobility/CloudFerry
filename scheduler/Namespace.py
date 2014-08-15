__author__ = 'mirrorcoder'


class Namespace:

    def __init__(self, vars={}):
        self.vars = vars

    def convert_to_dict(self):
        return {
            '_type_class': Namespace.__name__,
            'vars': self.vars
        }
