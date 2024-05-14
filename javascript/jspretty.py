#!/usr/bin/python3

import argparse
import jsparser

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pretty prints a javascript file')
    parser.add_argument('js', help='a js file')
    args = parser.parse_args()
    with open(args.js) as jsfile:
        rules = jsparser.Rules()
        jsprog = jsparser.load(jsfile.read())
        print(jsprog.pretty(rules))