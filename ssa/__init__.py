import abc
import enum
import itertools
import unittest

__names__ = [
    'ContEdge',
    'Cont',
    'Inst',
    'Param',
    'Block',
    'Procedure',
]

class ContEdge:
    def __init__(self, target):
        self.target = target
        self.args = {}

    def add_arg(self, param, value):
        if param.block != self.target:
            return
        self.args[param] = value

    def get_args(self):
        return frozenset(self.args.values())

    def debug(self, names=None, end='\n', file=None):
        if self.args:
            print(self.target.label, end='(', file=file)
            for a, v in self.args.items():
                print(a.name(names), end='=', file=file)
                print(v.name(names), end=', ', file=file)
            print(')', end=end, file=file)
        else:
            print(self.target.label, end=end, file=file)

class Cont:
    @property
    def uses(self):
        return frozenset()

    @property
    def targets(self):
        return [edge.target for edge in self.edges]

    @property
    def args(self):
        return frozenset().union(*(edge.get_args() for edge in self.edges))

    def add_arg(self, param, value):
        for edge in self.edges:
            if isinstance(edge, ContEdge):
                edge.add_arg(param, value)

class Value:
    def __init__(self):
        self.forwarded = None

    def find(self):
        result = self
        while isinstance(result, Inst):
            if result.forwarded is None:
                return result
            result = result.forwarded
        return result

    def replace(self, value):
        print(f'replace {self} with {value}')
        self.find().forward(value)

    def forward(self, value):
        assert self.forwarded is None
        self.forwarded = value

    def name(self, names):
        return names[self]

    def iseffectful(self):
        return False

class Inst(Value):
    __match_args__ = ("opcode", "args")

    def __init__(self, opcode, args):
        super().__init__()
        self.opcode = opcode
        self._args = args

    def arg(self, i):
        return self._args[i].find()

    @property
    def args(self):
        for i in range(len(self._args)):
            yield self.arg(i)

    def __getattribute__(self, name):
        if name.startswith('arg_'):
            try:
                index = int(name[4:])
            except ValueError:
                return super().__getattribute__(name)
            try:
                return self.arg(index)
            except IndexError:
                return super().__getattribute__(name)
        return super().__getattribute__(name)

    def debug(self, names, end='\n', file=None):
        parts = [str(self.opcode.name)]
        for arg in self.args:
            parts.append(arg.name(names))
        if self.output:
            name = self.name(names)
            print(f'\t{name} = ' + ' '.join(parts), end=end, file=file)
        else:
            print(f'\t' + ' '.join(parts), end=end, file=file)

    def iseffectful(self):
        return True

class Param(Value):
    assignable = True

    def __init__(self, block):
        super().__init__()
        self.block = block

    def __repr__(self):
        return f'Param({self.block.label})'

    def __str__(self):
        return f'@{self.block.label}'

class Names:
    def __init__(self, prefix='v'):
        self.prefix = prefix
        self.dict = {}
        self.counter = itertools.count(1)

    def __getitem__(self, key):
        if key not in self.dict:
            self.dict[key] = 'v' + str(next(self.counter))
        return self.dict[key]

class Block:
    anon_labels = (f'b{i}' for i in itertools.count(1))
    anon_params = (f'p{i}' for i in itertools.count(1))

    def __init__(self, label=None):
        self.insts = []
        if label is None:
            label = next(self.anon_labels)
        self.label = label
        self.cont = None
        self.preds = []
        self.succs = []
        self.params = []

    def emit_before(self, inst, insts):
        index = self.insts.index(inst)
        self.insts[index:index] = insts

    def emit(self, inst):
        self.insts.append(inst)
        return inst

    def param(self):
        param = Param(self)
        self.params.append(param)
        return param

    def add_arg(self, param, value):
        self.cont.add_arg(param, value)

class Procedure:
    def __init__(self, label, blocks, procedures):
        self.label = label
        self.blocks = blocks
        self.procedures = procedures

    def debug(self, names=None, end='\n', file=None):
        for proc in self.procedures:
            proc.debug(names, end, file)
        if names is None:
            names = Names()
        print(self.label + ':', end=end, file=file)
        for block in self.blocks:
            params = ', '.join(param.label for param in block.params)
            if params:
                print(f'{block.label}({params}):', end=end, file=file)
            else:
                print(f'{block.label}:', end=end, file=file)
            for inst in block.insts:
                inst.debug(names, end=end, file=file)
            if block.cont is not None:
                block.cont.debug(names, end=end, file=file)
            else:
                print('\tNo jump', end=end, file=file)
