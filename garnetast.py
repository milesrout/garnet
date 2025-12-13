import abc
from abc import abstractmethod
import enum

class UnaryOp(enum.Enum):
    NEG = enum.auto()
    INV = enum.auto()
    NOT = enum.auto()
    ODD = enum.auto()

class BinaryOp(enum.Enum):
    ADD = enum.auto()
    SUB = enum.auto()
    MUL = enum.auto()

class Expr:
    pass

class Stmt:
    pass

class Decl:
    def __init__(self, const_decls, var_decls, proc_decls, stmt):
        self.const_decls = const_decls
        self.var_decls = var_decls
        self.proc_decls = proc_decls
        self.stmt = stmt

class IdentExpr(Expr):
    def __init__(self, ident):
        self.ident = ident

class NumberExpr(Expr):
    def __init__(self, number):
        self.number = number

class UnaryExpr(Expr):
    def __new__(cls, op, expr):
        match expr:
            case NumberExpr(number=n):
                match op:
                    case '+':   return expr
                    case '-':   return NumberExpr(-n)
                    case 'odd': return NumberExpr(n % 2)
        return super().__new__(cls)

    def __init__(self, op, expr):
        self.op = op
        self.expr = expr

class BinaryExpr(Expr):
    def __new__(cls, op, lhs, rhs):
        match (lhs, rhs):
            case (NumberExpr(number=l), NumberExpr(number=r)):
                match op:
                    case '+':  return NumberExpr(l + r)
                    case '-':  return NumberExpr(l - r)
                    case '*':  return NumberExpr(l * r)
                    case '==': return NumberExpr(int(l == r))
                    case '!=': return NumberExpr(int(l != r))
                    case '<=': return NumberExpr(int(l <= r))
                    case '>=': return NumberExpr(int(l >= r))
                    case '<':  return NumberExpr(int(l < r))
                    case '>':  return NumberExpr(int(l > r))
        return super().__new__(cls)

    def __init__(self, op, lhs, rhs):
        self.op = op
        self.lhs = lhs
        self.rhs = rhs

class AssignStmt(Stmt):
    def __init__(self, ident, expr):
        self.ident = ident
        self.expr = expr

class CallStmt(Stmt):
    def __init__(self, ident):
        self.ident = ident

class Statements(Stmt):
    def __init__(self, stmts):
        self.stmts = stmts

class IfStmt(Stmt):
    def __new__(cls, cond, body):
        match cond:
            case NumberExpr(number=n):
                return body if n else Statements([])
        return super().__new__(cls)

    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class IfElseStmt(Stmt):
    def __new__(cls, cond, body, alt):
        match cond:
            case NumberExpr(number=n):
                return body if n else alt
        return super().__new__(cls)

    def __init__(self, cond, body, alt):
        self.cond = cond
        self.body = body
        self.alt = alt

class WhileStmt(Stmt):
    def __new__(cls, cond, body):
        match cond:
            case NumberExpr(number=n):
                if not n:
                    return Statements([])
        return super().__new__(cls)

    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class LoopStmt(Stmt):
    def __init__(self, body):
        self.body = body

class Visitor(abc.ABC):
    def visit(self, node, *args, **kwds):
        func = getattr(self, 'visit_' + node.__class__.__name__)
        return func(node, *args, **kwds)

    @abstractmethod
    def visit_Decl(self, decl, *args, **kwds): ...

    @abstractmethod
    def visit_IdentExpr(self, expr, *args, **kwds): ...

    @abstractmethod
    def visit_NumberExpr(self, expr, *args, **kwds): ...

    @abstractmethod
    def visit_UnaryExpr(self, expr, *args, **kwds): ...

    @abstractmethod
    def visit_BinaryExpr(self, expr, *args, **kwds): ...

    @abstractmethod
    def visit_AssignStmt(self, stmt, *args, **kwds): ...

    @abstractmethod
    def visit_CallStmt(self, stmt, *args, **kwds): ...

    @abstractmethod
    def visit_Statements(self, stmts, *args, **kwds): ...

    @abstractmethod
    def visit_IfStmt(self, stmt, *args, **kwds): ...

    @abstractmethod
    def visit_IfElseStmt(self, stmt, *args, **kwds): ...

    @abstractmethod
    def visit_LoopStmt(self, stmt, *args, **kwds): ...

    @abstractmethod
    def visit_WhileStmt(self, stmt, *args, **kwds): ...

class ExprVisitor(Visitor):
    def visit_Decl(self, decl, *args, **kwds):
        for ident, decl1 in decl.proc_decls:
            self.visit(decl1.stmt, *args, **kwds)
        self.visit(decl.stmt, *args, **kwds)

    def visit_IdentExpr(self, expr, *args, **kwds):
        pass

    def visit_NumberExpr(self, expr, *args, **kwds):
        pass

    def visit_UnaryExpr(self, expr, *args, **kwds):
        self.visit(expr.expr, *args, **kwds)

    def visit_BinaryExpr(self, expr, *args, **kwds):
        self.visit(expr.lhs, *args, **kwds)
        self.visit(expr.rhs, *args, **kwds)

    def visit_AssignStmt(self, stmt, *args, **kwds):
        self.visit(stmt.expr, *args, **kwds)

    def visit_CallStmt(self, stmt, *args, **kwds):
        pass

    def visit_Statements(self, stmts, *args, **kwds):
        for stmt in stmts.stmts:
            self.visit(stmt, *args, **kwds)

    def visit_IfStmt(self, stmt, *args, **kwds):
        self.visit(stmt.cond, *args, **kwds)
        self.visit(stmt.body, *args, **kwds)

    def visit_IfElseStmt(self, stmt, *args, **kwds):
        self.visit(stmt.cond, *args, **kwds)
        self.visit(stmt.body, *args, **kwds)
        self.visit(stmt.alt, *args, **kwds)

    def visit_LoopStmt(self, stmt, *args, **kwds):
        self.visit(stmt.body, *args, **kwds)

    def visit_WhileStmt(self, stmt, *args, **kwds):
        self.visit(stmt.cond, *args, **kwds)
        self.visit(stmt.body, *args, **kwds)

class StmtVisitor(Visitor):
    def visit_Decl(self, decl, *args, **kwds):
        for ident, decl1 in decl.proc_decls:
            self.visit(decl1.stmt, *args, **kwds)
        self.visit(decl.stmt, *args, **kwds)

    def visit_AssignStmt(self, stmt, *args, **kwds):
        pass

    def visit_CallStmt(self, stmt, *args, **kwds):
        pass

    def visit_Statements(self, stmts, *args, **kwds):
        for stmt in stmts.stmts:
            self.visit(stmt, *args, **kwds)

    def visit_IfStmt(self, stmt, *args, **kwds):
        self.visit(stmt.cond, *args, **kwds)
        self.visit(stmt.body, *args, **kwds)

    def visit_IfElseStmt(self, stmt, *args, **kwds):
        self.visit(stmt.cond, *args, **kwds)
        self.visit(stmt.body, *args, **kwds)
        self.visit(stmt.alt, *args, **kwds)

    def visit_LoopStmt(self, stmt, *args, **kwds):
        self.visit(stmt.body, *args, **kwds)

    def visit_WhileStmt(self, stmt, *args, **kwds):
        self.visit(stmt.cond, *args, **kwds)
        self.visit(stmt.body, *args, **kwds)
