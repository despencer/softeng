#!/usr/bin/python3

import json
import argparse
from pyjsparser import parse

class Rules:
    def __init__(self):
        self.indent = ''
        self.baseindent = 4

    def newindent(self):
        return ''.ljust(self.baseindent)

    def pushindent(self):
        self.indent += self.newindent()

    def popindent(self):
        self.indent = self.indent[:-self.baseindent]

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

class Operation:
    general = 1
    assignment = 2
    dotmember = 3
    bracketmember = 4
    logical = 5

    def __init__(self, operator, left, right, kind = general):
        self.operator = operator
        self.left = left
        self.right = right
        self.kind = kind

    @classmethod
    def prettyoperand(cls, op, rules):
        if isinstance(op, Operand):
            return op.pretty(rules)
        else:
            return '(' + op.pretty(rules) + ')'

    def pretty(self, rules):
        if self.kind == Operation.assignment:
            return self.left.pretty(rules) + ' ' + self.operator + ' ' + self.right.pretty(rules)
        elif self.kind == Operation.dotmember:
            return self.left.pretty(rules) + '.' + self.right.pretty(rules)
        elif self.kind == Operation.bracketmember:
            return self.left.pretty(rules) + '[' + self.right.pretty(rules) + ']'
        return Operation.prettyoperand(self.left, rules) + self.operator + Operation.prettyoperand(self.right, rules)

class Modifier:
    def __init__(self, operator, argument):
        self.operator = operator
        self.argument = argument

    def pretty(self, rules):
        return self.operator + ' ' + Operation.prettyoperand(self.argument, rules)

class ConditionalExpression:
    def __init__(self, test, consequent, alternate):
        self.test = test
        self.consequent = consequent
        self.alternate = alternate

    def pretty(self, rules):
        return '(' + self.test.pretty(rules) + ') ? ' + Operation.prettyoperand(self.consequent, rules) + ' : ' + Operation.prettyoperand(self.alternate, rules)

class ConditionalStatement:
    def __init__(self, test, consequent, alternate):
        self.test = test
        self.consequent = consequent
        self.alternate = alternate

    def pretty(self, rules):
        buf = 'if (' + self.test.pretty(rules) + ')\n'
        buf += rules.newindent() + self.consequent.pretty(rules) + ';\n'
        if self.alternate != None:
            buf += 'else\n'
            buf += rules.newindent() + self.alternate.pretty(rules) + ';\n'
        return buf

class Block:
    def __init__(self):
        self.vardecl = []
        self.exprs = []
        self.funcs = []
        self.statements = []
        self.top = False

    def pretty(self, rules):
        buf = ''
        indent = rules.indent
        if not self.top:
            rules.pushindent()
        for s in self.statements:
            local = s.pretty(rules)
            if len(local) > 0:
                if s in self.funcs:
                    buf += rules.indent + local
                else:
                    buf += rules.indent + local + ';\n'
        if not self.top:
            buf = indent + '{\n' + buf + indent + '}\n'
            rules.popindent()
        return buf

    checks = { 'VariableDeclaration':['declarations', 'kind'], 'ExpressionStatement':'expression', 'FunctionDeclaration':None,
               'EmptyStatement':[], 'ReturnStatement':'argument', 'IfStatement':['test','consequent','alternate'],
               'BlockStatement':'body' }
    loads = { 'VariableDeclaration': lambda x: Block.loadvardecl(x) , 'ExpressionStatement': lambda x: Expression.load(x['expression']),
              'FunctionDeclaration': lambda x: Function.load(x, True), 'EmptyStatement': lambda x: Expression(),
              'ReturnStatement': lambda x: Return(Expression.load(x['argument'])), 'IfStatement':lambda x: Block.loadconditional(x),
              'BlockStatement': lambda x: Block.load(x['body']) }

    @classmethod
    def load(cls, astnode):
        block = Block()
        dispatch = { 'VariableDeclaration': 'vardecl', 'ExpressionStatement':'exprs', 'FunctionDeclaration':'funcs', 'EmptyStatement':'exprs',
                    'ReturnStatement':'exprs',  'IfStatement':'exprs', 'BlockStatement': 'exprs'}
        for x in astnode:
            xtype = x['type']
            stmt = cls.loadstatement(x)
            if not isinstance(stmt, list):
                stmt = [ stmt ]
            getattr(block, dispatch[x['type']]).extend(stmt)
            block.statements.extend(stmt)
        return block

    @classmethod
    def loadstatement(cls, x):
        xtype = x['type']
        if xtype in cls.checks:
            if cls.checks[xtype] != None:
                checknode(x, cls.checks[xtype])
        else:
            raise Exception('Unknown block statement ' + x['type'])
        return cls.loads[xtype](x)

    @classmethod
    def loadvardecl(cls, x):
        vds = []
        for vdn in x['declarations']:
            vds.append( VariableDeclaration.load(vdn, x['kind']) )
        return vds

    @classmethod
    def loadconditional(cls, x):
        return ConditionalStatement( Expression.load(x['test']), Block.loadstatement(x['consequent']),
                                     None if x['alternate'] == None else Block.loadstatement(x['alternate']) )

