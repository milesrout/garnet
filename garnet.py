from copy import copy
import collections
import enum
import itertools
import unittest

import garnetast as ast
import parse

ABBREVIATE_PHI_EPSILON = True

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

    def debug(self, names=None):
        parts = [str(self.type.name)]
        for arg in self.args:
            if isinstance(arg, Block):
                parts.append(arg.name)
            elif isinstance(arg, Value) and names is not None:
                parts.append(names[arg.block, arg.index])
            else:
                parts.append(str(arg))
        print('\t' + ' '.join(parts))

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

    def debug(self, names, end='\n'):
        if self.opcode is Opcode.PHI and ABBREVIATE_PHI_EPSILON:
            name = names[self]
            print(f'\t{name} = ^{name}')
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
        print(f'\t{name} = ' + ' '.join(parts), end=end)

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

class ValueInst(Inst):
    def __init__(self, imm):
        super().__init__(Opcode.VALUE, ())
        self.imm = imm

    def __str__(self):
        return f'{self.opcode.name} {self.imm}'

    def debug(self, names):
        super().debug(names, end=' ')
        print(str(self.imm))

class UpsilonInst(Inst):
    def __init__(self, phi, value):
        super().__init__(Opcode.UPSILON, (value,))
        self.phi = phi

    def __str__(self):
        return super().__str__() + ' ^' + str(self.phi)

    def debug(self, names):
        phi_name = names[self.phi.block, self.phi.index]
        if ABBREVIATE_PHI_EPSILON:
            val_name = names[self.args[0].block, self.args[0].index]
            print(f'\t^{phi_name} = {val_name}')
        else:
            super().debug(names, end=' ')
            print('^' + phi_name)

class StoreGlobalInst(Inst):
    def __init__(self, variable, value):
        super().__init__(Opcode.STORE_GLOBAL, (value,))
        self.variable = variable

    def __str__(self):
        return super().__str__() + ' %' + str(self.variable)

    def debug(self, names):
        super().debug(names, end=' ')
        print('%' + str(self.variable))

class LoadGlobalInst(Inst):
    def __init__(self, variable):
        super().__init__(Opcode.LOAD_GLOBAL, ())
        self.variable = variable

    def __str__(self):
        return super().__str__() + ' $' + str(self.variable)

    def debug(self, names):
        super().debug(names, end=' ')
        print('%' + str(self.variable))

class CallInst(Inst):
    def __init__(self, procedure):
        super().__init__(Opcode.CALL, ())
        self.procedure = procedure

    def __str__(self):
        return super().__str__() + ' @' + str(self.procedure)

    def debug(self, names):
        super().debug(names, end=' ')
        print('@' + str(self.procedure))

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

    def debug(self):
        print(self.name, end=':\n')
        print(type(self.insts))
        for i, inst in enumerate(self.insts):
            print(f'\t{i}:  {inst}')
        if self.cont is not None:
            self.cont.debug()
        else:
            print('\tNo jump')

class Procedure:
    def __init__(self, blocks, variables):
        self.blocks = blocks
        self.variables = variables

    def debug(self):
        names = {}
        counter = itertools.count(1)
        for block in self.blocks:
            for i, inst in enumerate(block.insts):
                if inst not in names:
                    names[inst] = names[block, i] = 'v' + str(next(counter))
        for block in self.blocks:
            print(f'{block.name}:')
            for inst in block.insts:
                inst.debug(names)
            if block.cont is not None:
                block.cont.debug(names)
            else:
                print('\tNo jump')

class TestSsa(unittest.TestCase):
    def test_ssa(self):
        b1 = Block()
        b1.insts.append(Inst.nop())
        b1.insts.append(Inst.value(1))
        b1.insts.append(Inst.phi())
        b1.insts.append(Inst.upsilon(Value(b1,2), Value(b1,1)))
        b1.insts.append(Inst.add(Value(b1,1), Value(b1,1)))
        b1.ret()

