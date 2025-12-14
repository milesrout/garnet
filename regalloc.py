import enum
from collections import defaultdict, deque
import itertools
import sys
import unittest

import ssa.riscv64 as r
from riscv64 import REGALLOC, Register

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
            if block.label.endswith('_cthen'):
                params = block.params[1:]
            else:
                params = block.params
            assignment = {p: REGALLOC[i] for i, p in enumerate(params)}
            if block.label.endswith('_cthen'):
                assignment[block.params[0]] = Register.A0
            assigned = set(assignment.values())
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
                    b = next(c for c in REGALLOC if c not in assigned)
                    assignment[inst] = b
                    if inst in last_use:
                        assigned.add(assignment[inst])
            self.colours[block] = {k: r.Reg(v) for k, v in assignment.items()}
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
                cu = REGALLOC.index(self.colours[u][ru].reg)
                cv = REGALLOC.index(self.colours[v][rv].reg)
                tmp = max([tmp, cu, cv])
                if cu != cv:
                    movs.append((cv, cu))
            if not len(movs):
                return []
            tmp += 1
            movs = parallelmoves(movs, tmp)
            return [r.Inst.binary(r.Opcode.MV,
                                  r.Reg(REGALLOC[dst]),
                                  r.Reg(REGALLOC[src]))
                    for (src, dst) in movs]
        for v in self.proc.blocks:
            if len(v.succs) > 1:
                for i, u in enumerate(v.succs):
                    assert len(u.preds) == 1
                    u.insts[:0] = do(v.cont.edges[i], v, u)
            elif len(v.succs) == 1:
                v.insts.extend(do(v.cont.edges[0], v, v.succs[0]))

    def result(self):
        return self.colours
