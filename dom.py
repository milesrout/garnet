import enum
from collections import defaultdict, deque
import itertools
import sys
import unittest

from ssa.riscv64 import Cont, Block

__names__ = ['calcdominators']

class Node:
    def __init__(self, block, index):
        self.preds = []
        self.children = []
        self.block = block
        self.index = index

    def __repr__(self):
        return f'Node({self.block.label})'

class LengauerTarjan:
    @classmethod
    def _graph(self, proc):
        bkwd = {}
        nodes = []
        for i, block in enumerate(proc.blocks):
            nodes.append(Node(block, i))
            bkwd[block] = i
        seen = set()
        def go(node):
            if node in seen:
                return
            seen.add(node)
            node.children = [nodes[bkwd[target]] for target in node.block.cont.targets]
            for child in node.children:
                go(child)
            node.preds = [nodes[bkwd[b]] for b in node.block.preds]
        go(nodes[0])
        return nodes, nodes[0]

    def __init__(self, proc):
        self.proc = proc
        self.nodes, self.root = self._graph(proc)

    def splitcrit(self):
        for v in self.nodes:
            if len(v.children) > 1:
                for i, u in enumerate(v.children):
                    if len(u.preds) > 1:
                        b = Block()
                        b.label += '_split'
                        b.cont = Cont.jump(u.block)
                        b.preds = [v.block]
                        b.succs = [u.block]
                        av = {}
                        aw = {}
                        for j, pu in enumerate(u.block.params):
                            pw = b.param()
                            aw[pu] = pw
                            av[pw] = v.block.cont.edges[i].args[pu]
                        v.block.cont.edges[i].target = b
                        v.block.cont.edges[i].args = av
                        b.cont.target.args = aw
                        w = Node(b, len(self.nodes))
                        self.nodes.append(w)
                        self.proc.blocks.append(b)
                        j = u.preds.index(v)
                        u.preds[j] = w
                        w.children.append(u)
                        v.children[i] = w
                        w.preds.append(v)
                        v.block.succs[v.block.succs.index(u.block)] = b
                        u.block.preds[u.block.preds.index(v.block)] = b

    def dfs(self):
        counter = itertools.count(0)
        seen = set()
        nodes = []
        def go(v):
            if v in seen:
                return
            v.dfs = next(counter)
            nodes.append(v)
            seen.add(v)
            for u in v.children:
                go(u)
                u.parent = v
        go(self.root)
        self.root.parent = self.root
        self.dfsnodes = list(reversed(nodes))

    def find(self, v):
        a = self.ancestor[v.index]
        if a == v:
            return v
        r = self.find(a)
        if self.semi[self.label[a.index].dfs].dfs < self.semi[self.label[v.index].dfs].dfs:
            self.label[v.index] = self.label[a.index]
        self.ancestor[v.index] = r
        return r

    def eval(self, v):
        if self.ancestor[v.index] != v:
            self.find(v)
            return self.label[v.index]
        return v

    def semidominators(self):
        self.ancestor = [self.nodes[i] for i in range(len(self.nodes))]
        self.semi = [self.nodes[i] for i in range(len(self.nodes))]
        self.label = [self.nodes[i] for i in range(len(self.nodes))]
        for v in self.dfsnodes:
            self.semi[v.dfs] = v.parent
            for u in v.preds:
                if u.dfs < v.dfs:
                    if u.dfs < self.semi[v.dfs].dfs:
                        self.semi[v.dfs] = u
                else:
                    su = self.eval(u)
                    if self.semi[su.dfs].dfs < self.semi[v.dfs].dfs:
                        self.semi[v.dfs] = self.semi[su.dfs]
            self.ancestor[v.index] = v.parent

    def idominators(self):
        self.idom = {}
        for v in reversed(self.dfsnodes):
            s_v = self.semi[v.dfs]
            if s_v == v.parent:
                self.idom[v] = s_v
            else:
                w = self.eval(v)
                if self.semi[w.dfs] == s_v:
                    self.idom[v] = s_v
                else:
                    self.idom[v] = self.idom[w]

    def dominators(self):
        dom = {v: set() for v in self.dfsnodes}
        for k, v in self.idom.items():
            dom[v].add(k)
        self.dom = dom

    def dominates(self, u, v):
        """Returns whether u dominates v"""
        w = v
        while self.idom[w] != w:
            if w == u:
                return True
            w = self.idom[w]
        return w == u

    def calcbackedges(self):
        self.backedges = set()
        for v in self.dfsnodes:
            for u in v.children:
                if self.dominates(u, v):
                    self.backedges.add((v, u))

    def calcloops(self):
        self.loops = {}
        self.loopheader = {}
        for v, u in self.backedges:
            nodes = {u, v}
            stack = [v]
            while stack:
                x = stack.pop()
                for p in x.preds:
                    if p not in nodes:
                        nodes.add(p)
                        stack.append(p)
            self.loops[u, v] = frozenset(nodes)
            self.loopheader[self.loops[u, v]] = u

    def calclnf(self):
        loops = list(self.loops.values())
        loops.sort(key=len)

        parent = defaultdict(lambda: None)
        children = defaultdict(list)

        for l1 in loops:
            for l2 in loops:
                if l1 is l2:
                    continue
                if l1.issubset(l2):
                    if parent[l1] is None or len(l2) < len(parent[l1]):
                        parent[l1] = l2

        roots = set(l for l in loops if parent[l] is None)
        for l in loops:
            if parent[l]:
                children[parent[l]].append(l)

        self.lparent = parent
        self.lchildren = children

    def dominatortree(self):
        self.dtree = {}
        for node, idom in self.idom.items():
            if node is idom:
                self.dtreeroot = node
            else:
                self.dtree[idom] = self.dtree.get(idom, set())
                self.dtree[idom].add(node)

    def frontier(self):
        self.frontier = {}
        def go(b):
            assert self.frontier.get(b) is None
            self.frontier[b] = set()
            for u in self.dtree.get(b, set()):
                go(u)
            for y in b.children:
                if b != self.idom[y]:
                    self.frontier[b].add(y)
            for c in self.dtree.get(b, set()):
                for w in self.frontier[c]:
                    if b != self.idom[w]:
                        self.frontier[b].add(w)
        go(self.dtreeroot)

    def result(self):
        idom = {a.block: b.block for a, b in self.idom.items()}
        dom = {a.block: {c.block for c in b} for a, b in self.dom.items()}
        dtree = {a.block: {c.block for c in b} for a, b in self.dtree.items()}
        dtreeroot = self.dtreeroot.block
        frontier = {a.block: {c.block for c in b} for a, b in self.frontier.items()}
        result = DominationResult(
            idom=idom, dom=dom,
            dtree=dtree, dtreeroot=dtreeroot,
            frontier=frontier)
        return result

class DominationResult:
    def __init__(self, *, idom, dom, dtree, dtreeroot, frontier):
        self.idom = idom
        self.dom = dom
        self.dtree = dtree
        self.dtreeroot = dtreeroot
        self.frontier = frontier

def calcdominators(proc):
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
    return lt.result()
