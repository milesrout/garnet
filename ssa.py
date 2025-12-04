import enum
import itertools
import unittest

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
            print(self.target.name, end='(', file=file)
            for a, v in self.args.items():
                print(a.label, end='=', file=file)
                if isinstance(v, Param):
                    print(v.label, end=', ', file=file)
                else:
                    print(names[v], end=', ', file=file)
            print(')', end=end, file=file)
        else:
            print(self.target.name, end=end, file=file)
        #if self.args:
        #    for a, v in self.args.items():
        #        print(type(a), a)
        #        print(type(v), v)
        #        print(v.name(names))
        #    args = (a.label + '=' + v.name(names) for a, v in self.args.items())
        #    print(self.target.name + '(' + ', '.join(args) + ')', end=end, file=file)
        #else:
        #    print(self.target.name, end=end, file=file)

class Cont:
    @staticmethod
    def ret():
        return ReturnCont()

    @staticmethod
    def jump(block):
        eblock = ContEdge(block)
        return JumpCont(eblock)

    @staticmethod
    def branch(value, then, alt):
        ethen = ContEdge(then)
        ealt = ContEdge(alt)
        return BranchCont(value, ethen, ealt)

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

class ReturnCont(Cont):
    @property
    def edges(self):
        return []

    def debug(self, names=None, end='\n', file=None):
        print('\tRETURN', end=end, file=file)

class JumpCont(Cont):
    def __init__(self, target):
        self.target = target

    @property
    def edges(self):
        return [self.target]

    def debug(self, names=None, end='\n', file=None):
        print('\tJUMP', end=' ', file=file)
        self.target.debug(names=names, end=end, file=file)

class BranchCont(Cont):
    def __init__(self, value, ttrue, tfals):
        self.value = value
        self.ttrue = ttrue
        self.tfals = tfals

    @property
    def edges(self):
        return [self.ttrue, self.tfals]

    @property
    def uses(self):
        return frozenset({self.value})

    def debug(self, names=None, end='\n', file=None):
        if isinstance(self.value, Param):
            print('\tBRANCH ' + self.value.label, end=' ', file=file)
        else:
            print('\tBRANCH ' + names[self.value], end=' ', file=file)
        self.ttrue.debug(names=names, end=' ', file=file)
        self.tfals.debug(names=names, end=end, file=file)

class Type(enum.Enum):
    VOID = enum.auto()
    INT = enum.auto()

class Opcode(enum.Enum):
    NOP = enum.auto()
    CONST = enum.auto()
    STORE = enum.auto()
    LOAD = enum.auto()
    CALL = enum.auto()
    ODD = enum.auto()
    ADD = enum.auto()
    SUB = enum.auto()
    MUL = enum.auto()
    DIV = enum.auto()
    SLT = enum.auto()
    SGT = enum.auto()
    SLE = enum.auto()
    SGE = enum.auto()
    SEQ = enum.auto()
    SNE = enum.auto()
    NEG = enum.auto()

OPCODE0 = [
    Opcode.NOP,
]
OPCODE1 = [
    Opcode.ODD,
    Opcode.NEG,
]
OPCODE2 = [
    Opcode.ADD,
    Opcode.SUB,
    Opcode.MUL,
    Opcode.DIV,
    Opcode.SLT,
    Opcode.SGT,
    Opcode.SLE,
    Opcode.SGE,
    Opcode.SEQ,
    Opcode.SNE,
]
OPCODE_MATCH = {
    Opcode.CONST: ('const',),
    Opcode.STORE: ('arg0', 'variable'),
    Opcode.LOAD: ('variable',),
    Opcode.CALL: ('procedure',),
}
for op in OPCODE0:
    OPCODE_MATCH[op] = ()
for op in OPCODE1:
    OPCODE_MATCH[op] = ('arg0',)
for op in OPCODE2:
    OPCODE_MATCH[op] = ('arg0', 'arg1')

class InstMeta(type):
    def __instancecheck__(cls, inst):
        return (type.__instancecheck__(cls, inst) or
                (isinstance(inst, Inst) and inst.opcode.name.lower() == cls.__name__.lower()))

for op, match in OPCODE_MATCH.items():
    globals()[op.name.title()] = InstMeta(
        op.name.title(), (),
        {'__match_args__': match})

class Const(metaclass=InstMeta):
    __match_args__ = ("const",)

