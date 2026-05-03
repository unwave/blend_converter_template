import os
import importlib

from blend_converter import serialization

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))


if __name__ == '__main__':

    module = serialization.import_module_from_file(ROOT_DIR, 'blend_converter_template')
    app = importlib.import_module(module.__name__ + '.' + 'app')
    app.main()
