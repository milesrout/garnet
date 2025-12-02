import operator
import unittest

import ssa as s
import ssa_riscv64 as r

CMP = {
    s.Opcode.SEQ: (operator.eq, r.Opcode.SEQ, r.Opcode.SEQZ),
    s.Opcode.SNE: (operator.ne, r.Opcode.SNE, r.Opcode.SNEZ),
    s.Opcode.SLT: (operator.lt, r.Opcode.SLT, r.Opcode.SLTZ),
    s.Opcode.SGT: (operator.gt, r.Opcode.SGT, r.Opcode.SGTZ),
    s.Opcode.SLE: (operator.le, r.Opcode.SLE, r.Opcode.SLEZ),
    s.Opcode.SGE: (operator.ge, r.Opcode.SGE, r.Opcode.SGEZ),
}

def iscmp(op):
    return op in CMP

def cmp_e(cmp, a, b):
    #print('cmp_e', cmp, CMP[cmp][0])
    return int(CMP[cmp][0](a, b))

def cmp_r(cmp):
    #print('cmp_r', cmp, CMP[cmp][1])
    return CMP[cmp][1]

def cmp_z(cmp):
    #print('cmp_z', cmp, CMP[cmp][2])
    return CMP[cmp][2]

def iseffectful(inst):
    return inst.opcode != s.Opcode.CONST

class InsSel:
    def do_munch_expr(self, inst):
        if isinstance(inst, s.Param):
            return inst

        match inst:
            case s.Const(const):
                return r.Inst.const(const)

            case s.Add(s.Const(c0), s.Const(c1)):
                return r.Inst.const(c0 + c1)
            case s.Add(e0, s.Const(c1)):
                v0 = self.munch_expr(e0)
                return r.Inst.binary(r.Opcode.ADDI, v0, r.Imm(c1))
            case s.Add(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(r.Opcode.ADD, v0, v1)

            case s.Mul(s.Const(c0), s.Const(c1)):
                return r.Inst.const(c0 * c1)
            case s.Mul(e, s.Const(2)):
                v = self.munch_expr(e)
                return r.Inst.binary(r.Opcode.ADD, v, v)
            case s.Mul(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(r.Opcode.MUL, v0, v1)

            case s.Div(s.Const(c0), s.Const(c1)) if c1 != 0:
                return r.Inst.const(c0 // c1)
            case s.Div(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(r.Opcode.DIV, v0, v1)

            case s.Inst(cmp, (s.Const(c0), s.Const(c1))) if iscmp(cmp):
                return r.Inst.const(cmp_e(cmp, c0, c1))
            case s.Inst(cmp, (e0, s.Const(0))) if iscmp(cmp):
                v0 = self.munch_expr(e0)
                return r.Inst.unary(cmp_z(cmp), v0)
            case s.Inst(cmp, (e0, e1)) if iscmp(cmp):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(cmp_r(cmp), v0, v1)

            case s.Odd(e):
                v0 = self.munch_expr(e)
                v1 = r.Inst.binary(r.Opcode.ANDI, v0, r.Imm(1))
                self.output.append(v1)
                return r.Inst.unary(r.Opcode.SNEZ, v1)

            case s.Print(e):
                v = self.munch_expr(e)
                f = r.Inst.func("_print")
                self.output.append(f)
                return r.Inst.unary(r.PseudoOpcode.CALL, f)

            case s.Scan():
                f = r.Inst.func("_scan")
                self.output.append(f)
                return r.Inst.unary(r.PseudoOpcode.CALL, f)

            case _:
                print(f'{inst=}')
                raise RuntimeError(f'Unsupported opcode: {inst.opcode}')

    def munch_expr(self, value):
        inst = self.do_munch_expr(value)
        value.done = True
        if not isinstance(inst, s.Param):
            self.output.append(inst)
        return inst

    def munch_block(self, block):
        for inst in block.insts:
            inst.done = False
        self.outputs = []
        for i, inst in reversed(list(enumerate(block.insts))):
            self.output = []
            if iseffectful(inst) and not inst.done:
                self.munch_expr(inst)
                self.outputs.append(self.output)
        return list(reversed(self.outputs))

class TestInssel(unittest.TestCase):
    def do_test(self, source):
        import parse
        import checkvars
        import convertssa
        prog = parse.parse(source)
        const, escaped, free = checkvars.checkvars(prog)
        proc = convertssa.convertssa(prog, const, escaped, free)
        inssel = InsSel()
        for block in proc.blocks:
            print(f'{block.name}:')
            groups = inssel.munch_block(block)
            names = {}
            i = 1
            for group in groups:
                for inst in group:
                    names[inst] = f'x{i}'
                    i += 1
            for group in groups:
                for inst in group:
                    inst.debug(names)

    def test_prog0(self):
        from examples import prog6 as prog
        self.do_test(prog)

