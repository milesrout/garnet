import collections
from copy import copy
import garnetast as ast

def checkvars(prog):
    varck = VariableChecker()
    varck.visit(prog)
    return (varck.const_decls, varck.escaped_variables, varck.free_variables)

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
