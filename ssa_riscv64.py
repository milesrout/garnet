import enum
import ssa
from ssa import ContEdge, Block, Procedure
from riscv64 import Opcode

class Value:
    pass

class Zero(Value):
    def __str__(self):
        return 'x0'

    def debug(self, names, end='\n', file=None):
        print(self, end=end, file=file)

class Imm(Value):
    __match_args__ = ('imm',)
    def __init__(self, imm, display=None):
        self.imm = imm
        if display is None:
            display = str
        self.display = display

    def name(self, names):
        return str(self)

    def __str__(self):
        return self.display(self.imm)

    def __repr__(self):
        return f'Imm({self.imm})'

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.imm == other.imm)

    def __hash__(self):
        return hash((Imm, self.imm))

class Sym(Value):
    __match_args__ = ('sym',)
    def __init__(self, sym):
        self.sym = sym

    def name(self, names):
        return self.sym

    def __repr__(self):
        return f'Sym({self.sym})'

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.sym == other.sym)

    def __hash__(self):
        return hash((Sym, self.sym))

class PseudoOpcode(enum.Enum):
    # pseudo
    CONST = enum.auto()
    FUNC = enum.auto()
    PARAM = enum.auto()
    CALL = enum.auto()

class Inst:
    def __init__(self, opcode, args):
        self.opcode = opcode
        self.args = args

    @property
    def output(self):
        return self.opcode not in {Opcode.NOP, Opcode.SD, Opcode.SW, Opcode.SH,
                                   Opcode.SB, PseudoOpcode.CALL}

    def __str__(self):
        args = ', '.join(map(str, self.args))
        return f'{self.opcode.name}({args})'

    def __repr__(self):
        args = ', '.join(map(str, self.args))
        return f'Inst({self.opcode}, {self.args})'

    def debug(self, names, end='\n', file=None):
        parts = []
        for arg in self.args:
            if isinstance(arg, Inst):
                parts.append(names[arg])
            elif isinstance(arg, ssa.Param):
                parts.append(arg.label)
            elif isinstance(arg, Block):
                parts.append(arg.name)
            elif isinstance(arg, Imm):
                parts.append(str(arg))
            elif isinstance(arg, Sym):
                parts.append(str(arg.sym))
            else:
                raise RuntimeError(f'Invalid arg {type(arg)}')
        if self.output:
            print(f'\t{names[self]} = ', end='', file=file)
        else:
            print('\t', end='', file=file)
        print(f'{self.opcode.name.upper()} ' + ','.join(parts), end=end, file=file)

    @staticmethod
    def const(const):
        return ConstInst(const)

    @staticmethod
    def func(func):
        return FuncInst(func)

    @staticmethod
    def param(param):
        return ParamInst(param)

    @staticmethod
    def nullary(op):
        return Inst(op, ())

    @staticmethod
    def unary(op, v):
        return Inst(op, (v,))

    @staticmethod
    def binary(op, v1, v2):
        return Inst(op, (v1, v2))

class ConstInst(Inst):
    def __init__(self, const):
        super().__init__(PseudoOpcode.CONST, ())
        self.const = const

    def __str__(self):
        return f'{self.opcode.name}({self.const})'#str(self.const)

    def __repr__(self):
        return f'ConstInst({self.opcode}, {self.const})'

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print(str(self.const), end=end, file=file)

class FuncInst(Inst):
    def __init__(self, func):
        super().__init__(PseudoOpcode.FUNC, ())
        self.func = func

    def __str__(self):
        return f'{self.opcode.name}({self.func})'

    def __repr__(self):
        return f'FuncInst({self.opcode}, {self.func})'

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print(str(self.func), end=end, file=file)

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

    @staticmethod
    def call(value, then):
        ethen = ContEdge(then)
        return CallCont(value, then)

    @property
    def uses(self):
        return frozenset()

    @property
    def targets(self):
        return [edge.target for edge in self.edges]

    @property
    def args(self):
        return frozenset().union(*(edge.get_args() for edge in self.edges))

    def add_arg(self, param, pvalue, avalue):
        for edge in self.edges:
            if isinstance(edge, ContEdge):
                edge.add_arg(param, pvalue, avalue)

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
        if isinstance(self.value, ssa.Param):
            print('\tBRANCH ' + self.value.label, end=' ', file=file)
        else:
            print('\tBRANCH ' + names[self.value], end=' ', file=file)
        self.ttrue.debug(names=names, end=' ', file=file)
        self.tfals.debug(names=names, end=end, file=file)

class CallCont(Cont):
    def __init__(self, value, target):
        self.value = value
        self.target = target

    @property
    def edges(self):
        return [self.target]

    @property
    def uses(self):
        return frozenset({self.value})

    def debug(self, names=None, end='\n', file=None):
        print('\tCALL ' + self.value.name(names), end=' ', file=file)
        self.target.debug(names=names, end=end, file=file)
