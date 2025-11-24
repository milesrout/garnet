import collections
import unittest
import garnetast as ast
from ssa import Block, Inst, Opcode, Procedure

def convertssa(prog, const, escaped, free):
    converter = SsaConverter(const, escaped, free)
    proc = converter.convert(prog)
    return proc

class SsaConverter(ast.Visitor):
    def __init__(self, constants, free_variables, escaped_variables):
        self.constants = constants
        self.free_variables = free_variables
        self.escaped_variables = escaped_variables

        self.current_def = collections.defaultdict(dict)
        self.incomplete_params = collections.defaultdict(dict)
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
            param, value = block.param(variable)
            self.incomplete_params[block][variable] = (param, value)
        elif len(block.preds) == 1:
            param, pvalue = block.param(variable)
            pred = next(iter(block.preds))
            avalue = self.read_variable(variable, pred)
            self.add_block_args(variable, param, pvalue)
            self.set_variable(variable, block, pvalue)
            return pvalue
        else:
            param, value = block.param(variable)
            self.set_variable(variable, block, value)
            self.add_block_args(variable, param, value)
        self.write_variable(variable, block, value)
        return value

    def add_block_args(self, variable, param, value):
        for pred in value.block.preds:
            pred.add_arg(param, value, self.read_variable(variable, pred))

    def seal_block(self, block):
        for variable, (param, value) in self.incomplete_params[block].items():
            self.add_block_args(variable, param, value)
        self.sealed_blocks.add(block)

    def new_block(self, addendum=None):
        block = Block()
        if addendum is not None:
            block.name += '_' + addendum
        self.blocks.append(block)
        return block

    def convert(self, prog):
        bbody = self.new_block('fentry')
        self.seal_block(bbody)
        bbodyend = self.visit(prog, bbody)
        bexit = self.new_block('fexit')
        bbodyend.jump(bexit)
        self.seal_block(bexit)
        bexit.ret()
        return Procedure(self.blocks, self.procedures)

    def get_variable(self, ident, block):
        if ident in self.free_variables[self.current_proc]:
            return block.emit(Inst.load(ident))
        elif ident in self.escaped_variables[self.current_proc]:
            return block.emit(Inst.load(ident))
        else:
            return self.read_variable(ident, block)

    def set_variable(self, ident, block, value):
        if ident in self.free_variables[self.current_proc]:
            block.emit(Inst.store(ident, value))
        elif ident in self.escaped_variables[self.current_proc]:
            block.emit(Inst.store(ident, value))
        else:
            self.write_variable(ident, block, value)

    ####

    def visit_Decl(self, decl, block):
        old_current_proc = self.current_proc
        self.current_proc = decl

        for ident, decl1 in decl.proc_decls:
            converter = SsaConverter(self.constants, self.free_variables, self.escaped_variables)
            self.procedures[ident] = converter.convert(decl1)
            self.procedures[ident].debug()

        for ident, number in self.constants:
            value = block.emit(Inst.const(number))
            self.write_variable(ident, block, value)

        block = self.visit(decl.stmt, block)
        self.current_proc = old_current_proc
        return block

    def visit_IdentExpr(self, expr, block):
        return self.get_variable(expr.ident, block)

    def visit_NumberExpr(self, expr, block):
        return block.emit(Inst.const(expr.number))

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
        bthen = self.new_block('ithen')
        bexit = self.new_block('iexit')
        cond = self.visit(stmt.cond, bentry)
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
        bheader = self.new_block('wheader')
        bbody = self.new_block('wbody')
        bexit = self.new_block('wexit')
        bentry.jump(bheader)
        cond = self.visit(stmt.cond, bheader)
        bheader.branch(cond, bbody, bexit)
        self.seal_block(bbody)
        bbodyend = self.visit(stmt.body, bbody)
        bbodyend.jump(bheader)
        self.seal_block(bheader)
        self.seal_block(bexit)
        return bexit

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
