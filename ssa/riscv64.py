import abc
import enum
import ssa
from ssa import ContEdge, Procedure
from riscv64 import Opcode, Register

__names__ = [
    'Value', 'Reg', 'Zero', 'Imm', 'Sym',
    'Inst',
    'Cont',
    'Block',
]

class Value(ssa.Value, abc.ABC):
    @abc.abstractmethod
    def debug(self, names, end='\n'):
        print(self, end=end)

class SimpleValue(Value):
    def name(self, names):
        return str(self)

    def debug(self, names, end='\n'):
        print(self, end=end)

class Off(SimpleValue):
    assignable = False

    def __init__(self, reg, off):
        self.reg = reg
        self.off = off

    def __str__(self):
        return f'{self.off}({self.reg})'

    def name(self, names):
        off = self.off.name(names)
        reg = self.reg.name(names)
        return f'{off}({reg})'

class Reg(SimpleValue):
    assignable = True

    def __init__(self, reg):
        self.reg = reg

    def __repr__(self):
        return f'Reg({self.reg.name})'

    def __str__(self):
        return self.reg.name.lower()

class Zero(SimpleValue):
    assignable = False

    def __str__(self):
        return 'x0'

class Imm(SimpleValue):
    __match_args__ = ('imm',)
    assignable = False

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

class Sym(SimpleValue):
    __match_args__ = ('sym',)
    assignable = False

    def __init__(self, sym):
        self.sym = sym

    def __str__(self):
        return self.sym

    def __repr__(self):
        return f'Sym({self.sym})'

class PseudoOpcode(enum.Enum):
    # pseudo
    CONST = enum.auto()
    FUNC = enum.auto()
    PARAM = enum.auto()
    CALL = enum.auto()

class Inst(ssa.Inst, Value):
    assignable = True

    def __init__(self, opcode, args):
        super().__init__(opcode, args)

    @property
    def output(self):
        return self.opcode not in {
                Opcode.NOP, Opcode.SD, Opcode.SW, Opcode.SH,
                Opcode.SB, Opcode.MV, PseudoOpcode.CALL}

    def __str__(self):
        args = ', '.join(map(str, self.args))
        return f'{self.opcode.name}({args})'

    def __repr__(self):
        args = ', '.join(map(str, self.args))
        return f'Inst({self.opcode}, {self.args})'

    def debug(self, names, end='\n'):
        parts = []
        for arg in self.args:
            parts.append(arg.name(names))
        if 0:
            if self.output:
                name = self.name(names)
                print(f'\t{name} = ', end='')
            else:
                print('\t', end='')
            print(f'{self.opcode.name.upper()} ' + ','.join(parts), end=end)
        else:
            print('\t', end='')
            print(self.opcode.name.lower(), end=' ')
            if self.output:
                print(self.name(names), end=',')
            print(','.join(parts), end=end)

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
        return f'{self.opcode.name}({self.const})'

    def __repr__(self):
        return f'ConstInst({self.opcode}, {self.const})'

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print(str(self.const), end=end)

class FuncInst(Inst):
    def __init__(self, func):
        super().__init__(PseudoOpcode.FUNC, ())
        self.func = func

    def __str__(self):
        return f'{self.opcode.name}({self.func})'

    def __repr__(self):
        return f'FuncInst({self.opcode}, {self.func})'

    def debug(self, names, end='\n'):
        super().debug(names, end=' ')
        print(str(self.func), end=end)

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
    def call(proc, params, then):
        ethen = ContEdge(then)
        return CallCont(proc, params, ethen)

class ReturnCont(Cont):
    @property
    def edges(self):
        return []

    def debug(self, names, end='\n'):
        print('\treturn', end=end)

class JumpCont(Cont):
    def __init__(self, target):
        self.target = target

    @property
    def edges(self):
        return [self.target]

    def debug(self, names, end='\n'):
        print('\tjump', end=' ')
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

    def debug(self, names, end='\n'):
        print('\tbranch ' + self.value.name(names), end=' ')
        self.ttrue.debug(names=names, end=' ')
        self.tfals.debug(names=names, end=end)

class CallCont(Cont):
    def __init__(self, proc, params, then):
        self.proc = proc
        self.params = params
        self.then = then

    @property
    def edges(self):
        return [self.then]

    def debug(self, names, end='\n'):
        if len(self.params):
            print('\tcall ' + self.proc, end='(')
            for i, arg in enumerate(self.params):
                if i == len(self.params) - 1:
                    print(arg.name(names), end=') ')
                else:
                    print(arg.name(names), end=', ')
        else:
            print('\tcall ' + self.proc, end=' ')
        self.then.debug(names=names, end=end)

class Block(ssa.Block):
    pass
