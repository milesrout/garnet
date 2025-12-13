import enum
import itertools
import unittest

from ssa import ContEdge
import ssa

__names__ = [
    'Cont',
    'Type',
    'Opcode',
    'Inst',
    'Block',
]

class Block(ssa.Block):
    def __str__(self):
        return self.label

    def ret(self):
        assert self.cont is None
        self.cont = Cont.ret()
        assert self.cont is not None

    def jump(self, target):
        assert self.cont is None
        self.cont = Cont.jump(target)
        self.succs.append(target)
        target.preds.append(self)
        assert self.cont is not None

    def branch(self, value, then, alt):
        assert self.cont is None
        self.cont = Cont.branch(value, then, alt)
        self.succs.append(then)
        self.succs.append(alt)
        then.preds.append(self)
        alt.preds.append(self)
        assert self.cont is not None

    def call(self, proc, then):
        assert self.cont is None
        self.cont = Cont.call(proc, then)
        self.succs.append(then)
        then.preds.append(self)
        assert self.cont is not None

class Cont(ssa.Cont):
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

    @staticmethod
    def call(proc, then):
        ethen = ContEdge(then)
        return CallCont(proc, ethen)

class ReturnCont(Cont):
    @property
    def edges(self):
        return []

    def debug(self, names=None, end='\n'):
        print('\tRETURN', end=end)

class JumpCont(Cont):
    def __init__(self, target):
        self.target = target

    @property
    def edges(self):
        return [self.target]

    def debug(self, names=None, end='\n'):
        print('\tJUMP', end=' ')
        self.target.debug(names=names, end=end)

class CallCont(Cont):
    def __init__(self, proc, then):
        self.proc = proc
        self.then = then

    @property
    def edges(self):
        return [self.then]

    def debug(self, names=None, end='\n'):
        print('\tCALL', self.proc, end=' ')
        self.then.debug(names=names, end=end)

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
        print('\tBRANCH ' + self.value.name(names), end=' ', file=file)
        self.ttrue.debug(names=names, end=' ')
        self.tfals.debug(names=names, end=end)

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
    SRA = enum.auto()
    SRL = enum.auto()
    SLL = enum.auto()

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
    Opcode.SRA,
    Opcode.SRL,
    Opcode.SLL,
]
OPCODE_MATCH = {
    Opcode.CONST: ('const',),
    Opcode.STORE: ('arg_0', 'variable'),
    Opcode.LOAD: ('variable',),
    Opcode.CALL: ('procedure',),
}
for op in OPCODE0:
    OPCODE_MATCH[op] = ()
for op in OPCODE1:
    OPCODE_MATCH[op] = ('arg_0',)
for op in OPCODE2:
    OPCODE_MATCH[op] = ('arg_0', 'arg_1')

class InstMeta(type):
    def __instancecheck__(cls, inst):
        return (type.__instancecheck__(cls, inst) or
                (isinstance(inst, Inst) and inst.opcode.name.lower() == cls.__name__.lower()))

for op, match in OPCODE_MATCH.items():
    globals()[op.name.title()] = InstMeta(
        op.name.title(), (),
        {'__match_args__': match})
    __names__.append(op.name.title())

class Inst(ssa.Inst):
    @property
    def output(self):
        return self.opcode not in {Opcode.NOP, Opcode.CALL, Opcode.STORE}

    def __repr__(self):
        cls = self.__class__.__qualname__
        args = [str(self.opcode)]
        for arg in self.args:
            args.append(repr(arg))
        parts = ', '.join(args)
        return f'{cls}({parts})'

    def __str__(self):
        cls = self.__class__.__name__
        args = [self.opcode.name]
        for arg in self.args:
            args.append(str(arg))
        parts = ', '.join(args)
        return f'{cls}({parts})'

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

    def iseffectful(self):
        return False

class ConstInst(Inst):
    def __init__(self, const):
        super().__init__(Opcode.CONST, ())
        self.const = const

    def __repr__(self):
        return f'ConstInst({self.const})'

    def __str__(self):
        return str(self.const)

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print(str(self.const), end=end)

class StoreInst(Inst):
    def __init__(self, variable, value):
        super().__init__(Opcode.STORE, (value,))
        self.variable = variable

    @property
    def output(self):
        return False

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print('%' + str(self.variable), end=end)

    def iseffectful(self):
        return True

class LoadInst(Inst):
    def __init__(self, variable):
        super().__init__(Opcode.LOAD, ())
        self.variable = variable

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print('%' + str(self.variable), end=end)
