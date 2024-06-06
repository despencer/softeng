#!/usr/bin/python3

import json
import argparse
from pyjsparser import parse

class Rules:
    def __init__(self):
        self.indent = '    '
        self.reqsm = [ Operation, Operand, Modifier, ConditionalExpression, Call, Action, VariableDeclaration, Object ]

    def applyindent(self, code):
        lines = code.split('\n')
        if lines[-1] == '':
            lines = [ *(map(lambda x: self.indent+x, lines[:-1])) , lines[-1] ]
        else:
            lines = list(map(lambda x: self.indent+x, lines))
        return '\n'.join(lines)

    def endmark(self, stmt):
        if stmt.__class__ in self.reqsm:
            return ';\n'
        return ''

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
    this = 4
    regex = 5

    def __init__(self, kind, value, raw):
        self.kind = kind
        self.value = value
        self.raw = raw

    def pretty(self, rules):
        if self.kind == Operand.regex:
            return '(' + self.raw + ')'
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
        return Operation.prettyoperand(self.left, rules) + ' ' + self.operator + ' ' + Operation.prettyoperand(self.right, rules)

class Modifier:
    def __init__(self, operator, argument, prefix):
        self.operator = operator
        self.argument = argument
        self.prefix = prefix

    def pretty(self, rules):
        if self.prefix:
            return self.operator + Operation.prettyoperand(self.argument, rules)
        else:
            return Operation.prettyoperand(self.argument, rules) + self.operator

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
        buf = 'if ( ' + self.test.pretty(rules) + ' )\n'
        buf += rules.applyindent( self.consequent.pretty(rules) + rules.endmark(self.consequent) )
        if self.alternate != None:
            buf += 'else\n'
            buf += rules.applyindent( self.alternate.pretty(rules) + rules.endmark(self.alternate) )
        return buf

class Handler:
    def __init__(self):
        self.block = None
        self.param = None
        self.catcher = None
        self.finalizer = None

    def pretty(self, rules):
        buf = 'try\n' + rules.applyindent( self.block.pretty(rules) + rules.endmark(self.block) )
        if self.catcher != None:
            buf += 'catch ( ' + self.param + ' )\n' + rules.applyindent( self.catcher.pretty(rules) + rules.endmark(self.catcher) )
        if self.finalizer != None:
            buf += 'finally \n' + rules.applyindent( self.finalizer.pretty(rules) + rules.endmark(self.finalizer) )
        return buf

    @classmethod
    def load(cls, astnode):
        checknode(astnode, ['block', 'handler', 'guardedHandlers', 'handlers', 'finalizer'])
        checknode(astnode['block'], 'body', nodetype = 'BlockStatement')
        if not (isinstance(astnode['guardedHandlers'], list) and len(astnode['guardedHandlers']) == 0):
            raise Exception ('Bad guardedHandlers in try-catch')
        handler = cls()
        handler.block = Block.load(astnode['block']['body'])
        if astnode['handler'] != None:
            if len(astnode['handlers']) != 1:
                raise Exception('Handlers array is of unusual size in try-catch')
            checknode(astnode['handler'], ['param','body'], nodetype = 'CatchClause')
            checknode(astnode['handler']['param'], 'name', nodetype = 'Identifier')
            checknode(astnode['handler']['body'], 'body', nodetype = 'BlockStatement')
            handler.param = astnode['handler']['param']['name']
            handler.catcher = Block.load( astnode['handler']['body']['body'] )
        else:
            if len(astnode['handlers']) > 0:
                raise Exception('Handlers array is not empty in try-catch')
        if astnode['finalizer'] != None:
            checknode(astnode['finalizer'], 'body', nodetype = 'BlockStatement')
            handler.finalizer = Block.load( astnode['finalizer']['body'] )
        return handler

