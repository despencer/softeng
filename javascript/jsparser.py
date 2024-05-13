#!/usr/bin/python3

import json
import argparse
from pyjsparser import parse

def checknode(node, keys, nodetype = None):
    if nodetype != None and node['type'] != nodetype:
        raise Exception('Mismatched node type ' + node['type'] + ' (should be ' + nodetype + ')')
    if isinstance(keys, str):
        keys = [ keys ]
    keys.append('type')
    for k in node.keys():
        if k not in keys:
            raise Exception('Unknown key ' + k)

class Operand:
    literal = 1
    identifier = 2
    parameter = 3

    def __init__(self, kind, value, raw):
        self.kind = kind
        self.value = value
        self.raw = raw

    def pretty(self, rules):
        return self.raw

class Block:
    def __init__(self):
        self.vardecl = []
        self.exprs = []
        self.funcs = []
        self.statements = []

    def pretty(self, rules):
        buf = ''
        for s in self.statements:
            buf += s.pretty(rules) + '\n'
        return buf

    @classmethod
    def load(cls, astnode):
        block = Block()
        for x in astnode:
            if x['type'] == 'VariableDeclaration':
                checknode(x, ['declarations', 'kind'])
                for vdn in x['declarations']:
                    vd = VariableDeclaration.load(vdn, x['kind'])
                    block.vardecl.append(vd)
                    block.statements.append(vd)
            elif x['type'] == 'ExpressionStatement':
                checknode(x, 'expression')
                ex = Expression.load(x['expression'])
                block.exprs.append(ex)
                block.statements.append(ex)
            elif x['type'] == 'FunctionDeclaration':
                fn = Function.load(x, True)
                block.funcs.append(fn)
                block.statements.append(fn)
            elif x['type'] == 'EmptyStatement':
                checknode(x, [])
                ex = Expression()
                block.exprs.append(ex)
                block.statements.append(ex)
            else:
                raise Exception('Unknown type ' + x['type'])
        return block

class Function:
    def __init__(self, name, decl):
        self.name = name
        self.decl = decl
        self.params = []

    def pretty(self, rules):
        buf = 'function'
        if self.name != None:
            buf += ' ' + self.name
        buf += '(' + ','.join( map(lambda x: x.pretty(rules), self.params) ) + ')'
        if not self.decl:
            buf = '(' + buf + ')'
        return buf

    @classmethod
    def load(cls, astnode, decl):
        checknode(astnode, ['id','params','defaults','body','generator','expression'])
        checknode(astnode['id'], 'name')
        if astnode['generator'] or astnode['expression']:
            raise Exception('Generators or expressions are not yet implemented')
        if len(astnode['defaults']) < 0:
            raise Exception('Defaults are not yet implemented')
        func = Function(astnode['id']['name'], decl, Block.load(astnode['body']) )
        for p in astnode['params']:
            if p['type'] != 'Identifier':
                raise Exception('Unsupported parameter ' + p['type'])
            checknode(p, 'name')
            func.params.append( Operand(Operand.parameter, p['name'], p['name']) )
        return func

class Call:
    def __init__(self, callee):
        self.callee = callee
        self.args = []

    def pretty(self, rules):
        return self.callee.pretty(rules) + '(' + ','.join( map(lambda x: x.pretty(rules), self.args) ) + ');'

    @classmethod
    def load(cls, astnode):
        checknode(astnode, ['callee','arguments'] )
        call = Call(Expression.load(astnode['callee']))
        for a in astnode['arguments']:
            call.args.append( Expression.load(a) )
        return call

class Expression:
    def pretty(self, rules):
        return ''

    @classmethod
    def load(cls, astnode):
        if astnode['type'] == 'Literal':
            checknode(astnode, ['value','raw'])
            return Operand(Operand.literal, astnode['value'], astnode['raw'])
        elif astnode['type'] == 'CallExpression':
            return Call.load(astnode)
        elif astnode['type'] == 'FunctionExpression':
            return Function.load(astnode, false)
        elif astnode['type'] == 'Identifier':
            checknode(astnode, 'name')
            return Operand(Operand.identifier, astnode['name'], astnode['name'])
        else:
            raise Exception('Unknown expression type ' + astnode['type'])
        return None

class VariableDeclaration:
    def __init__(self):
        self.id = None
        self.kind = None
        self.expression = None

    def pretty(self, rules):
        buf = self.kind + ' ' + self.id
        if self.expression != None:
            buf += ' = ' + self.expression.pretty(rules)
        buf += ';'
        return buf

    @classmethod
    def load(cls, astnode, kind):
        checknode(astnode, ['id', 'init'], nodetype = 'VariableDeclarator')
        checknode(astnode['id'], 'name', nodetype='Identifier')
        vd = VariableDeclaration()
        vd.id = astnode['id']['name']
        vd.kind = kind
        if 'init' in astnode:
            vd.expression = Expression.load(astnode['init'])
        return vd

class Program:
    def __init__(self, body):
        self.body = body

    def pretty(self, rules):
        return self.body.pretty(rules)

    @classmethod
    def load(cls, astnode):
        checknode(astnode, 'body')
        return Program( Block.load(astnode['body']) )

def load(jssource):
    ast = parse(jssource);
    if ast['type'] != 'Program':
        raise Exception('Invalid AST ' + ast['type'])
    else:
        return Program.load(ast)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reads a javascript file')
    parser.add_argument('js', help='a js file')
    args = parser.parse_args()
    with open(args.js) as jsfile:
        load(jsfile.read())
