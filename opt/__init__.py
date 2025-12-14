from util import trace
import ssa.abstract as s

class Optimiser:
    def __init__(self, proc):
        self.proc = proc

    def peep_expr(self, block, inst):
        match inst.find():

            case s.Add(s.Const(c1), s.Const(c2)):
                inst.replace(s.Inst.const(c1 + c2))
            case s.Add(s.Const(c), e):
                inst.replace(s.Inst.add(inst.arg_1, inst.arg_0))
            case s.Add(e, s.Const(0)):
                inst.replace(e)

            case s.Mul(s.Const(c1), s.Const(c2)):
                inst.replace(s.Inst.const(c1 * c2))
            case s.Mul(s.Const(c), e):
                inst.replace(s.Inst.mul(inst.arg_1, inst.arg_0))
            case s.Mul(e1, s.Const(0) as e2):
                inst.replace(e2)
            case s.Mul(e1, s.Const(1)):
                inst.replace(e1)
            case s.Mul(e1, s.Const(2)):
                e2 = s.Inst.const(1)
                block.emit_before(inst, [e2])
                inst.replace(s.Inst.binary(s.Opcode.SLL, e1, e2))

            case s.Div(s.Const(c1), s.Const(c2)) if c2 != 0:
                inst.replace(s.Inst.const(c1 // c2))
            case s.Div(e1, s.Const(2)):
                e2 = s.Inst.const(63)
                e3 = s.Inst.binary(s.Opcode.SRL, e1, e2)
                e4 = s.Inst.binary(s.Opcode.ADD, e1, e3)
                e5 = s.Inst.const(1)
                e6 = s.Inst.binary(s.Opcode.SRA, e4, e5)
                block.emit_before(inst, [e2, e3, e4, e5])
                inst.replace(e6)
            case s.Div(e1, s.Const(3)):
                e2 = s.Inst.const((2**64 + 2) // 3, display=hex)
                e3 = s.Inst.binary(s.Opcode.MULH, e1, e2)
                e4 = s.Inst.const(63)
                e5 = s.Inst.binary(s.Opcode.SRL, e1, e4)
                e6 = s.Inst.binary(s.Opcode.ADD, e3, e5)
                block.emit_before(inst, [e2, e3, e4, e5])
                inst.replace(e6)
            case s.Div(e1, s.Const(n)) if n & (n-1) == 0:
                k = n.bit_length() - 1
                e2 = s.Inst.const(k-1)
                e3 = s.Inst.binary(s.Opcode.SRA, e1, e2)
                e4 = s.Inst.const(64-k)
                e5 = s.Inst.binary(s.Opcode.SRL, e3, e4)
                e6 = s.Inst.binary(s.Opcode.ADD, e1, e5)
                e7 = s.Inst.const(k)
                e8 = s.Inst.binary(s.Opcode.SRA, e6, e7)
                block.emit_before(inst, [e2, e3, e4, e5, e6, e7])
                inst.replace(e8)

            case _:
                return True

    def peephole(self):
        for block in self.proc.blocks:
            for i, inst in enumerate(block.insts):
                result = False
                while not result:
                    result = self.peep_expr(block, block.insts[i])

    def result(self):
        return self.proc

def optimise(proc):
    for i in range(len(proc.procedures)):
        proc.procedures[i] = optimise(proc.procedures[i])
    return _optimise(proc)

def _optimise(proc):
    opt = Optimiser(proc)
    opt.peephole()
    return opt.result()