class Block:
    def __init__(self):
        self.vardecl = []
        self.exprs = []
        self.funcs = []
        self.statements = []
        self.top = False

    def pretty(self, rules):
        buf = ''
        for s in self.statements:
            buf += s.pretty(rules) + rules.endmark(s)
        if not self.top:
            buf = '{\n' + rules.applyindent(buf) + '}\n'
        return buf

    checks = { 'VariableDeclaration':['declarations', 'kind'], 'ExpressionStatement':'expression', 'FunctionDeclaration':None,
               'EmptyStatement':[], 'ReturnStatement':'argument', 'IfStatement':['test','consequent','alternate'],
               'BlockStatement':'body', 'ThrowStatement':'argument', 'ForStatement':None,  'ForInStatement':None, 
               'BreakStatement': 'label', 'ContinueStatement': 'label', 'WhileStatement':None, 'TryStatement':None}
    loads = { 'VariableDeclaration': lambda x: Block.loadvardecl(x) , 'ExpressionStatement': lambda x: Expression.load(x['expression']),
              'FunctionDeclaration': lambda x: Function.load(x, Function.declaration), 'EmptyStatement': lambda x: Expression(),
              'ReturnStatement': lambda x: Action(Expression.load(x['argument']), kind=Action.Return), 'IfStatement':lambda x: Block.loadconditional(x),
              'BlockStatement': lambda x: Block.load(x['body']), 'ThrowStatement': lambda x: Action(Expression.load(x['argument']), kind=Action.Throw),
              'ForStatement':lambda x: Loop.loadfor(x), 'ForInStatement':lambda x: Iterator.load(x),
              'BreakStatement': lambda x: Block.loadcontrol(x, Action.Break), 'ContinueStatement': lambda x: Block.loadcontrol(x, Action.Continue),
              'WhileStatement':lambda x: Loop.loadwhile(x), 'TryStatement': Handler.load }

    @classmethod
    def load(cls, astnode):
        block = Block()
        dispatch = { 'VariableDeclaration': 'vardecl', 'ExpressionStatement':'exprs', 'FunctionDeclaration':'funcs', 'EmptyStatement':'exprs',
                    'ReturnStatement':'exprs',  'ThrowStatement':'exprs', 'IfStatement':'exprs', 'BlockStatement': 'exprs', 'ForStatement':'exprs',
                    'ForInStatement':'exprs', 'BreakStatement':'exprs', 'ContinueStatement':'exprs', 'WhileStatement':'exprs', 'TryStatement':'exprs'}
        for x in astnode:
            xtype = x['type']
            stmt = cls.loadstatement(x)
            if not isinstance(stmt, list):
                stmt = [ stmt ]
            getattr(block, dispatch[x['type']]).extend(stmt)
            block.statements.extend(stmt)
        return block

    @classmethod
    def loadstatement(cls, astnode):
        xtype = astnode['type']
        if xtype in cls.checks:
            if cls.checks[xtype] != None:
                checknode(astnode, cls.checks[xtype])
        else:
            print(astnode)
            raise Exception('Unknown block statement ' + xtype)
        return cls.loads[xtype](astnode)

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

    @classmethod
    def loadcontrol(cls, astnode, kind):
        if astnode['label'] != None:
            raise Exception(astnode['type'] + ' with labels are unsupported')
        return Action(None, kind)

class Iterator:
    def __init__(self, itervar, rangedecl, body):
        self.itervar = itervar
        self.rangedecl = rangedecl
        self.body = body

    def pretty(self, rules):
        buf = 'for(' + self.itervar.pretty(rules) + ' in ' + self.rangedecl.pretty(rules) + ')\n'
        buf += rules.applyindent( self.body.pretty(rules) + rules.endmark(self.body) )
        return buf

    @classmethod
    def load(self, astnode):
        checknode(astnode, ['left','right','each','body'])
        if astnode['each']:
            raise Exception("'each' attribute should be false in for-in statement")
        return Iterator( Expression.load(astnode['left']), Expression.load(astnode['right']), Block.loadstatement(astnode['body']) )

