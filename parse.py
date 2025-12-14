from util import GarnetError
from scan import scan
import garnetast as ast
import unittest

class GarnetSyntaxError(GarnetError):
    pass

def parse(source):
    parser = Parser(source)
    return parser.program()

class Parser:
    def __init__(self, string):
        self.string = string
        self.tokens = list(scan(self.string))
        self.index = 0
        self.keywords = ('const var procedure call begin end param '
                        'if then else while do odd unopt loop'.split())
        self.token_type = self.calc_token_type()

    def calc_token_type(self, index=None):
        if index is None:
            index = self.index
        try:
            token = self.tokens[index]
        except IndexError:
            return 'eof'
        if not token.isascii():
            raise RuntimeError('Unicode not supported')
        if token in self.keywords:
            return token
        if token[0].isalpha() and token.isalnum():
            return 'ident'
        if token.isdigit():
            return 'number'
        return token

    def accept(self, *tokens):
        if self.token_type in tokens:
            self.index += 1
            self.token_type = self.calc_token_type()
            if self.token_type == 'eof':
                return ''
            return self.tokens[self.index - 1]

    def fmttoken(self, index):
        token = self.tokens[index]
        toktype = self.calc_token_type(index)
        if toktype == 'ident' or toktype == 'number':
            return f"{toktype}('{token}')"
        return str(toktype)

    def expect(self, *tokens):
        if self.token_type in tokens:
            self.index += 1
            self.token_type = self.calc_token_type()
            if self.token_type == 'eof':
                return ''
            return self.tokens[self.index - 1]
        if len(tokens) == 1:
            expected = repr(tokens[0])
        else:
            expected = repr(tokens)
        actual = self.fmttoken(self.index)
        amount = 5
        context_before = range(self.index - amount, self.index)
        context_after = range(self.index + 1, self.index + amount)
        context_before = ' '.join(map(self.fmttoken, context_before))
        context_after = ' '.join(map(self.fmttoken, context_after))
        context = f'{context_before} >>{actual}<< {context_after}'
        raise GarnetSyntaxError(
            f'expected {expected}, got {actual} ({context})')

    def program(self):
        b = self.block('__main__')
        self.expect('.')
        self.expect('eof')
        return b

    def block(self, name):
        const_decls = []
        var_decls = []
        param_decls = []
        proc_decls = []
        if self.accept('const'):
            i = self.ident()
            self.expect('=')
            n = self.number()
            const_decls.append((i, n))
            while self.accept(','):
                i = self.ident()
                self.expect('=')
                n = self.number()
                const_decls.append((i, n))
            self.expect(';')
        if self.accept('var'):
            i = self.ident()
            var_decls.append(i)
            while self.accept(','):
                i = self.ident()
                var_decls.append(i)
            self.expect(';')
        while self.accept('procedure'):
            i = self.ident()
            self.expect(';')
            ps = []
            if self.accept('param'):
                ps.append(self.ident())
                while self.accept(','):
                    ps.append(self.ident())
                self.expect(';')
            b = self.block(i)
            self.expect(';')
            proc_decls.append(ast.ProcDecl(i, ps, b))
            b.label = i
        stmt = self.statement()
        return ast.Decl(
            name,
            const_decls,
            var_decls,
            proc_decls,
            stmt)

    def statement(self):
        if self.accept('begin'):
            ss = [self.statement()]
            while self.accept(';'):
                ss.append(self.statement())
            self.expect('end')
            return ast.Statements(ss)
        if self.accept('if'):
            cond = self.condition()
            self.expect('then')
            body = self.statement()
            if self.accept('else'):
                alt = self.statement()
                return ast.IfElseStmt(cond, body, alt)
            return ast.IfStmt(cond, body)
        if self.accept('while'):
            cond = self.condition()
            self.expect('do')
            body = self.statement()
            return ast.WhileStmt(cond, body)
        if self.accept('loop'):
            body = self.statement()
            return ast.LoopStmt(body)
        e = self.expression()
        return ast.ExprStmt(e)

    def condition(self):
        if self.accept('odd'):
            e = self.expression()
            return ast.UnaryExpr('odd', e)
        lhs = self.expression()
        op = self.expect('==', '!=', '<', '<=', '>', '>=')
        rhs = self.expression()
        return ast.BinaryExpr(op, lhs, rhs)

    def expression(self):
        a = self.arith_expression()
        if self.accept(':='):
            # TODO: Support assignments to things other than IdentExpr
            if not isinstance(a, ast.IdentExpr):
                raise SyntaxError('May only assign to identifiers')
            e = self.expression()
            return ast.AssignExpr(a, e)
        return a

    def arith_expression(self):
        if op := self.accept('+', '-'):
            t = self.term()
            e = ast.UnaryExpr(op, t)
        else:
            e = self.term()
        while op := self.accept('+', '-'):
            t = self.term()
            e = ast.BinaryExpr(op, e, t)
        return e

    def term(self):
        t = self.factor()
        while op := self.accept('*', '/'):
            f = self.factor()
            t = ast.BinaryExpr(op, t, f)
        return t

    def factor(self):
        if self.accept('('):
            e = self.expression()
            self.expect(')')
            return e
        if self.accept('unopt'):
            e = self.factor()
            return ast.UnaryExpr('unopt', e)
        if self.accept('call'):
            i = self.ident()
            if self.accept('('):
                ps = self.arglist()
                self.expect(')')
            else:
                ps = []
            return ast.CallExpr(i, ps)
        if n := self.accept('number'):
            return ast.NumberExpr(int(n))
        i = self.ident()
        return ast.IdentExpr(i)

    def arglist(self):
        ps = []
        p = self.expression()
        ps.append(p)
        while self.accept(','):
            p = self.expression()
            ps.append(p)
        return ps

    def ident(self):
        return self.expect('ident')

    def number(self):
        return self.expect('number')

class TestParser(unittest.TestCase):
    def test_prog1(self):
        from examples import prog1
        parser = Parser(prog1)
        parser.program()

    def test_prog2(self):
        from examples import prog2
        parser = Parser(prog2)
        parser.program()

    def test_prog3(self):
        from examples import prog3
        parser = Parser(prog3)
        parser.program()
