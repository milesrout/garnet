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
    return r.Imm(int(CMP[cmp][0](a, b)))

def cmp_r(cmp):
    return CMP[cmp][1]

def cmp_z(cmp):
    return CMP[cmp][2]

class InsSel:
    def do_munch_expr(self, inst):
        if isinstance(inst, s.Param):
            return inst

        match inst:
            case s.Const(const):
                return r.Inst.unary(r.Opcode.LI, r.Imm(const))

            case s.Add(s.Const(c0), s.Const(c1)):
                return r.Inst.unary(r.Opcode.LI, r.Imm(c0 + c1))
            case s.Add(e0, s.Const(0)):
                v = self.munch_expr(e)
                return v
            case s.Add(e0, s.Const(c1)):
                v0 = self.munch_expr(e0)
                return r.Inst.binary(r.Opcode.ADDI, v0, r.Imm(c1))
            case s.Add(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(r.Opcode.ADD, v0, v1)

            case s.Sub(s.Const(c0), s.Const(c1)):
                return r.Inst.unary(r.Opcode.LI, r.Imm(c0 - c1))
            case s.Sub(s.Const(0), e):
                v = self.munch_expr(e)
                return r.Inst.binary(r.Opcode.SUB, r.Imm(0), v)
            case s.Sub(e0, s.Const(0)):
                v = self.munch_expr(e)
                return v
            case s.Sub(e0, s.Const(c1)):
                v0 = self.munch_expr(e0)
                return r.Inst.binary(r.Opcode.ADDI, v0, r.Imm(-c1))
            case s.Sub(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(r.Opcode.SUB, v0, v1)

            case s.Mul(s.Const(c0), s.Const(c1)):
                return r.Inst.unary(r.Opcode.LI, r.Imm(c0 * c1))
            case s.Mul(e, s.Const(0)):
                return r.Imm(0)
            case s.Mul(e, s.Const(1)):
                v = self.munch_expr(e)
                return v
            case s.Mul(e, s.Const(2)):
                v = self.munch_expr(e)
                return r.Inst.binary(r.Opcode.ADD, v, v)
            case s.Mul(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(r.Opcode.MUL, v0, v1)

            case s.Div(s.Const(c0), s.Const(c1)) if c1 != 0:
                return r.Inst.unary(r.Opcode.LI, r.Imm(c0 // c1))
            case s.Div(e, s.Const(0)):
                return r.Inst.unary(r.Opcode.LI, r.Imm(0))
            case s.Div(e, s.Const(2)):
                v = self.munch_expr(e)
                v1 = r.Inst.binary(r.Opcode.SRLI, v, r.Imm(63))
                v2 = r.Inst.binary(r.Opcode.ADD, v, v1)
                v3 = r.Inst.binary(r.Opcode.SRAI, v2, r.Imm(1))
                self.output.append(v1)
                self.output.append(v2)
                return v3
            case s.Div(e, s.Const(3)):
                v = self.munch_expr(e)
                v1 = r.Inst.unary(r.Opcode.LI, r.Imm((2**64+2)//3, display=hex))
                v2 = r.Inst.binary(r.Opcode.MULH, v1, v)
                v3 = r.Inst.binary(r.Opcode.SRLI, v, r.Imm(63))
                v4 = r.Inst.binary(r.Opcode.ADD, v2, v3)
                self.output.append(v1)
                self.output.append(v2)
                self.output.append(v3)
                return v4
            case s.Div(e, s.Const(n)) if n & (n - 1) == 0:
                k = n.bit_length() - 1
                v = self.munch_expr(e)
                v0 = r.Inst.binary(r.Opcode.SRAI, v, r.Imm(k-1))
                v1 = r.Inst.binary(r.Opcode.SRLI, v0, r.Imm(64-k))
                v2 = r.Inst.binary(r.Opcode.ADD, v, v1)
                v3 = r.Inst.binary(r.Opcode.SRAI, v2, r.Imm(k))
                self.output.append(v0)
                self.output.append(v1)
                self.output.append(v2)
                return v3
            case s.Div(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return r.Inst.binary(r.Opcode.DIV, v0, v1)

            case s.Inst(cmp, (s.Const(c0), s.Const(c1))) if iscmp(cmp):
                return r.Inst.unary(r.Opcode.LI, r.Imm(cmp_e(cmp, c0, c1)))
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

            case s.Call(proc):
                f = r.Inst.unary(r.Opcode.LA, r.Sym(proc))
                self.output.append(f)
                return r.Inst.unary(r.PseudoOpcode.CALL, f)

            case s.Store(e, var):
                v = self.munch_expr(e)
                a = r.Inst.unary(r.Opcode.LA, r.Sym(var))
                self.output.append(a)
                return r.Inst.binary(r.Opcode.SD, a, v)

            case s.Load(var):
                a = r.Inst.unary(r.Opcode.LA, r.Sym(var))
                self.output.append(a)
                return r.Inst.unary(r.Opcode.LD, a)

            case _:
                print(f'{inst=}')
                raise RuntimeError(f'Unsupported opcode: {inst.opcode}')

    def munch_expr(self, value):
        if isinstance(value, s.Inst):
            if value.done and not value.iseffectful():
                return value.result
        inst = self.do_munch_expr(value)
        value.done = True
        value.result = inst
        if not isinstance(inst, s.Param):
            self.output.append(inst)
        return inst

    def munch_block(self, block):
        for arg in block.cont.args:
            arg.done = False
        for inst in block.insts:
            inst.done = False

        self.outputs = []
        args = {}
        for arg in block.cont.args:
            self.output = []
            args[arg] = self.munch_expr(arg)
            self.outputs.append(self.output)

        for inst in reversed(block.insts):
            if inst.iseffectful():
                self.output = []
                self.munch_expr(inst)
                self.outputs.append(self.output)

        newblock = s.Block(block.name)
        match block.cont:
            case s.ReturnCont():
                newblock.cont = r.ReturnCont()
            case s.JumpCont(target=target):
                newblock.cont = r.Cont.jump(target.target)
                newblock.cont.target.args = {p: args[a] for p, a in target.args.items()}
            case s.BranchCont(value=value, ttrue=ttrue, tfals=tfals):
                self.output = []
                value = self.munch_expr(value)
                self.outputs.insert(0, self.output)
                newblock.cont = r.Cont.branch(value, ttrue.target, tfals.target)
                newblock.cont.ttrue.args = {p: args[a] for p, a in ttrue.args.items()}
                newblock.cont.tfals.args = {p: args[a] for p, a in tfals.args.items()}
        newblock.insts = [a for b in list(reversed(self.outputs)) for a in b]
        newblock.params = block.params[:]
        return newblock

class TestInsSel(unittest.TestCase):
    def do_test(self, source):
        import parse
        import checkvars
        import convertssa
        prog = parse.parse(source)
        const, escaped, free = checkvars.checkvars(prog)
        proc = convertssa.convertssa(prog, const, escaped, free)
        proc.debug()
        proc1 = inssel(proc)
        proc1.debug()

    def test_prog0(self):
        from examples import prog0 as prog
        self.do_test(prog)

    def test_prog0a(self):
        from examples import prog0a as prog
        self.do_test(prog)

    def test_prog1(self):
        from examples import prog1 as prog
        self.do_test(prog)

    def test_prog2(self):
        from examples import prog2 as prog
        self.do_test(prog)

    def test_prog3(self):
        from examples import prog3 as prog
        self.do_test(prog)

    def test_prog4(self):
        from examples import prog4 as prog
        self.do_test(prog)

    def test_prog5(self):
        from examples import prog5 as prog
        self.do_test(prog)

    def test_prog6(self):
        from examples import prog6 as prog
        self.do_test(prog)

def inssel(proc):
    procs = []
    for subproc in proc.procedures:
        procs.append(inssel(subproc))

    sel = InsSel()
    blocks = []
    for block in proc.blocks:
        newblock = sel.munch_block(block)
        blocks.append(newblock)

    newproc = s.Procedure(proc.name, blocks, procs)
    return newproc