class VariableChecker(ast.ExprVisitor):
    def __init__(self):
        self.free_variables = collections.defaultdict(set)
        self.escaped_variables = collections.defaultdict(set)
        self.const_decls = set()
        self.var_decls = set()
        self.local_decls = set()
        self.proc_decls = set()
        self.current_proc = None

    def visit_Decl(self, decl):
        old_const_decls = copy(self.const_decls)
        old_var_decls = copy(self.var_decls)
        old_proc_decls = copy(self.proc_decls)
        old_current_proc = self.current_proc
        self.current_proc = decl

        for ident, number in decl.const_decls:
            self.const_decls.add(ident)
        for ident in decl.var_decls:
            self.var_decls.add(ident)
            self.local_decls.add(ident)

        escaped_variables = set()
        for ident, decl1 in decl.proc_decls:
            self.proc_decls.add(ident)

            old_local_decls = copy(self.local_decls)
            self.local_decls = set()
            self.visit(decl1)
            escaped_variables.update(self.free_variables[decl1])
            self.local_decls = old_local_decls

        self.escaped_variables[decl] = escaped_variables
        self.visit(decl.stmt)

        self.current_proc = old_current_proc
        self.const_decls = old_const_decls
        self.var_decls = old_var_decls
        self.proc_decls = old_proc_decls

    def check_writable(self, ident):
        if ident in self.const_decls:
            raise RuntimeError(f'Syntax error: cannot write to const {ident}')
        if ident in self.local_decls:
            return
        if ident in self.var_decls:
            self.free_variables[self.current_proc].add(ident)
            return
        if ident in self.proc_decls:
            raise RuntimeError(f'Syntax error: cannot use procedure as variable: {ident}')
        raise RuntimeError(f'Syntax error: no such variable {ident}')

    def check_readable(self, ident):
        if ident in self.const_decls:
            return
        if ident in self.local_decls:
            return
        if ident in self.var_decls:
            self.free_variables[self.current_proc].add(ident)
            return
        if ident in self.proc_decls:
            raise RuntimeError(f'Syntax error: cannot use procedure as variable: {ident}')
        raise RuntimeError(f'Syntax error: no such variable {ident}')

    def check_callable(self, ident):
        if ident in self.proc_decls:
            return
        if (ident in self.const_decls or
                ident in self.local_decls or
                ident in self.var_decls):
            raise RuntimeError(f'Syntax error: cannot call non-procedure variable {ident}')
        raise RuntimeError(f'Syntax error: no such procedure {ident}')

    def visit_ReadStmt(self, stmt):
        self.check_writable(stmt.ident)

    def visit_AssignStmt(self, stmt):
        self.check_writable(stmt.ident)
        self.visit(stmt.expr)

    def visit_CallStmt(self, stmt):
        self.check_callable(stmt.ident)

    def visit_IdentExpr(self, expr):
        self.check_readable(expr.ident)

