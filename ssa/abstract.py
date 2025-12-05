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
        if isinstance(self.value, ssa.Param):
            print('\tBRANCH ' + self.value.label, end=' ', file=file)
        else:
            print('\tBRANCH ' + names[self.value], end=' ')
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
    __names__.append(op.name.title())

class Inst(ssa.Inst):
    @property
    def output(self):
        return self.opcode not in {Opcode.NOP, Opcode.CALL, Opcode.STORE}

    def __str__(self):
        parts = [str(self.opcode.name)]
        for arg in self.args:
            parts.append(str(arg))
        return ' '.join(parts)

    def iseffectful(self):
        return self.opcode in [
            Opcode.STORE,
            Opcode.CALL,
        ]

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

    def iseffectful(self):
        return True

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print('%' + str(self.variable), end=end)

class LoadInst(Inst):
    def __init__(self, variable):
        super().__init__(Opcode.LOAD, ())
        self.variable = variable

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def iseffectful(self):
        return False

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print('%' + str(self.variable), end=end)

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

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print('@' + str(self.procedure), end=end)

class Block(ssa.Block):
    def ret(self):
        assert self.cont is None
        self.cont = Cont.ret()

    def jump(self, target):
        assert self.cont is None
        self.cont = Cont.jump(target)
        self.succs.append(target)
        target.preds.append(self)

    def branch(self, value, then, alt):
        assert self.cont is None
        self.cont = Cont.branch(value, then, alt)
        self.succs.append(then)
        self.succs.append(alt)
        then.preds.append(self)
        alt.preds.append(self)
