#!/usr/bin/python3

import importlib
import argparse

class ModuleDump:
    def __init__(self):
        pass

    def dump(self, modname):
        importlib.import_module(modname)
        buf = '# ' + modname
        return buf

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dumps contents of a module')
    parser.add_argument('module', help='module name')
    args = parser.parse_args()
    print(ModuleDump().dump(args.module))