class Loop:
    For = 1
    While = 2

    def __init__(self, kind):
        self.kind = kind
        self.init = []
        self.test = None
        self.update = None
        self.body = None

    def pretty(self, rules):
        if self.kind == Loop.For:
            buf = 'for(' + ' ,'.join( map(lambda x: x.pretty(rules), self.init)) + '; '
        else:
            buf = 'while( ';
        if self.test != None:
            buf += self.test.pretty(rules)
        if self.kind == Loop.For:
            buf += '; '
            if self.update != None:
                buf += self.update.pretty(rules)
        buf += ')\n'
        buf += rules.applyindent( self.body.pretty(rules) + rules.endmark(self.body) )
        return buf

    @classmethod
    def loadfor(cls, astnode):
        checknode(astnode, ['init','test','update','body'])
        loop = cls(Loop.For)
        if astnode['init'] != None:
            if astnode['init']['type'] == 'VariableDeclaration':
                checknode( astnode['init'], ['declarations', 'kind'] )
                loop.init.extend( Block.loadvardecl(astnode['init']) )
            else:
                loop.init.append( Expression.load(astnode['init']) )
        if astnode['test'] != None:
            loop.test = Expression.load(astnode['test'])
        if astnode['update'] != None:
            loop.update = Expression.load(astnode['update'])
        loop.body = Block.loadstatement(astnode['body'])
        return loop

    @classmethod
    def loadwhile(cls, astnode):
        checknode(astnode, ['test','body'])
        loop = cls(Loop.While)
        if astnode['test'] != None:
            loop.test = Expression.load(astnode['test'])
        loop.body = Block.loadstatement(astnode['body'])
        return loop

class Function:
    declaration = 1
    inline = 2
    objprop = 3

    def __init__(self, name, kind, body):
        self.name = name
        self.kind = kind
        self.params = []
        self.body = body

    def pretty(self, rules):
        if self.kind != Function.objprop:
            buf = 'function'
        else:
            buf = ''
        if self.name != None:
            buf += ' ' + self.name
        buf += '(' + ','.join( map(lambda x: x.pretty(rules), self.params) ) + ')\n'
        buf += self.body.pretty(rules)
        if self.kind == Function.inline:
            buf = '(' + buf + ')'
        if self.kind != Function.objprop:
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
    call = 1
    new = 2

    def __init__(self, callee, kind, args):
        self.kind = kind
        self.callee = callee
        self.args = args

    def pretty(self, rules):
        buf = ''
        if self.kind == Call.new:
            buf += 'new '
        return buf + self.callee.pretty(rules) + self.args.pretty(rules)

    @classmethod
    def load(cls, astnode, kind):
        checknode(astnode, ['callee','arguments'] )
        return Call(Expression.load(astnode['callee']), kind, Combinator.load(astnode['arguments'], '()') )

class Property:
    init = 1
    shorthand = 2
    method = 3
    setter = 4
    getter = 5

    def __init__(self, kind, key, value):
        self.kind = kind
        self.key = key
        self.value = value
        if self.kind in [Property.method, Property.setter, Property.getter] and isinstance(self.value, Function):
            self.value.kind = Function.objprop
            self.value.name = ''

    def pretty(self, rules):
        return { Property.init : lambda: self.key + ' : ' + self.value.pretty(rules) ,
                 Property.shorthand : lambda: self.key ,
                 Property.method: lambda: self.key + ' ' + self.value.pretty(rules) ,
                 Property.setter: lambda: 'set ' + self.key + ' ' + self.value.pretty(rules) ,
                 Property.getter: lambda: 'get ' + self.key + ' ' + self.value.pretty(rules) }[self.kind]()

    @classmethod
    def getkind(cls, astnode):
        if astnode['kind'] == 'init':
            if astnode['method']:
                return Property.method
            elif astnode['shorthand']:
                return Property.shorthand
            else:
                return Property.init
        elif astnode['kind'] == 'set':
            return Property.setter
        elif astnode['kind'] == 'get':
            return Property.getter
        else:
            raise Exception('Unknown property kind ' + astnode['kind'])

