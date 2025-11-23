import enum
import itertools
import unittest

class ContinuationType(enum.Enum):
    JUMP = enum.auto()
    BRANCH = enum.auto()
    RETURN = enum.auto()

class ContinuationEdge:
    def __init__(self, target):
        self.target = target
        self.args = {}

    def add_arg(self, param, pvalue, avalue):
        if pvalue.block != self.target:
            return
        self.args[param] = avalue

class Continuation:
    def __init__(self, type, args):
        self.type = type
        self.args = args

    @staticmethod
    def ret():
        return Continuation(ContinuationType.RETURN, ())

    @staticmethod
    def jump(block):
        eblock = ContinuationEdge(block)
        return Continuation(ContinuationType.JUMP, (eblock,))

    @staticmethod
    def branch(value, then, alt):
        ethen = ContinuationEdge(then)
        ealt = ContinuationEdge(alt)
        return Continuation(ContinuationType.BRANCH, (value, ethen, ealt))

    def add_arg(self, param, pvalue, avalue):
        for arg in self.args:
            if isinstance(arg, ContinuationEdge):
                arg.add_arg(param, pvalue, avalue)

    def debug(self, names=None, end='\n', file=None):
        parts = [str(self.type.name)]
        for arg in self.args:
            if isinstance(arg, ContinuationEdge):
                if arg.args:
                    params = (a.name + ':' + v.name(names) for a, v in arg.args.items())
                    parts.append(arg.target.name + '(' + ', '.join(params) + ')')
                else:
                    parts.append(arg.target.name)
            elif isinstance(arg, Value) and names is not None:
                parts.append(arg.name(names))
            else:
                parts.append(str(arg))
        print('\t' + ' '.join(parts), end=end, file=file)

class Opcode(enum.Enum):
    NOP = enum.auto()
    CONST = enum.auto()
    PARAM = enum.auto()
    STORE = enum.auto()
    LOAD = enum.auto()
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
        parts = [str(self.opcode.name)]
        for arg in self.args:
            if isinstance(arg, Value):
                parts.append(arg.name(names))
            elif isinstance(arg, Block):
                parts.append(arg.name)
            else:
                raise RuntimeError
        name = names[self]
        print(f'\t{name} = ' + ' '.join(parts), end=end, file=file)

    @staticmethod
    def const(const):
        return ConstInst(const)

    @staticmethod
    def param(param):
        return ParamInst(param)

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
    pass

class InstValue(Value):
    def __init__(self, block, index):
        self.block = block
        self.index = index

    def name(self, names):
        return names[self.block, self.index]

    def __str__(self):
        return f'{{{self.block.name}:{self.index}}}'

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.block == other.block and
                self.index == other.index)

    def __hash__(self):
        return hash((InstValue, self.block, self.index))

class ParamValue(Value):
    def __init__(self, block, param):
        self.block = block
        self.param = param

    def name(self, names):
        return self.param.name

    def __str__(self):
        return f'{{{self.block.name}:{self.param.name}}}'

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.block == other.block and
                self.param == other.param)

    def __hash__(self):
        return hash((ParamValue, self.block, self.param))

class ConstInst(Inst):
    def __init__(self, const):
        super().__init__(Opcode.CONST, ())
        self.const = const

    def __str__(self):
        return f'{self.opcode.name} {self.const}'

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print(str(self.const), end=end, file=file)

class ParamInst(Inst):
    def __init__(self, param):
        super().__init__(Opcode.PARAM, ())
        self.param = param

    def __str__(self):
        return super().__str__() + ' ~' + str(self.param)

    def debug(self, names, end='\n', file=None):
        super().debug(names, end=' ', file=file)
        print('~' + self.param.name, end=end, file=file)

class StoreInst(Inst):
    def __init__(self, variable, value):
        super().__init__(Opcode.STORE, (value,))
        self.variable = variable

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

class Param:
    def __init__(self, name):
        self.name = name

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
        self.params = set()

    def emit(self, inst):
        self.insts.append(inst)
        return InstValue(self, len(self.insts) - 1)

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

    def param(self, variable):
        param = Param(next(self.anon_params))
        self.params.add(param)
        return param, ParamValue(self, param)

    def add_arg(self, param, pvalue, avalue):
        self.cont.add_arg(param, pvalue, avalue)

    def debug(self, end='\n', file=None):
        params = ', '.join(param.name for param in self.params)
        print(f'{self.name}({params}):', end=end, file=file)
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
            params = ', '.join(param.name for param in block.params)
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
