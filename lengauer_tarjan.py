from collections import defaultdict, deque
import itertools
import sys

from ssa import Opcode, ContinuationType, InstValue, ParamValue

def debug_dominator_tree(graph, idom, name=None):
    print(f'debug_dominator_tree {name=}')
    with open(f'{name}.dot', 'w') as file:
        print('digraph {', file=file)
        for node in graph.nodes:
            print('\t', node.index, f'[label="{node.block.name}"]', file=file)
            for i in range(len(node.children)):
                print('\t', node.index, '->', node.children[i].index, '[constrant=false]', file=file)
        for node in graph.nodes:
            print('\t', f'D{node.index}', f'[label="{node.block.name}"]', file=file)
        for i, j in idom.items():
            if j: print('\t', i, '->', j, '[color=red,constraint=false]', file=file)
            print('\t', f'D{j}', '->',  f'D{i}', file=file)
        print('}', file=file)

class Node:
    def __init__(self, block, index):
        self.preds = []
        self.children = []
        self.block = block
        self.index = index

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
            if node.block.cont.type == ContinuationType.JUMP:
                btarg = node.block.cont.args[0].target
                node.children = [nodes[bkwd[btarg]]]
            elif node.block.cont.type == ContinuationType.BRANCH:
                btrue = node.block.cont.args[1].target
                bfals = node.block.cont.args[2].target
                node.children = [nodes[bkwd[btrue]], nodes[bkwd[bfals]]]
            else:
                node.children = []
            for child in node.children:
                go(child)
            node.preds = [nodes[bkwd[b]] for b in node.block.preds]
        go(nodes[0])
        return nodes, nodes[0]

    def __init__(self, proc):
        self.nodes, self.root = self._graph(proc)
        self.ancestor = [self.nodes[i] for i in range(len(self.nodes))]
        self.semi = [self.nodes[i] for i in range(len(self.nodes))]
        self.label = [self.nodes[i] for i in range(len(self.nodes))]
        self.dfsnodes = []
        self._dfs()

    def _dfs(self):
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

    def liveness(self):
        self.livein = {}
        self.liveout = {}
        for node in self.nodes:
            self.livein[node] = set()
            self.liveout[node] = set()
            for param in node.block.params:
                pvalue = ParamValue(node.block, param)
                self.livein[node].add(pvalue)
            for arg in node.block.cont.get_args():
                self.liveout[node].add(arg)

    def colour(self):
        self.colours = {}
        def go(node):
            # TODO: this initial assignment could be heuristically improved by
            # selecting the permutation of the assigned registers such that the
            # parameter assignments are most similar to the registers assigned
            # to the continuation arguments that target this block, if they
            # have already been computed.
            assignment = {ParamValue(node.block, p): i for i, p in enumerate(node.block.params)}
            assigned = set(range(len(node.block.params)))
            last_use = {}
            for i, inst in enumerate(node.block.insts):
                for arg in inst.args:
                    last_use[arg] = inst
            if node.block.cont.type == ContinuationType.BRANCH:
                last_use[node.block.cont.args[0]] = node.block.cont
            for arg in node.block.cont.get_args():
                last_use[arg] = node.block.cont
            for i, inst in enumerate(node.block.insts):
                for arg in inst.args:
                    if last_use[arg] == inst:
                        assigned.discard(assignment[arg])
                inst_value = InstValue(node.block, i)
                b = next(c for c in itertools.count(0) if c not in assigned)
                assignment[inst_value] = b
                if inst_value in last_use:
                    assigned.add(b)
            self.colours[node] = assignment
            for c in self.dom[node]:
                if c != node:
                    go(c)
        go(self.root)

    def debug(self, file=None):
        if file is None:
            with open('dominator.dot', 'w') as file:
                self._debug(file)
        else:
            self._debug(file)

    def _debug(self, file):
        names = {}
        counter = itertools.count(1)
        for node in self.nodes:
            for i, inst in enumerate(node.block.insts):
                if inst not in names:
                    names[inst] = names[node.block, i] = 'v' + str(next(counter))
        idom = {k.index: v.index for k, v in self.idom.items()}
        print('digraph {', file=file)
        for node in self.nodes:
            print('\t', node.index, f'[shape=box nojustify=true label="', file=file, end='')
            params = ', '.join(param.name for param in node.block.params)
            if params:
                params = '(' + params + ')'
            print(f'{node.block.name}{params}:', file=file, end='\\l')
            for inst in node.block.insts:
                inst.debug(names, file=file, end='\\l')
            if node.block.cont is not None:
                node.block.cont.debug(names, end='\\l', file=file)
            else:
                print('\tNo jump', end='\\l', file=file)
            livein = ', '.join(sorted(list(k.name(names) for k in self.livein[node])))
            liveout = ', '.join(sorted(list(k.name(names) for k in self.liveout[node])))
            colours = ', '.join(f'{v.name(names)}:r{i}' for v, i in self.colours[node].items())
            #if livein:
            #    print(f'Livein = {{{livein}}}', end='\\l', file=file)
            #if liveout:
            #    print(f'Liveout = {{{liveout}}}', end='\\l', file=file)
            if colours:
                print(f'Colours = {{{colours}}}', end='\\l', file=file)
            print('" xlabel="', file=file, end='')
            print('"]', file=file)
            for i in range(len(node.children)):
                print('\t', node.index, '->', node.children[i].index, file=file)
        for i, j in idom.items():
            print('\t', i, '->', j, '[color=red,constraint=false]', file=file)
        print('}', file=file)

import unittest

class TestLengauerTarjanSSA(unittest.TestCase):
    def do_test(self, source, debug=False, name=None):
        from parse import parse
        from checkvars import checkvars
        prog = parse(source)
        const, escaped, free = checkvars(prog)
        from convertssa import convertssa
        proc = convertssa(prog, const, escaped, free)
        for name, proc in [(name, proc), *proc.procedures.items()]:
            proc.debug()
            lt = LengauerTarjan(proc)
            lt.semidominators()
            lt.idominators()
            lt.dominators()
            lt.calcbackedges()
            lt.calcloops()
            lt.calclnf()
            lt.dominatortree()
            lt.frontier()
            lt.liveness()
            lt.colour()
            if debug:
                lt.debug()
                input()

    def test_myprog1(self):
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