class Object:
    def __init__(self):
        self.properties = []

    def pretty(self, rules):
        buf = ''
        for s in self.properties:
            buf += s.pretty(rules) + ',\n'
        buf = '{\n' + rules.applyindent(buf) + '}'
        return buf

    @classmethod
    def load(cls, astnode):
        checknode(astnode, 'properties')
        obj = Object()
        for p in astnode['properties']:
            checknode(p, ['key', 'computed', 'value', 'kind', 'method', 'shorthand'], nodetype = 'Property')
            checknode(p['key'], 'name', nodetype = 'Identifier')
            if p['computed']:
                raise Exception('Computed properties are not supported')
            obj.properties.append( Property(Property.getkind(p), p['key']['name'], Expression.load(p['value'])) )
        return obj

class Combinator:
    def __init__(self, kind):
        self.open = kind[0]
        self.close = kind[-1]
        self.args = []

    def pretty(self, rules):
        return self.open + ' ,'.join( map(lambda x: x.pretty(rules), self.args) ) + self.close

    @classmethod
    def load(cls, astnode, kind):
        combinator = Combinator(kind)
        for a in astnode:
            combinator.args.append( Expression.load(a) )
        return combinator

class Action:
    Return = 1
    Throw = 2
    Break = 3
    Continue = 4

    def __init__(self, expression, kind):
        self.expression = expression
        self.kind = kind

    def pretty(self, rules):
        buf = { Action.Return:'return', Action.Throw:'throw', Action.Break:'break', Action.Continue:'continue' }[self.kind]
        if self.expression != None:
            buf += ' ' + self.expression.pretty(rules)
        return buf


class Expression:
    def pretty(self, rules):
        return ''

    binary = { 'BinaryExpression':Operation.general, 'AssignmentExpression':Operation.assignment, 'LogicalExpression':Operation.logical }
    call = { 'CallExpression':Call.call, 'NewExpression':Call.new }

    @classmethod
    def load(cls, astnode):
        if astnode['type'] == 'Literal':
            checknode(astnode, ['value','raw','regex'])
            return Operand( Operand.regex if 'regex' in astnode else Operand.literal, astnode['value'], astnode['raw'])
        elif astnode['type'] in cls.call:
            return Call.load(astnode, cls.call[astnode['type']])
        elif astnode['type'] == 'FunctionExpression':
            return Function.load(astnode, Function.inline)
        elif astnode['type'] == 'MemberExpression':
            checknode(astnode, ['computed', 'object', 'property'])
            kind = Operation.bracketmember if astnode['computed'] else Operation.dotmember
            return Operation('.', Expression.load(astnode['object']), Expression.load(astnode['property']), kind=kind )
        elif astnode['type'] == 'Identifier':
            checknode(astnode, 'name')
            return Operand(Operand.identifier, astnode['name'], astnode['name'])
        elif astnode['type'] == 'ThisExpression':
            checknode(astnode, [])
            return Operand(Operand.this, 'this', 'this')
        elif astnode['type'] in cls.binary:
            checknode(astnode, ['operator','left','right'])
            return Operation( astnode['operator'], Expression.load(astnode['left']), Expression.load(astnode['right']), kind=cls.binary[astnode['type']] )
        elif astnode['type'] == 'ConditionalExpression':
            checknode(astnode, ['test', 'consequent', 'alternate'])
            return ConditionalExpression( Expression.load(astnode['test']), Expression.load(astnode['consequent']), Expression.load(astnode['alternate']) )
        elif astnode['type'] == 'UnaryExpression' or astnode['type'] == 'UpdateExpression':
            checknode(astnode, ['operator', 'argument', 'prefix'])
            return Modifier( astnode['operator'], Expression.load(astnode['argument']), astnode['prefix'] )
        elif astnode['type'] == 'ArrayExpression':
            checknode(astnode, 'elements')
            return Combinator.load(astnode['elements'], '[]')
        elif astnode['type'] == 'ObjectExpression':
            return Object.load(astnode)
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
        if 'init' in astnode and astnode['init'] != None:
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
