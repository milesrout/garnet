import collections
import contextlib
import functools
import itertools
import unittest

import garnetast as ast
import sem
from ssa import Procedure
from ssa.abstract import Block, Inst, Opcode, AbstractReturnValue

def convertssa(prog, symbols):
    converter = SsaConverter(symbols)
    proc = converter.convert(prog)
    return proc

class SsaConverter(ast.Visitor):
    def __init__(self, symbols):
        self.symbols = symbols
        self.current_def = collections.defaultdict(dict)
        self.incomplete_params = collections.defaultdict(dict)
        self.blocks = []
        self.sealed_blocks = set()
        self.procedures = []
        self.current_proc = None
        self.current_break = None
        self.fentry = None

    def write_variable(self, variable, block, value):
        self.current_def[variable][block] = value

    def read_variable(self, variable, block):
        if block in self.current_def[variable]:
            return self.current_def[variable][block]
        return self.read_variable_recursive(variable, block)

    def read_variable_recursive(self, variable, block):
        if block not in self.sealed_blocks:
            param = block.param()
            self.incomplete_params[block][variable] = param
        elif len(block.preds) == 0:
            raise RuntimeError(f'Syntax error: unbound local variable {variable}')
        elif len(block.preds) == 1:
            param = block.param()
            pred = next(iter(block.preds))
            avalue = self.read_variable(variable, pred)
            self.add_block_args(variable, param)
            self.set_variable(variable, block, param)
            return param
        else:
            param = block.param()
            self.set_variable(variable, block, param)
            self.add_block_args(variable, param)
        self.write_variable(variable, block, param)
        return param

    def add_block_args(self, variable, param):
        for pred in param.block.preds:
            pred.add_arg(param, self.read_variable(variable, pred))

    def seal_block(self, block):
        for variable, param in self.incomplete_params[block].items():
            self.add_block_args(variable, param)
        self.sealed_blocks.add(block)

    def new_block(self, addendum=None):
        block = Block()
        if addendum is not None:
            block.label += '_' + addendum
        self.blocks.append(block)
        return block

    def convert(self, prog):
        bbody = self.new_block('fentry')
        self.seal_block(bbody)
        self.fentry = bbody
        bbodyend = self.visit(prog, bbody)
        bexit = self.new_block('fexit')
        bbodyend.jump(bexit)
        self.seal_block(bexit)
        bexit.ret()
        return Procedure('__main__', self.blocks, self.procedures)

    def get_variable(self, variable, block):
        declaration = self.symbols[self.current_proc].used[variable]
        match declaration:
            case sem.ParamVar():
                param = self.fentry.param()
                self.write_variable(variable, self.fentry, param)
                return self.read_variable(variable, block)
            case sem.LocalVar():
                return self.read_variable(variable, block)
            case sem.ConstVar(init=value):
                return block.emit(Inst.const(value))
            case sem.GlobalVar():
                return block.emit(Inst.load(variable))
            case _:
                raise NotImplementedError(f"Cannot convert '{variable}' ({declaration}) to SSA")

    def set_variable(self, variable, block, value):
        declaration = self.symbols[self.current_proc].used[variable]
        match declaration:
            case sem.ReturnVar():
                self.write_variable(variable, block, value)
            case sem.LocalVar():
                self.write_variable(variable, block, value)
            case sem.GlobalVar():
                block.emit(Inst.store(variable, value))
            case _:
                raise NotImplementedError(f"Cannot convert '{variable}' ({declaration}) to SSA")

    ####

    def visit_Decl(self, decl, block):
        old_current_proc = self.current_proc
        self.current_proc = decl

        for pdecl in decl.proc_decls:
            converter = SsaConverter(self.symbols)
            proc = converter.convert(pdecl.decl)
            proc.label = pdecl.ident
            self.procedures.append(proc)

        block = self.visit(decl.stmt, block)
        self.current_proc = old_current_proc
        return block

    def visit_IdentExpr(self, expr, block):
        return (self.get_variable(expr.ident, block), block)

    def visit_NumberExpr(self, expr, block):
        return (block.emit(Inst.const(expr.number)), block)

    def visit_UnaryExpr(self, expr, block):
        unop_to_opcode = {
            '+':     Opcode.ADD,
            '-':     Opcode.SUB,
            'odd':   Opcode.ODD,
            'unopt': Opcode.UNOPT,
        }
        opcode = unop_to_opcode[expr.op]
        value, block = self.visit(expr.expr, block)
        return (block.emit(Inst.unary(opcode, value)), block)

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
        lhs, block = self.visit(expr.lhs, block)
        rhs, block = self.visit(expr.rhs, block)
        return (block.emit(Inst.binary(opcode, lhs, rhs)), block)

    def visit_AssignExpr(self, expr, block):
        value, block = self.visit(expr.expr, block)
        self.set_variable(expr.ident.ident, block, value)
        return (value, block)

    def visit_CallExpr(self, expr, block):
        args = []
        for arg in expr.args:
            argvalue, block = self.visit(arg, block)
            args.append(argvalue)
        bthen = self.new_block('cthen')
        block.call(expr.ident, args, bthen)
        self.seal_block(bthen)
        param = bthen.param()
        block.cont.then.add_arg(param, AbstractReturnValue)
        return (param, bthen)

    def visit_ExprStmt(self, stmt, block):
        value, block = self.visit(stmt.expr, block)
        return block

    def visit_Statements(self, stmts, block):
        for stmt in stmts.stmts:
            block = self.visit(stmt, block)
        return block

    def visit_IfStmt(self, stmt, bentry):
        bthen = self.new_block('ithen')
        bexit = self.new_block('iexit')
        cond, bentry = self.visit(stmt.cond, bentry)
        bentry.branch(cond, bthen, bexit)
        self.seal_block(bthen)
        bthenend = self.visit(stmt.body, bthen)
        bthenend.jump(bexit)
        self.seal_block(bexit)
        return bexit

    def visit_IfElseStmt(self, stmt, bentry):
        bthen = self.new_block('ethen')
        balt = self.new_block('ealt')
        bexit = self.new_block('eexit')
        cond, bentry = self.visit(stmt.cond, bentry)
        bentry.branch(cond, bthen, balt)
        self.seal_block(bthen)
        bthenend = self.visit(stmt.body, bthen)
        bthenend.jump(bexit)
        self.seal_block(balt)
        baltend = self.visit(stmt.alt, balt)
        baltend.jump(bexit)
        self.seal_block(bexit)
        return bexit

    def visit_LoopStmt(self, stmt, bentry):
        bbody = self.new_block('lbody')
        bexit = self.new_block('lexit')
        bentry.jump(bbody)
        with self.with_break(bexit):
            bbodyend = self.visit(stmt.body, bbody)
        bbodyend.jump(bbody)
        self.seal_block(bbody)
        self.seal_block(bexit)
        return bexit

    def visit_WhileStmt(self, stmt, bentry):
        bheader = self.new_block('wheader')
        bbody = self.new_block('wbody')
        bexit = self.new_block('wexit')
        bentry.jump(bheader)
        cond, bheader = self.visit(stmt.cond, bheader)
        bheader.branch(cond, bbody, bexit)
        self.seal_block(bbody)
        with self.with_break(bexit):
            bbodyend = self.visit(stmt.body, bbody)
        bbodyend.jump(bheader)
        self.seal_block(bheader)
        self.seal_block(bexit)
        return bexit

    @contextlib.contextmanager
    def with_break(self, block):
        old_break = self.current_break
        self.current_break = block
        yield
        self.current_break = old_break

class TestSsaConverter(unittest.TestCase):
    def do_test(self, source):
        import parse
        from checkvars import checkvars
        parser = parse.Parser(source)
        prog = parser.program()
        const, escaped, free = checkvars(prog)
        proc = convertssa(prog, const, escaped, free)
        proc.debug()

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

    def test_prog5(self):
        from examples import prog5
        self.do_test(prog5)
