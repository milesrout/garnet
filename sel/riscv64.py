import operator
import unittest

from ssa import Param, Procedure
import ssa.abstract as sa
import ssa.riscv64 as sr

CMP = {
    sa.Opcode.SEQ: (operator.eq, sr.Opcode.SEQ, sr.Opcode.SEQZ),
    sa.Opcode.SNE: (operator.ne, sr.Opcode.SNE, sr.Opcode.SNEZ),
    sa.Opcode.SLT: (operator.lt, sr.Opcode.SLT, sr.Opcode.SLTZ),
    sa.Opcode.SGT: (operator.gt, sr.Opcode.SGT, sr.Opcode.SGTZ),
    sa.Opcode.SLE: (operator.le, sr.Opcode.SLE, sr.Opcode.SLEZ),
    sa.Opcode.SGE: (operator.ge, sr.Opcode.SGE, sr.Opcode.SGEZ),
}

def iscmp(op):
    return op in CMP

def cmp_e(cmp, a, b):
    return sr.Imm(int(CMP[cmp][0](a, b)))

def cmp_r(cmp):
    return CMP[cmp][1]

def cmp_z(cmp):
    return CMP[cmp][2]

class InsSel:
    def __init__(self):
        self.blockmap = {}

    def fixblocks(self, proc):
        for block in proc.blocks:
            block.preds = [self.blockmap[p] for p in block.preds]
            block.succs = [self.blockmap[s] for s in block.succs]
            match block.cont:
                case sr.JumpCont(target=target):
                    target.target = self.blockmap[target.target]
                case sr.BranchCont(ttrue=ttrue, tfals=tfals):
                    ttrue.target = self.blockmap[ttrue.target]
                    tfals.target = self.blockmap[tfals.target]

    def do_munch_expr(self, inst):
        if isinstance(inst, Param):
            return inst

        match inst:
            case sa.Const(const):
                return sr.Inst.unary(sr.Opcode.LI, sr.Imm(const))

            case sa.Add(sa.Const(c0), sa.Const(c1)):
                return sr.Inst.unary(sr.Opcode.LI, sr.Imm(c0 + c1))
            case sa.Add(e0, sa.Const(0)):
                v = self.munch_expr(e)
                return v
            case sa.Add(e0, sa.Const(c1)):
                v0 = self.munch_expr(e0)
                return sr.Inst.binary(sr.Opcode.ADDI, v0, sr.Imm(c1))
            case sa.Add(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return sr.Inst.binary(sr.Opcode.ADD, v0, v1)

            case sa.Sub(sa.Const(c0), sa.Const(c1)):
                return sr.Inst.unary(sr.Opcode.LI, sr.Imm(c0 - c1))
            case sa.Sub(sa.Const(0), e):
                v = self.munch_expr(e)
                return sr.Inst.binary(sr.Opcode.SUB, sr.Imm(0), v)
            case sa.Sub(e0, sa.Const(0)):
                v = self.munch_expr(e)
                return v
            case sa.Sub(e0, sa.Const(c1)):
                v0 = self.munch_expr(e0)
                return sr.Inst.binary(sr.Opcode.ADDI, v0, sr.Imm(-c1))
            case sa.Sub(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return sr.Inst.binary(sr.Opcode.SUB, v0, v1)

            case sa.Mul(sa.Const(c0), sa.Const(c1)):
                return sr.Inst.unary(sr.Opcode.LI, sr.Imm(c0 * c1))
            case sa.Mul(e, sa.Const(0)):
                return sr.Imm(0)
            case sa.Mul(e, sa.Const(1)):
                v = self.munch_expr(e)
                return v
            case sa.Mul(e, sa.Const(2)):
                v = self.munch_expr(e)
                return sr.Inst.binary(sr.Opcode.ADD, v, v)
            case sa.Mul(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return sr.Inst.binary(sr.Opcode.MUL, v0, v1)

            case sa.Div(sa.Const(c0), sa.Const(c1)) if c1 != 0:
                return sr.Inst.unary(sr.Opcode.LI, sr.Imm(c0 // c1))
            case sa.Div(e, sa.Const(0)):
                return sr.Inst.unary(sr.Opcode.LI, sr.Imm(0))
            case sa.Div(e, sa.Const(2)):
                v = self.munch_expr(e)
                v1 = sr.Inst.binary(sr.Opcode.SRLI, v, sr.Imm(63))
                v2 = sr.Inst.binary(sr.Opcode.ADD, v, v1)
                v3 = sr.Inst.binary(sr.Opcode.SRAI, v2, sr.Imm(1))
                self.output.append(v1)
                self.output.append(v2)
                return v3
            case sa.Div(e, sa.Const(3)):
                v = self.munch_expr(e)
                v1 = sr.Inst.unary(sr.Opcode.LI, sr.Imm((2**64+2)//3, display=hex))
                v2 = sr.Inst.binary(sr.Opcode.MULH, v1, v)
                v3 = sr.Inst.binary(sr.Opcode.SRLI, v, sr.Imm(63))
                v4 = sr.Inst.binary(sr.Opcode.ADD, v2, v3)
                self.output.append(v1)
                self.output.append(v2)
                self.output.append(v3)
                return v4
            case sa.Div(e, sa.Const(n)) if n & (n - 1) == 0:
                k = n.bit_length() - 1
                v = self.munch_expr(e)
                v0 = sr.Inst.binary(sr.Opcode.SRAI, v, sr.Imm(k-1))
                v1 = sr.Inst.binary(sr.Opcode.SRLI, v0, sr.Imm(64-k))
                v2 = sr.Inst.binary(sr.Opcode.ADD, v, v1)
                v3 = sr.Inst.binary(sr.Opcode.SRAI, v2, sr.Imm(k))
                self.output.append(v0)
                self.output.append(v1)
                self.output.append(v2)
                return v3
            case sa.Div(e0, e1):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return sr.Inst.binary(sr.Opcode.DIV, v0, v1)

            case sa.Inst(cmp, (sa.Const(c0), sa.Const(c1))) if iscmp(cmp):
                return sr.Inst.unary(sr.Opcode.LI, sr.Imm(cmp_e(cmp, c0, c1)))
            case sa.Inst(cmp, (e0, sa.Const(0))) if iscmp(cmp):
                v0 = self.munch_expr(e0)
                return sr.Inst.unary(cmp_z(cmp), v0)
            case sa.Inst(cmp, (e0, e1)) if iscmp(cmp):
                v0 = self.munch_expr(e0)
                v1 = self.munch_expr(e1)
                return sr.Inst.binary(cmp_r(cmp), v0, v1)

            case sa.Odd(e):
                v0 = self.munch_expr(e)
                v1 = sr.Inst.binary(sr.Opcode.ANDI, v0, sr.Imm(1))
                self.output.append(v1)
                return sr.Inst.unary(sr.Opcode.SNEZ, v1)

            case sa.Call(proc):
                f = sr.Inst.unary(sr.Opcode.LA, sr.Sym(proc))
                self.output.append(f)
                return sr.Inst.unary(sr.PseudoOpcode.CALL, f)

            case sa.Store(e, var):
                v = self.munch_expr(e)
                a = sr.Inst.unary(sr.Opcode.LA, sr.Sym(var))
                self.output.append(a)
                return sr.Inst.binary(sr.Opcode.SD, v, sr.Off(a, sr.Imm(0)))

            case sa.Load(var):
                a = sr.Inst.unary(sr.Opcode.LA, sr.Sym(var))
                self.output.append(a)
                return sr.Inst.unary(sr.Opcode.LD, sr.Off(a, sr.Imm(0)))

            case _:
                print(f'{inst=}')
                raise RuntimeError(f'Unsupported opcode: {inst.opcode}')

    def munch_expr(self, value):
        if not isinstance(value, Param):
            if value.done and not value.iseffectful():
                return value.result
        inst = self.do_munch_expr(value)
        value.done = True
        value.result = inst
        if not isinstance(inst, Param):
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

        newblock = sa.Block(block.label)
        self.blockmap[block] = newblock
        match block.cont:
            case sa.ReturnCont():
                newblock.cont = sr.ReturnCont()
            case sa.JumpCont(target=target):
                newblock.cont = sr.Cont.jump(target.target)
                newblock.cont.target.args = {p: args[a] for p, a in target.args.items()}
            case sa.BranchCont(value=value, ttrue=ttrue, tfals=tfals):
                self.output = []
                value = self.munch_expr(value)
                self.outputs.insert(0, self.output)
                newblock.cont = sr.Cont.branch(value, ttrue.target, tfals.target)
                newblock.cont.ttrue.args = {p: args[a] for p, a in ttrue.args.items()}
                newblock.cont.tfals.args = {p: args[a] for p, a in tfals.args.items()}
        newblock.insts = [a for b in reversed(self.outputs) for a in b]
        newblock.params = block.params[:]
        newblock.preds = block.preds[:]
        newblock.succs = block.succs[:]
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
    sel.blockmap = {}
    blocks = []
    for block in proc.blocks:
        newblock = sel.munch_block(block)
        blocks.append(newblock)

    newproc = Procedure(proc.label, blocks, procs)
    sel.fixblocks(newproc)
    return newproc