class SsaConverter(ast.Visitor):
    def __init__(self, constants, free_variables, escaped_variables):
        self.constants = constants
        self.free_variables = free_variables
        self.escaped_variables = escaped_variables

        self.current_def = collections.defaultdict(dict)
        self.incomplete_phis = collections.defaultdict(dict)
        self.blocks = []
        self.sealed_blocks = set()
        self.procedures = {}
        self.current_proc = None

    def write_variable(self, variable, block, value):
        self.current_def[variable][block] = value

    def read_variable(self, variable, block):
        if block in self.current_def[variable]:
            return self.current_def[variable][block]
        return self.read_variable_recursive(variable, block)

    def read_variable_recursive(self, variable, block):
        if block not in self.sealed_blocks:
            value = block.emit(Inst.phi())
            self.incomplete_phis[block][variable] = value
        elif len(block.preds) == 1:
            pred = next(iter(block.preds))
            value = self.read_variable(variable, pred)
        else:
            value = block.emit(Inst.phi())
            self.set_variable(variable, block, value)
            self.add_phi_operands(variable, value)
        self.write_variable(variable, block, value)
        return value

    def emit_upsilon(self, variable, block, phi):
        if block in self.current_def[variable]:
            block.emit(Inst.upsilon(phi, self.current_def[variable][block]))

    def add_phi_operands(self, variable, phi):
        for pred in phi.block.preds:
            self.emit_upsilon(variable, pred, phi)

    def seal_block(self, block):
        for variable, phi in self.incomplete_phis[block].items():
            self.add_phi_operands(variable, phi)
        self.sealed_blocks.add(block)

    def new_block(self):
        block = Block()
        self.blocks.append(block)
        return block

    def finish(self):
        proc = Procedure(self.blocks, set())
        return proc

    def convert(self, prog):
        block = self.new_block()
        self.seal_block(block)
        blockend = self.visit(prog, block)
        blockend.ret()
        return Procedure(self.blocks, set())

    ####

    def visit_Decl(self, decl, block):
        old_current_proc = self.current_proc
        self.current_proc = decl

        for ident, decl1 in decl.proc_decls:
            converter = SsaConverter(self.constants, self.free_variables, self.escaped_variables)
            self.procedures[ident] = converter.convert(decl1)

        for ident, number in self.constants:
            value = block.emit(Inst.value(number))
            self.write_variable(ident, block, value)

        block = self.visit(decl.stmt, block)
        self.current_proc = old_current_proc
        return block

    def get_variable(self, ident, block):
        if ident in self.free_variables[self.current_proc]:
            return block.emit(Inst.load_global(ident))
        elif ident in self.escaped_variables[self.current_proc]:
            return block.emit(Inst.load_global(ident))
        else:
            return self.read_variable(ident, block)

    def set_variable(self, ident, block, value):
        if ident in self.free_variables[self.current_proc]:
            block.emit(Inst.store_global(ident, value))
        elif ident in self.escaped_variables[self.current_proc]:
            block.emit(Inst.store_global(ident, value))
        else:
            self.write_variable(ident, block, value)

    def visit_IdentExpr(self, expr, block):
        return self.get_variable(expr.ident, block)

    def visit_NumberExpr(self, expr, block):
        return block.emit(Inst.value(expr.number))

    def visit_UnaryExpr(self, expr, block):
        unop_to_opcode = {
            '+':   Opcode.ADD,
            '-':   Opcode.SUB,
            'odd': Opcode.ODD,
        }
        opcode = unop_to_opcode[expr.op]
        value = self.visit(expr.expr, block)
        return block.emit(Inst.unary(opcode, value))

    def visit_BinaryExpr(self, expr, block):
        binop_to_opcode = {
            '+':  Opcode.ADD,
            '-':  Opcode.SUB,
            '*':  Opcode.MUL,
            '/':  Opcode.DIV,
            '<':  Opcode.SLT,
            '>':  Opcode.SGT,
            '<=': Opcode.SLE,
            '>=': Opcode.SGE,
            '==': Opcode.SEQ,
            '!=': Opcode.SNE,
        }
        opcode = binop_to_opcode[expr.op]
        lhs = self.visit(expr.lhs, block)
        rhs = self.visit(expr.rhs, block)
        return block.emit(Inst.binary(opcode, lhs, rhs))

    def visit_AssignStmt(self, stmt, block):
        value = self.visit(stmt.expr, block)
        self.set_variable(stmt.ident, block, value)
        return block

    def visit_CallStmt(self, stmt, block):
        block.emit(Inst.call(stmt.ident))
        return block

    def visit_ReadStmt(self, stmt, block):
        value = block.emit(Inst.scan())
        self.set_variable(stmt.ident, block, value)
        return block

    def visit_WriteStmt(self, stmt, block):
        value = self.visit(stmt.expr, block)
        block.emit(Inst.print(value))
        return block

    def visit_Statements(self, stmts, block):
        for stmt in stmts.stmts:
            block = self.visit(stmt, block)
        return block

    def visit_IfStmt(self, stmt, bentry):
        bthen = self.new_block()
        bexit = self.new_block()
        bthen.name = bthen.name
        bexit.name = bexit.name
        cond = self.visit(stmt.cond, bentry)
        bentry.branch(cond, bthen, bexit)
        self.seal_block(bthen)
        bthenend = self.visit(stmt.body, bthen)
        bthenend.jump(bexit)
        self.seal_block(bexit)
        return bexit

    def visit_IfElseStmt(self, stmt, bentry):
        bthen = self.new_block()
        balt = self.new_block()
        bexit = self.new_block()
        bthen.name = bthen.name
        balt.name = balt.name
        bexit.name = bexit.name
        cond = self.visit(stmt.cond, bentry)
        bentry.branch(cond, bthen, balt)
        self.seal_block(bthen)
        bthenend = self.visit(stmt.body, bthen)
        bthenend.jump(bexit)
        self.seal_block(balt)
        baltend = self.visit(stmt.alt, balt)
        baltend.jump(bexit)
        self.seal_block(bexit)
        return bexit

    def visit_WhileStmt(self, stmt, bentry):
        bheader = self.new_block()
        bbody = self.new_block()
        bexit = self.new_block()
        bheader.name = bheader.name
        bbody.name = bbody.name
        bexit.name = bexit.name
        bentry.jump(bheader)
        cond = self.visit(stmt.cond, bheader)
        bheader.branch(cond, bbody, bexit)
        self.seal_block(bbody)
        bbodyend = self.visit(stmt.body, bbody)
        bbodyend.jump(bheader)
        self.seal_block(bheader)
        self.seal_block(bexit)
        return bexit

