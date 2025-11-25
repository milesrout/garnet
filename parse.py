import garnetast as ast
import unittest

def parse(source):
    parser = Parser(source)
    return parser.program()

class Parser:
    def __init__(self, string):
        self.string = string
        self.tokens = self.string.strip().split()
        self.index = 0
        self.keywords = ('const var procedure call begin end '
                        'if then else while do odd loop'.split())
        self.token_type = self.calc_token_type()

    def calc_token_type(self):
        try:
            token = self.tokens[self.index]
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

    def expect(self, *tokens):
        if self.token_type in tokens:
            self.index += 1
            self.token_type = self.calc_token_type()
            if self.token_type == 'eof':
                return ''
            return self.tokens[self.index - 1]
        raise RuntimeError(f'Syntax error: expected {tokens}, got {self.token_type}')

    def program(self):
        b = self.block()
        self.expect('.')
        self.expect('eof')
        b.name = '__main__'
        return b

    def block(self):
        const_decls = []
        var_decls = []
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
            b = self.block()
            self.expect(';')
            proc_decls.append((i, b))
            b.name = i
        stmt = self.statement()
        return ast.Decl(
            const_decls,
            var_decls,
            proc_decls,
            stmt)

    def statement(self):
        if self.accept('call'):
            i = self.ident()
            return ast.CallStmt(i)
        if self.accept('?'):
            i = self.ident()
            return ast.ReadStmt(i)
        if self.accept('!'):
            e = self.expression()
            return ast.WriteStmt(e)
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
        i = self.ident()
        self.expect(':=')
        e = self.expression()
        return ast.AssignStmt(i, e)

    def condition(self):
        if self.accept('odd'):
            e = self.expression()
            return ast.UnaryExpr('odd', e)
        lhs = self.expression()
        op = self.expect('==', '!=', '<', '<=', '>', '>=')
        rhs = self.expression()
        return ast.BinaryExpr(op, lhs, rhs)

    def expression(self):
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
        if n := self.accept('number'):
            return ast.NumberExpr(n)
        i = self.ident()
        return ast.IdentExpr(i)

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
