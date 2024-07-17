#!/usr/bin/python3

import importlib
import argparse
import yaml
import inspect

class ModuleDump:
    def __init__(self):
        pass

    def clsfuncs(self, iclsobj, klass):
        klass['methods'] = []
        for obj in dir(iclsobj):
            if callable(getattr(iclsobj,obj)):
                print(obj)

    def clsbases(self, iclsobj, klass):
        bases = [ * (iclsobj.__bases__) ]
        if len(bases) == 1:
            if bases[0].__name__ != 'object':
                klass['base'] = bases[0].__name__
        else:
            klass['base'] = []
            for b in bases:
                klass['base'].append( b.__name__)

    def classes(self, module):
        classes = []
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                klass = { 'name':obj.__name__ }
                self.clsbases(obj, klass)
                self.clsfuncs(obj, klass)
                classes.append(klass)
        return classes

    def dump(self, modname):
        module = importlib.import_module(modname)
        desc = {'module': {'name':modname, 'classes':self.classes(module)}}
        return desc

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dumps contents of a module')
    parser.add_argument('module', help='module name')
    args = parser.parse_args()
    desc = ModuleDump().dump(args.module)
    with open(args.module+'.int', 'w') as strfile:
        yaml.dump(desc, strfile, default_flow_style=False)

