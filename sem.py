# Semantic analysis

import contextlib
from copy import copy
import enum
import unittest

import garnetast as ast
from util import GarnetError

__names__ = ['analyse', 'Type', 'Var', 'ConstVar', 'ReturnVar', 'LocalVar', 'ParamVar',
             'GlobalVar', 'Proc']

class GarnetSemanticError(GarnetError):
    pass

class Type(enum.Enum):
    VOID = enum.auto()
    INT = enum.auto()
    PROC = enum.auto()

class Var:
    writeable = True
    readable = True
    callable = False
    def __init__(self, type, init=None):
        self.type = type
        self.init = init
    def __repr__(self):
        init = ''
        if self.init is not None:
            init = f', {self.init}'
        return f'{self.__class__.__name__}({self.type}{init})'

class ConstVar(Var):
    writeable = False

class LocalVar(Var):
    pass

class ReturnVar(Var):
    pass

class ParamVar(Var):
    pass

class GlobalVar(Var):
    pass

class Proc(Var):
    writeable = False
    readable = False
    callable = True
    def __init__(self):
        super().__init__(Type.PROC)

PRELUDE = {
    'print': Proc(),
}

class SemanticVisitor(ast.Visitor):
    def __init__(self, parent, sem):
        super().__init__()
        self.declared = {}
        self.used = {}
        self.parent = parent
        self.sem = sem

    @contextlib.contextmanager
    def scope(self):
        old = self.declared
        self.declared = copy(old)
        yield
        self.declared = old

    def declare(self, ident, value):
        assert isinstance(ident, str)
        self.declared[ident] = value

    def isdeclared(self, ident):
        if ident in self.declared:
            return self
        if self.parent is not None:
            return self.parent.isdeclared(ident)

    def check(self, ident):
        if decl := self.isdeclared(ident):
            if decl is not self:
                if isinstance(decl.declared[ident], LocalVar):
                    decl.declared[ident] = GlobalVar(
                        type=decl.declared[ident].type,
                        init=decl.declared[ident].init)
        else:
            raise GarnetSemanticError(f'Undeclared identifier {ident}')
        return decl

    def check_readable(self, ident):
        decl = self.check(ident)
        if not decl.declared[ident].readable:
            raise GarnetSemanticError(f'Cannot read from non-value identifier {ident}')
        self.used[ident] = decl.declared[ident]

    def check_writeable(self, ident):
        decl = self.check(ident)
        if not decl.declared[ident].writeable:
            if not decl.declared[ident].readable:
                raise GarnetSemanticError(f'Cannot write to constant identifier {ident}')
            raise GarnetSemanticError(f'Cannot write to non-value identifier {ident}')
        self.used[ident] = decl.declared[ident]

    def check_callable(self, ident):
        decl = self.check(ident)
        if not decl.declared[ident].callable:
            raise GarnetSemanticError(f'Cannot call non-callable identifier {ident}')
        self.used[ident] = decl.declared[ident]

    ##########################################################

    def visit_Decl(self, decl):
        for ident, value in decl.const_decls:
            self.declare(ident, ConstVar(Type.INT, init=value))
        for ident in decl.var_decls:
            self.declare(ident, LocalVar(Type.INT))
        for pdecl in decl.proc_decls:
            sv = SemanticVisitor(parent=self, sem=self.sem)
            sv.declare(pdecl.ident, ReturnVar(Type.INT))
            for param in pdecl.params:
                sv.declare(param, ParamVar(Type.INT))
            sv.visit(pdecl.decl)
            self.declare(pdecl.ident, Proc())
        self.visit(decl.stmt)
        self.sem.symbols[decl] = Symbols(self.declared, self.used)

    def visit_IdentExpr(self, expr):
        self.check_readable(expr.ident)

    def visit_NumberExpr(self, expr):
        pass

    def visit_UnaryExpr(self, expr):
        self.visit(expr.expr)

    def visit_BinaryExpr(self, expr):
        self.visit(expr.lhs)
        self.visit(expr.rhs)

    def visit_AssignExpr(self, expr):
        # TODO: Support assignments to things other than IdentExpr
        self.check_writeable(expr.ident.ident)
        self.visit(expr.expr)

    def visit_CallExpr(self, expr):
        for arg in expr.args:
            self.visit(arg)
        self.check_callable(expr.ident)

    def visit_ExprStmt(self, stmt):
        self.visit(stmt.expr)

    def visit_Statements(self, stmts):
        for stmt in stmts.stmts:
            self.visit(stmt)

    def visit_IfStmt(self, stmt):
        self.visit(stmt.cond)
        self.visit(stmt.body)

    def visit_IfElseStmt(self, stmt):
        self.visit(stmt.cond)
        self.visit(stmt.body)
        self.visit(stmt.alt)

    def visit_LoopStmt(self, stmt):
        self.visit(stmt.body)

    def visit_WhileStmt(self, stmt):
        self.visit(stmt.cond)
        self.visit(stmt.body)

class PreludeSemanticVisitor(SemanticVisitor):
    def __init__(self):
        super().__init__(parent=None, sem=None)
        self.declared = copy(PRELUDE)

class Semantics:
    def __init__(self, prog):
        self.prog = prog
        self.symbols = {}

    def analyse(self):
        psv = PreludeSemanticVisitor()
        sv = SemanticVisitor(psv, self)
        sv.visit(self.prog)
        return self.prog

class Symbols:
    def __init__(self, declared, used):
        self.declared = declared
        self.used = used

def analyse(prog):
    sem = Semantics(prog)
    sem.analyse()
    return sem.symbols

class TestSemantics(unittest.TestCase):
    def do_test(self, source):
        from parse import parse
        prog = parse(source)
        sem = Semantics(prog)
        proc = sem.analyse()
        debug = ast.DebugVisitor()
        for block, (declared, used) in sem.symbols.items():
            debug.visit(block, subdecls=False)
            print(f'{declared=}')
            print(f'{used=}')

    def test_prog0(self):
        from examples import prog0
        self.do_test(prog0)

    def test_prog0a(self):
        from examples import prog0a
        self.do_test(prog0a)
