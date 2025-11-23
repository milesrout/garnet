import enum
import itertools
import unittest

ABBREVIATE_PHI_EPSILON = False

class Opcode(enum.Enum):
    NOP = enum.auto()
    VALUE = enum.auto()
    PHI = enum.auto()
    UPSILON = enum.auto()
    STORE_GLOBAL = enum.auto()
    LOAD_GLOBAL = enum.auto()
    PRINT = enum.auto()
    SCAN = enum.auto()
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

class ContinuationType(enum.Enum):
    JUMP = enum.auto()
    BRANCH = enum.auto()
    RETURN = enum.auto()

class Continuation:
    def __init__(self, type, args):
        self.type = type
        self.args = args

    @staticmethod
    def ret():
        return Continuation(ContinuationType.RETURN, ())

    @staticmethod
    def jump(block):
        return Continuation(ContinuationType.JUMP, (block,))

    @staticmethod
    def branch(value, then, alt):
        return Continuation(ContinuationType.BRANCH, (value, then, alt))

    def debug(self, names=None, end='\n', file=None):
        parts = [str(self.type.name)]
        for arg in self.args:
            if isinstance(arg, Block):
                parts.append(arg.name)
            elif isinstance(arg, Value) and names is not None:
                parts.append(names[arg.block, arg.index])
            else:
                parts.append(str(arg))
        print('\t' + ' '.join(parts), end=end, file=file)

class Type(enum.Enum):
    VOID = enum.auto()
    INT = enum.auto()

class Inst:
    def __init__(self, opcode, args):
        self.opcode = opcode
        self.args = args

    def __str__(self):
        parts = [str(self.opcode.name)]
        for arg in self.args:
            parts.append(str(arg))
        return ' '.join(parts)

    def debug(self, names, end='\n', file=None):
        if self.opcode is Opcode.PHI and ABBREVIATE_PHI_EPSILON:
            name = names[self]
            print(f'\t{name} = ^{name}', file=file, end=end)
            return
        parts = [str(self.opcode.name)]
        for arg in self.args:
            if isinstance(arg, Value):
                parts.append(names[arg.block, arg.index])
            elif isinstance(arg, Block):
                parts.append(arg.name)
            else:
                raise RuntimeError
        name = names[self]
        print(f'\t{name} = ' + ' '.join(parts), end=end, file=file)

    @staticmethod
    def value(imm):
        return ValueInst(imm)

    @staticmethod
    def upsilon(phi, value):
        return UpsilonInst(phi, value)

    @staticmethod
    def store_global(variable, value):
        return StoreGlobalInst(variable, value)

    @staticmethod
    def load_global(variable):
        return LoadGlobalInst(variable)

    @staticmethod
    def call(procedure):
        return CallInst(procedure)

    @staticmethod
    def nop():
        return Inst(Opcode.NOP, ())

    @staticmethod
    def phi():
        return Inst(Opcode.PHI, ())

    @staticmethod
    def print(value):
        return Inst(Opcode.PRINT, (value,))

    @staticmethod
    def scan():
        return Inst(Opcode.SCAN, ())

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

class Value:
    def __init__(self, block, index):
        self.block = block
        self.index = index

    def __str__(self):
        return f'{{{self.block.name}:{self.index}}}'

    def __eq__(self, other):
        return self.block == other.block and self.index == other.index

    def __hash__(self):
        return hash((Value, self.block, self.index))

class ValueInst(Inst):
    def __init__(self, imm):
        super().__init__(Opcode.VALUE, ())
        self.imm = imm

    def __str__(self):
        return f'{self.opcode.name} {self.imm}'

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print(str(self.imm), end=end, file=file)

class UpsilonInst(Inst):
    def __init__(self, phi, value):
        super().__init__(Opcode.UPSILON, (value,))
        self.phi = phi

    def __str__(self):
        return super().__str__() + ' ^' + str(self.phi)

    def debug(self, names, end='\n', file=None):
        phi_name = names[self.phi.block, self.phi.index]
        if ABBREVIATE_PHI_EPSILON:
            val_name = names[self.args[0].block, self.args[0].index]
            print(f'\t^{phi_name} = {val_name}', end=end, file=file)
        else:
            super().debug(names, end=' ', file=file)
            print('^' + phi_name, end=end, file=file)

class StoreGlobalInst(Inst):
    def __init__(self, variable, value):
        super().__init__(Opcode.STORE_GLOBAL, (value,))
        self.variable = variable

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print('%' + str(self.variable), end=end, file=file)

class LoadGlobalInst(Inst):
    def __init__(self, variable):
        super().__init__(Opcode.LOAD_GLOBAL, ())
        self.variable = variable

    def __str__(self):
        return super().__str__() + ' $' + str(self.variable)

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print('%' + str(self.variable), end=end, file=file)

class CallInst(Inst):
    def __init__(self, procedure):
        super().__init__(Opcode.CALL, ())
        self.procedure = procedure

    def __str__(self):
        return super().__str__() + ' @' + str(self.procedure)

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print('@' + str(self.procedure), end=end, file=file)

class Block:
    anon_names = (f'b{i}' for i in itertools.count(1))
    def __init__(self, name=None):
        self.insts = []
        if name is None:
            name = next(Block.anon_names)
        self.name = name
        self.cont = None
        self.preds = set()

    def emit(self, inst):
        self.insts.append(inst)
        return Value(self, len(self.insts) - 1)

    def ret(self):
        assert self.cont is None or self.cont.type is ContinuationType.RETURN
        self.cont = Continuation.ret()

    def jump(self, target):
        assert self.cont is None
        self.cont = Continuation.jump(target)
        target.preds.add(self)

    def branch(self, value, then, alt):
        assert self.cont is None
        self.cont = Continuation.branch(value, then, alt)
        then.preds.add(self)
        alt.preds.add(self)

    def debug(self, end='\n', file=None):
        print(self.name, end=':'+end, file=file)
        for i, inst in enumerate(self.insts):
            print(f'\t{i}:  {inst}', end=end, file=file)
        if self.cont is not None:
            self.cont.debug(end=end, file=file)
        else:
            print('\tNo jump', end=end, file=file)

class Procedure:
    def __init__(self, blocks, procedures):
        self.blocks = blocks
        self.procedures = procedures

    def debug(self, end='\n', file=None):
        names = {}
        counter = itertools.count(1)
        for block in self.blocks:
            for i, inst in enumerate(block.insts):
                if inst not in names:
                    names[inst] = names[block, i] = 'v' + str(next(counter))
        for block in self.blocks:
            print(f'{block.name}:', end=end, file=file)
            for inst in block.insts:
                inst.debug(names, end=end, file=file)
            if block.cont is not None:
                block.cont.debug(names, end=end, file=file)
            else:
                print('\tNo jump', end=end, file=file)

class TestSsa(unittest.TestCase):
    def test_ssa(self):
        b1 = Block()
        b1.insts.append(Inst.nop())
        b1.insts.append(Inst.value(1))
        b1.insts.append(Inst.phi())
        b1.insts.append(Inst.upsilon(Value(b1,2), Value(b1,1)))
        b1.insts.append(Inst.add(Value(b1,1), Value(b1,1)))
        b1.ret()