class LeafValueCounter(ast.ExprVisitor):
    def __init__(self):
        self.counter = collections.Counter()

    def visit_Decl(self, decl):
        for ident, number in decl.const_decls:
            self.counter[ident] += 1
            self.counter[number] += 1
        for ident in decl.var_decls:
            self.counter[ident] += 1
        for ident, decl1 in decl.proc_decls:
            self.counter[ident] += 1
            self.visit(decl1.stmt)
        self.visit(decl.stmt)

    def visit_ReadStmt(self, stmt):
        self.counter[stmt.ident] += 1

    def visit_AssignStmt(self, stmt):
        self.counter[stmt.ident] += 1
        self.visit(stmt.expr)

    def visit_CallStmt(self, stmt):
        self.counter[stmt.ident] += 1

    def visit_IdentExpr(self, expr):
        self.counter[expr.ident] += 1

    def visit_NumberExpr(self, expr):
        self.counter[expr.number] += 1

class TestSsaConverter(unittest.TestCase):
    def do_test(self, source):
        parser = parse.Parser(source)
        prog = parser.program()
        varck = VariableChecker()
        varck.visit(prog)
        converter = SsaConverter(
            varck.const_decls,
            varck.escaped_variables,
            varck.free_variables)
        proc = converter.convert(prog)

    def test_prog0(self):
        from examples import prog0
        self.do_test(prog0)

    def test_prog0a(self):
        from examples import prog0a
        self.do_test(prog0a)

    def test_prog1(self):
        from examples import prog1
        self.do_test(prog1)

    def test_prog2(self):
        from examples import prog2
        self.do_test(prog2)

    def test_prog3(self):
        from examples import prog3
        self.do_test(prog3)

    def test_prog4(self):
        from examples import prog4
        self.do_test(prog4)

def main():
    from examples import prog1 as source
    parser = parse.Parser(source)
    prog = parser.program()

    varck = VariableChecker()
    varck.visit(prog)

    converter = SsaConverter(
        varck.const_decls,
        varck.escaped_variables,
        varck.free_variables)
    result = converter.convert(prog)

if __name__ == '__main__':
    main()
