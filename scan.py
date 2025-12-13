import re
tokens = {
    'ident':     '[a-zA-Z_][a-zA-Z0-9_]*',
    'number':    '[0-9]+',
    'string':    '"(?:[^"]|\\")*"',
    'char':      "'.'",
    'lparen':    '\\(',
    'rparen':    '\\)',
    'lsqbrack':  '\\[',
    'rsqbrack':  '\\]',
    'lcurly':    '\\{',
    'rcurly':    '\\}',
    'mul':       '\\*',
    'div':       '/',
    'add':       '\\+',
    'sub':       '-',
    'eq':        '==',
    'ne':        '!=',
    'le':        '<=',
    'ge':        '>=',
    'lt':        '<',
    'gt':        '>',
    'assign':    ':=',
    'semi':      ';',
    'comma':     ',',
    'equals':    '=',
    'qmark':     '\\?',
    'at':        '@',
    'dot':       '\\.',
    'space':     '[ \\t]+',
    'fail':      '.',
}
keywords = set('const var procedure call begin end '
               'if then else while do odd unopt loop'.split())

tokens = {k: f'(?P<{k}>{v})' for k, v in tokens.items()}
tokens = '|'.join(tokens.values())
pattern = re.compile(tokens)

def scan(prog):
    for match in pattern.finditer(prog):
        toktype = match.lastgroup
        value = match.group()
        if toktype == 'fail':
            raise RuntimeError('Invalid token')
        if toktype == 'ident' and value in keywords:
            yield value#(value, value)
            continue
        if toktype != 'space':
            yield value#(toktype, value)

if __name__ == '__main__':
    from examples import prog1
    print(list(scan(prog1)))
    print(prog1.strip().split())