class Function:
    def __init__(self, name, decl, body):
        self.name = name
        self.decl = decl
        self.params = []
        self.body = body

    def pretty(self, rules):
        buf = 'function'
        if self.name != None:
            buf += ' ' + self.name
        buf += '(' + ','.join( map(lambda x: x.pretty(rules), self.params) ) + ')\n'
        buf += self.body.pretty(rules)
        if not self.decl:
            buf = '(' + buf + ')'
        buf += '\n'
        return buf

    @classmethod
    def load(cls, astnode, decl):
        checknode(astnode, ['id','params','defaults','body','generator','expression'])
        if astnode['id'] != None:
            checknode(astnode['id'], 'name')
            funcname = astnode['id']['name']
        else:
            funcname = None
        if astnode['generator'] or astnode['expression']:
            raise Exception('Generators or expressions are not yet implemented')
        if len(astnode['defaults']) < 0:
            raise Exception('Defaults are not yet implemented')
        if astnode['body']['type'] != 'BlockStatement':
            raise Exception('Unknown function body')
        func = Function(funcname, decl, Block.load(astnode['body']['body']) )
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
        return self.callee.pretty(rules) + '(' + ','.join( map(lambda x: x.pretty(rules), self.args) ) + ')'

    @classmethod
    def load(cls, astnode):
        checknode(astnode, ['callee','arguments'] )
        call = Call(Expression.load(astnode['callee']))
        for a in astnode['arguments']:
            call.args.append( Expression.load(a) )
        return call

class Return:
    def __init__(self, expression):
        self.expression = expression

    def pretty(self, rules):
        return 'return ' + self.expression.pretty(rules)


class Expression:
    def pretty(self, rules):
        return ''

    binary = { 'BinaryExpression':Operation.general, 'AssignmentExpression':Operation.assignment, 'LogicalExpression':Operation.logical }

    @classmethod
    def load(cls, astnode):
        if astnode['type'] == 'Literal':
            checknode(astnode, ['value','raw'])
            return Operand(Operand.literal, astnode['value'], astnode['raw'])
        elif astnode['type'] == 'CallExpression':
            return Call.load(astnode)
        elif astnode['type'] == 'FunctionExpression':
            return Function.load(astnode, False)
        elif astnode['type'] == 'MemberExpression':
            checknode(astnode, ['computed', 'object', 'property'])
            kind = Operation.bracketmember if astnode['computed'] else Operation.dotmember
            return Operation('.', Expression.load(astnode['object']), Expression.load(astnode['property']), kind=kind )
        elif astnode['type'] == 'Identifier':
            checknode(astnode, 'name')
            return Operand(Operand.identifier, astnode['name'], astnode['name'])
        elif astnode['type'] in cls.binary:
            checknode(astnode, ['operator','left','right'])
            return Operation( astnode['operator'], Expression.load(astnode['left']), Expression.load(astnode['right']), kind=cls.binary[astnode['type']] )
        elif astnode['type'] == 'ConditionalExpression':
            checknode(astnode, ['test', 'consequent', 'alternate'])
            return ConditionalExpression( Expression.load(astnode['test']), Expression.load(astnode['consequent']), Expression.load(astnode['alternate']) )
        elif astnode['type'] == 'UnaryExpression':
            checknode(astnode, ['operator', 'argument', 'prefix'])
            if astnode['prefix'] != True:
                raise Exception('Prefix is not True for UnaryExpression')
            return Modifier( astnode['operator'], Expression.load(astnode['argument']) )
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
        self.body.top = True

    def pretty(self, rules):
        return self.body.pretty(rules)

    @classmethod
    def load(cls, astnode):
        checknode(astnode, 'body')
        return Program( Block.load(astnode['body']) )

def load(jssource):
    ast = parse(jssource)
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