class Inst:
    __match_args__ = ("opcode", "args")

    def __init__(self, opcode, args):
        self.opcode = opcode
        self.args = args

    @property
    def arg0(self):
        return self.args[0]

    @property
    def arg1(self):
        return self.args[1]

    @property
    def output(self):
        return self.opcode not in {Opcode.NOP, Opcode.CALL, Opcode.STORE}

    def __str__(self):
        parts = [str(self.opcode.name)]
        for arg in self.args:
            parts.append(str(arg))
        return ' '.join(parts)

    def name(self, names):
        return names[self]

    def iseffectful(self):
        return self.opcode in [
            Opcode.STORE,
            Opcode.CALL,
        ]

    def debug(self, names, end='\n', file=None):
        parts = [str(self.opcode.name)]
        for arg in self.args:
            if isinstance(arg, Inst):
                parts.append(names[arg])
            elif isinstance(arg, Param):
                parts.append(arg.label)
            elif isinstance(arg, Block):
                parts.append(arg.name)
            else:
                raise RuntimeError
        if self.output:
            name = names[self]
            print(f'\t{name} = ' + ' '.join(parts), end=end, file=file)
        else:
            print(f'\t' + ' '.join(parts), end=end, file=file)

    @staticmethod
    def const(const):
        return ConstInst(const)

    @staticmethod
    def store(variable, value):
        return StoreInst(variable, value)

    @staticmethod
    def load(variable):
        return LoadInst(variable)

    @staticmethod
    def call(procedure):
        return CallInst(procedure)

    @staticmethod
    def nop():
        return Inst(Opcode.NOP, ())

    @staticmethod
    def unary(op, value):
        return Inst(op, (value,))

    @staticmethod
    def binary(op, lhs, rhs):
        return Inst(op, (lhs, rhs))

    @staticmethod
    def add(lhs, rhs):
        return Inst(Opcode.ADD, (lhs, rhs))

    @staticmethod
    def sub(lhs, rhs):
        return Inst(Opcode.SUB, (lhs, rhs))

    @staticmethod
    def mul(lhs, rhs):
        return Inst(Opcode.MUL, (lhs, rhs))

class ConstInst(Inst):
    def __init__(self, const):
        super().__init__(Opcode.CONST, ())
        self.const = const

    def __str__(self):
        return f'{self.opcode.name} {self.const}'

    def iseffectful(self):
        return False

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print(str(self.const), end=end, file=file)

class StoreInst(Inst):
    def __init__(self, variable, value):
        super().__init__(Opcode.STORE, (value,))
        self.variable = variable

    @property
    def output(self):
        return False

    def iseffectful(self):
        return True

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print('%' + str(self.variable), end=end, file=file)

class LoadInst(Inst):
    def __init__(self, variable):
        super().__init__(Opcode.LOAD, ())
        self.variable = variable

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def iseffectful(self):
        return False

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print('%' + str(self.variable), end=end, file=file)

class CallInst(Inst):
    def __init__(self, procedure):
        super().__init__(Opcode.CALL, ())
        self.procedure = procedure

    @property
    def output(self):
        return False

    def iseffectful(self):
        return True

    def __str__(self):
        return super().__str__() + ' @' + str(self.procedure)

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print('@' + str(self.procedure), end=end, file=file)

class Param:
    assignable = False

    def __init__(self, label):
        self.label = label

    def name(self, names):
        return self.label

    def __str__(self):
        return self.label

    def __repr__(self):
        return f'Param({self.label})'

    def iseffectful(self):
        return False

class Block:
    anon_names = (f'b{i}' for i in itertools.count(1))
    anon_params = (f'p{i}' for i in itertools.count(1))
    def __init__(self, name=None):
        self.insts = []
        if name is None:
            name = next(self.anon_names)
        self.name = name
        self.cont = None
        self.preds = set()
        self.params = []

    def emit(self, inst):
        self.insts.append(inst)
        return inst

    def ret(self):
        assert self.cont is None
        self.cont = Cont.ret()

    def jump(self, target):
        assert self.cont is None
        self.cont = Cont.jump(target)
        target.preds.add(self)

    def branch(self, value, then, alt):
        assert self.cont is None
        self.cont = Cont.branch(value, then, alt)
        then.preds.add(self)
        alt.preds.add(self)

    def param(self):
        param = Param(next(self.anon_params))
        self.params.append(param)
        param.block = self
        return param

    def add_arg(self, param, value):
        self.cont.add_arg(param, value)

class Names:
    def __init__(self, prefix='v'):
        self.prefix = prefix
        self.dict = {}
        self.counter = itertools.count(1)

    def __getitem__(self, key):
        if key not in self.dict:
            self.dict[key] = 'v' + str(next(self.counter))
        return self.dict[key]

class Procedure:
    def __init__(self, name, blocks, procedures):
        self.name = name
        self.blocks = blocks
        self.procedures = procedures

    def debug(self, names=None, end='\n', file=None):
        for proc in self.procedures:
            proc.debug(names, end, file)
        if names is None:
            names = Names()
        print(self.name + ':', end=end, file=file)
        for block in self.blocks:
            params = ', '.join(param.label for param in block.params)
            if params:
                print(f'{block.name}({params}):', end=end, file=file)
            else:
                print(f'{block.name}:', end=end, file=file)
            for inst in block.insts:
                inst.debug(names, end=end, file=file)
            if block.cont is not None:
                block.cont.debug(names, end=end, file=file)
            else:
                print('\tNo jump', end=end, file=file)
