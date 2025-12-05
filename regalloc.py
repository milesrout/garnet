import enum
from collections import defaultdict, deque
import itertools
import sys
import unittest

import ssa.riscv64 as r

class ParMove(enum.Enum):
    NOTMOVED = enum.auto()
    MOVING = enum.auto()
    MOVED = enum.auto()

def parallelmoves(moves, tmp):
    state = [ParMove.NOTMOVED for _ in range(len(moves))]
    results = []
    def pmov1(i):
        if moves[i][0] != moves[i][1]:
            state[i] = ParMove.MOVING
            for j in range(len(moves)):
                if moves[j][0] == moves[i][1]:
                    match state[j]:
                      case ParMove.NOTMOVED:
                        pmov1(j)
                      case ParMove.MOVING:
                        results.append((moves[j][0], tmp))
                        moves[j] = (tmp, moves[j][1])
                      case ParMove.MOVED:
                        pass
            results.append((moves[i][0], moves[i][1]))
            state[i] = ParMove.MOVED
    for i in range(len(moves)):
        if state[i] == ParMove.NOTMOVED:
            pmov1(i)
    return results

def regalloc(proc, dom):
    ra = RegisterAllocator(proc, dom)
    ra.allocate()
    ra.parmove()
    return ra.result()

class RegisterAllocator:
    def __init__(self, proc, dom):
        self.proc = proc
        self.dom = dom

    def allocate(self):
        self.colours = {}
        def go(block):
            # TODO: this initial assignment could be heuristically improved by
            # selecting the permutation of the assigned registers such that the
            # parameter assignments are most similar to the registers assigned
            # to the continuation arguments that target this block, if they
            # have already been computed.
            assignment = {p: i for i, p in enumerate(block.params)}
            assigned = set(range(len(block.params)))
            last_use = {}
            for i, inst in enumerate(block.insts):
                for arg in inst.args:
                    if arg.assignable:
                        last_use[arg] = inst
            for use in block.cont.uses:
                last_use[use] = block.cont
            for arg in block.cont.args:
                last_use[arg] = block.cont
            for i, inst in enumerate(block.insts):
                for arg in inst.args:
                    if arg.assignable:
                        if last_use[arg] == inst:
                            assigned.discard(assignment[arg])
                if inst.output:
                    inst_value = block.insts[i]
                    b = next(c for c in itertools.count(0) if c not in assigned)
                    assignment[inst_value] = b
                    if inst_value in last_use:
                        assigned.add(b)
            self.colours[block] = assignment
            for c in self.dom.dom[block]:
                if c != block:
                    go(c)
        go(self.proc.blocks[0])

    def parmove(self):
        def do(e, v, u):
            if not len(e.args):
                return []
            tmp = 0
            movs = []
            for ru, rv in e.args.items():
                cu = self.colours[u][ru]
                cv = self.colours[v][rv]
                tmp = max([tmp, cu, cv])
                if cu != cv:
                    movs.append((cv, cu))
            if not len(movs):
                return []
            tmp += 1
            movs = parallelmoves(movs, tmp)
            return [r.Inst.binary(r.Opcode.MV, r.Reg(dst), r.Reg(src)) for (src,dst) in movs]
        for v in self.proc.blocks:
            if len(v.succs) > 1:
                for i, u in enumerate(v.succs):
                    print(u.preds)
                    assert len(u.preds) == 1
                    u.insts[:0] = do(v.cont.edges[i], v, u)
            elif len(v.succs) == 1:
                v.insts.extend(do(v.cont.edges[0], v, v.succs[0]))

    def result(self):
        return self.colours

class TestLengauerTarjanSSA(unittest.TestCase):
    def do_test(self, source, debug=False, name=None):
        from parse import parse
        from checkvars import checkvars
        prog = parse(source)
        const, escaped, free = checkvars(prog)
        from convertssa import convertssa
        proc = convertssa(prog, const, escaped, free)
        from sel.riscv64 import inssel
        proc = inssel(proc)
        proc.debug()
        for proc in [proc, *proc.procedures]:
            lt = LengauerTarjan(proc)
            lt.splitcrit()
            lt.dfs()
            lt.semidominators()
            lt.idominators()
            lt.dominators()
            lt.calcbackedges()
            lt.calcloops()
            lt.calclnf()
            lt.dominatortree()
            lt.frontier()
            lt.allocate()
            lt.parmove()
            if debug:
                lt.debug()
                input()

    def _test_myprog1(self):
        prog = '''\
        var x , y , z ;
        begin
            x := 0 ;
            y := 1 ;
            if x == y then
            begin
                z := x ;
                z := x + x ;
                z := z ;
                z := x ;
                z := x + x ;
                y := z
            end ;
            x := y
        end .'''
        self.do_test(prog, debug=True)

    def test_prog0(self):
        from examples import prog0 as prog
        self.do_test(prog, debug=True)

    def test_prog0a(self):
        from examples import prog0a as prog
        self.do_test(prog, debug=True)

    def test_prog1(self):
        from examples import prog1 as prog
        self.do_test(prog, debug=True)

    def test_prog2(self):
        from examples import prog2 as prog
        self.do_test(prog, debug=True)

    def test_prog3(self):
        from examples import prog3 as prog
        self.do_test(prog, debug=True)

    def test_prog4(self):
        from examples import prog4 as prog
        self.do_test(prog, debug=True)

    def test_prog5(self):
        from examples import prog5 as prog
        self.do_test(prog, debug=True)

    def test_prog6(self):
        from examples import prog6 as prog
        self.do_test(prog)
