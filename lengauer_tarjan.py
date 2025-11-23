from collections import defaultdict, deque
import itertools
import sys

from ssa import Opcode, ContinuationType, Value

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

class LengauerTarjan:
    def __init__(self, graph):
        self.graph = graph
        self.ancestor = [self.graph.nodes[i] for i in range(len(graph.nodes))]
        self.semi = [self.graph.nodes[i] for i in range(len(graph.nodes))]
        self.label = [self.graph.nodes[i] for i in range(len(graph.nodes))]
        self.nodes = []
        self.tonode = {}
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
        go(self.graph.root)
        self.graph.root.parent = self.graph.root
        self.nodes = list(reversed(nodes))
        for node in self.nodes:
            if hasattr(node, 'block'):
                self.tonode[node.block] = node

    def find(self, v):
        if self.ancestor[v.index] == v:
            return v
        r = self.find(self.ancestor[v.index])
        if self.semi[self.label[self.ancestor[v.index].index].dfs].dfs < self.semi[self.label[v.index].dfs].dfs:
            self.label[v.index] = self.label[self.ancestor[v.index].index]
        self.ancestor[v.index] = r
        return r

    def eval(self, v):
        if self.ancestor[v.index] != v:
            self.find(v)
            return self.label[v.index]
        return v

    def semidominators(self):
        for v in self.nodes:
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
        return self.semi

    def idominators(self):
        self.idom = {}
        for v in reversed(self.nodes):
            s_v = self.semi[v.dfs]
            if s_v == v.parent:
                self.idom[v] = s_v
            else:
                w = self.eval(v)
                if self.semi[w.dfs] == s_v:
                    self.idom[v] = s_v
                else:
                    self.idom[v] = self.idom[w]
        return self.idom

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
        for v in self.nodes:
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

    def old_calcphiuses(self):
        phiuses = defaultdict(set)
        seen = set()
        def go(v):
            if v in seen:
                return
            seen.add(v)
            for u in v.children:
                go(u)
            for i, inst in enumerate(v.block.insts):
                if inst.opcode == Opcode.UPSILON:
                    phiuses[inst.phi.block.insts[inst.phi.index]].add(Value(v.block, i))
        go(self.graph.root)
        self.phiuses = dict(phiuses.items())

    def calcphiuses(self):
        self.phiuses = defaultdict(set)
        self.phidefs = defaultdict(set)
        seen = set()
        def go(v):
            if v in seen:
                return
            seen.add(v)
            for u in v.children:
                go(u)
            for i, inst in enumerate(v.block.insts):
                if inst.opcode == Opcode.UPSILON:
                    self.phiuses[self.tonode[inst.phi.block]].add(Value(v.block, i))
                elif inst.opcode == Opcode.PHI:
                    self.phidefs[v].add(Value(v.block, i))
        go(self.graph.root)

    def calcshadowvars(self):
        killset = {}
        shadows = []
        for v in self.nodes:
            killset[v] = set()
            for i, inst in enumerate(v.block.insts):
                if inst.opcode == Opcode.UPSILON:
                    shadows.append(Value(v.block, i))
                    killset[v].add(Value(v.block, i))
        for v in self.nodes:
            print(f'killset({v.block.name})=' + ' '.join(map(str, killset[v])))
        print('shadows=[' + ' '.join(map(str, shadows)) + ']')
        edgeups = defaultdict(set)
        worklist = deque()
        for upsilon in shadows:
            block = self.tonode[upsilon.block]
            for u in block.children:
                edge = (block, u)
                if edge in self.backedges:
                    continue
                print(edge)
                if upsilon not in edgeups[edge]:
                    edgeups[edge].add(upsilon)
                    worklist.append(edge)
        while worklist:
            (a, b) = worklist.popleft()
            print(f'{a=} {b=}')
            current = edgeups[(a, b)]
            for c in b.children:
                e2 = (b, c)
                if e2 in self.backedges:
                    continue
                print(f'{a=} {b=} {c=} current=' + ' '.join(map(str, current)))
                new = set(current)
                new.difference_update(killset[b])
                print(f'{a=} {b=} {c=} new=' + ' '.join(map(str, new)))
                if not edgeups[e2].issuperset(new):
                    edgeups[e2] |= new
                    worklist.append(e2)
        phiuses = {v: set() for v in self.nodes}
        for (a, b), ups in edgeups.items():
            if (a, b) not in self.backedges:
                phiuses[a] |= ups

    def liveness(self):
        self.liveness_done = set()
        self.livein = {}
        self.liveout = {}
        for v in self.nodes:
            self.livein[v] = set()
            self.liveout[v] = set()
        self.liveness_dfs(self.graph.root)
        for loop in self.loops.values():
            self.looptree_dfs(loop)

    def liveness_dfs(self, v):
        for u in v.children:
            if (v, u) not in self.backedges and u not in self.liveness_done:
                self.liveness_dfs(u)

        live = set()
        for u in v.children:
            if (v, u) not in self.backedges:
                live |= self.livein[u] - self.phidefs[u]
        self.liveout[v] = set(live)
        for i, inst in reversed(list(enumerate(v.block.insts))):
            if inst.opcode != Opcode.PHI:
                inst_value = Value(block=v.block, index=i)
                for value in inst.args:
                    live.add(value)
                live.discard(inst_value)
        self.livein[v] = live | self.phidefs[v]
        self.liveness_done.add(v)

    def looptree_dfs(self, loop):
        if len(loop) > 1:
            lhdr = self.loopheader[loop]
            liveloop = self.livein[lhdr] - self.phidefs[lhdr]
            for child in self.lchildren[loop]:
                chdr = self.loopheader[child]
                self.livein[chdr] |= liveloop
                self.liveout[chdr] |= liveloop
                self.looptree_dfs(child)

    def debug(self, file=None):
        if file is None:
            with open('dominator.dot', 'w') as file:
                self._debug(file)
        else:
            self._debug(file)

    def _debug(self, file):
        names = {}
        counter = itertools.count(1)
        for node in self.graph.nodes:
            for i, inst in enumerate(node.block.insts):
                if inst not in names:
                    names[inst] = names[node.block, i] = 'v' + str(next(counter))
        idom = {k.index: v.index for k, v in self.idom.items()}
        print('digraph {', file=file)
        #print('subgraph cluster_program {', file=file)
        #print('label="CFG"', file=file)
        for node in self.graph.nodes:
            print('\t', node.index, f'[shape=box nojustify=true label="', file=file, end='')
            print(f'{node.block.name}:', file=file, end='\\l')
            for inst in node.block.insts:
                inst.debug(names, file=file, end='\\l')
            if node.block.cont is not None:
                node.block.cont.debug(names, end='\\l', file=file)
            else:
                print('\tNo jump', end='\\l', file=file)
            #defs = ', '.join(sorted(list(names[k.block, k.index] for k in self.defs[node])))
            #phidefs = ', '.join(sorted(list(names[k.block, k.index] for k in self.phidefs[node])))
            #phiuses = [use for inst in node.block.insts if inst.opcode == Opcode.PHI for use in self.phiuses[inst]]
            phidefs = ', '.join(sorted(list(names[k.block, k.index] for k in self.phidefs[node])))
            phiuses = ', '.join(sorted(list(names[k.block, k.index] for k in self.phiuses[node])))
            livein = ', '.join(sorted(list(names[k.block, k.index] for k in self.livein[node])))
            liveout = ', '.join(sorted(list(names[k.block, k.index] for k in self.liveout[node])))
            #upward = ', '.join(sorted(list(names[k.block, k.index] for k in self.upward[node])))
            #useset = ', '.join(sorted(list(names[k.block, k.index] for k in self.useset[node])))
            #livein = ', '.join(sorted(list(names[k.block, k.index] for k in self.livein[node])))
            #if self.defs[node]:
            #    print(f'Defs = {{{defs}}}', end='\\l', file=file)
            if phidefs:
                print(f'Phidefs = {{{phidefs}}}', end='\\l', file=file)
            if phiuses:
                print(f'Phiuses = {{{phiuses}}}', end='\\l', file=file)
            if livein:
                print(f'Livein = {{{livein}}}', end='\\l', file=file)
            if liveout:
                print(f'Liveout = {{{liveout}}}', end='\\l', file=file)
            #if self.upward[node]:
            #    print(f'Upward = {{{upward}}}', end='\\l', file=file)
            #print(f'Useset = {{{useset}}}', end='\\l', file=file)
            #print(f'Livein = {{{livein}}}', end='\\l', file=file)
            print('" xlabel="', file=file, end='')
            print('"]', file=file)
            for i in range(len(node.children)):
                print('\t', node.index, '->', node.children[i].index, file=file)
        for i, j in idom.items():
            print('\t', i, '->', j, '[color=red,constraint=false]', file=file)
        print('}', file=file)

import unittest

class TestLengauerTarjanSSA(unittest.TestCase):

    class TestGraph:
        class Node:
            def __init__(self, index, block):
                self.preds = []
                self.children = []
                self.index = index
                self.block = block

            def __repr__(self):
                return self.block.name
                #if hasattr(self, 'dfs'):
                #    return f'(i:{self.index},d:{self.dfs})'
                #return f'(i:{self.index})'

        def __init__(self, proc):
            bkwd = {}
            self.nodes = []
            for i, block in enumerate(proc.blocks):
                self.nodes.append(self.Node(i, block))
                bkwd[block] = i
            seen = set()
            def go(node):
                if node in seen:
                    return
                seen.add(node)
                if node.block.cont.type == ContinuationType.JUMP:
                    node.children = [self.nodes[bkwd[node.block.cont.args[0]]]]
                elif node.block.cont.type == ContinuationType.BRANCH:
                    btrue = node.block.cont.args[1]
                    bfals = node.block.cont.args[2]
                    node.children = [self.nodes[bkwd[btrue]],
                                     self.nodes[bkwd[bfals]]]
                else:
                    node.children = []
                for child in node.children:
                    go(child)
                node.preds = [self.nodes[bkwd[b]] for b in node.block.preds]
            go(self.nodes[0])
            self.root = self.nodes[0]

        def __repr__(self):
            return f'TestGraph({self.nodes=}, {self.root=})'

    def do_test(self, source, debug=False, name=None):
        from parse import parse
        from checkvars import checkvars
        prog = parse(source)
        const, escaped, free = checkvars(prog)
        from convertssa import convertssa
        proc = convertssa(prog, const, escaped, free)
        for name, proc in [(name, proc), *proc.procedures.items()]:
            print(name)
            proc.debug()
            graph = self.TestGraph(proc)
            lt = LengauerTarjan(graph)
            lt.semidominators()
            idom = lt.idominators()
            lt.calcbackedges()
            lt.calcloops()
            lt.calclnf()
            lt.dominatortree()
            lt.frontier()
            lt.calcphiuses()
            lt.calcshadowvars()
            lt.liveness()
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
        self.do_test(prog, debug=False)

    def test_prog0(self):
        from examples import prog0 as prog
        self.do_test(prog, debug=True)

    def test_prog0a(self):
        from examples import prog0a as prog
        self.do_test(prog, debug=False)

    def test_prog1(self):
        from examples import prog1 as prog
        self.do_test(prog, debug=False)

    def test_prog2(self):
        from examples import prog2 as prog
        self.do_test(prog, debug=False)

    def test_prog3(self):
        from examples import prog3 as prog
        self.do_test(prog, debug=False)

    def test_prog4(self):
        from examples import prog4 as prog
        self.do_test(prog, debug=False)

    def test_prog5(self):
        from examples import prog5 as prog
        self.do_test(prog, debug=False)

class TestLengauerTarjan(unittest.TestCase):

    class TestGraph:
        class Node:
            def __init__(self, index):
                self.preds = []
                self.children = []
                self.index = index

            def __repr__(self):
                if hasattr(self, 'dfs'):
                    return f'(i:{self.index},d:{self.dfs})'
                return f'(i:{self.index})'

        def __init__(self, nodes, edges):
            self.nodes = []
            for i, v in enumerate(nodes):
                self.nodes.append(self.Node(i))
            for u, v in edges:
                self.nodes[v].preds.append(self.nodes[u])
                self.nodes[u].children.append(self.nodes[v])
            self.root = self.nodes[0]

        def __repr__(self):
            return f'TestGraph({self.nodes=}, {self.root=})'

    def do_test_lt(self, nverts, edges, expected):
        graph = self.TestGraph(list(range(nverts)), edges)
        lt = LengauerTarjan(graph)
        lt.semidominators()
        idom = lt.idominators()
        idom = {k.index: v.index for k, v in idom.items()}
        self.assertEqual(idom, expected)
        return graph, idom

    def test_lt0(self):
        nverts = 3
        edges = [(0,1),(0,2)]
        expected = {0:0, 1:0, 2:0}
        self.do_test_lt(nverts, edges, expected)

    def test_lt1(self):
        nverts = 4
        edges = [(0,1),(0,2),(1,3),(2,3)]
        expected = {0:0, 1:0, 2:0, 3:0}
        self.do_test_lt(nverts, edges, expected)

    def test_lt2(self):
        nverts = 5
        edges = [(0,1),(0,2),(1,3),(2,3),(3,4)]
        expected = {0:0, 1:0, 2:0, 3:0, 4:3}
        self.do_test_lt(nverts, edges, expected)
        edges.append((3,0))
        self.do_test_lt(nverts, edges, expected)

    def test_lt4(self):
        nverts = 9
        edges = [
            (0,1),(0,2),(1,4),(2,3),(2,4),(3,5),
            (4,6),(5,3),(5,7),(6,8),(7,5),(7,8)
        ]
        expected = {0:0, 1:0, 2:0, 4:0, 8:0, 6:4, 3:2, 5:3, 7:5}
        self.do_test_lt(nverts, edges, expected)

    def test_lt5(self):
        nverts = 7
        edges = [(0,1),(0,2),(1,2),(2,3),(3,4),(1,5),(5,6),(6,4)]
        expected = {0:0, 1:0, 2:0, 3:2, 4:0, 5:1, 6:5}
        self.do_test_lt(nverts, edges, expected)

    # Misra's example
    def test_misra(self):
        nverts = 13
        edges = [
            (0,1),(0,2),(0,3),(1,4),(2,1),(2,4),(2,5),(3,6),(3,7),
            (4,12),(5,8),(6,9),(7,9),(7,10),(8,5),(8,11),(9,11),(10,9),
            (11,0),(11,9),(12,8)
        ]
        expected = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0, 6:3,
                    7:3, 8:0, 9:0, 10:7, 11:0, 12:4}
        self.do_test_lt(nverts, edges, expected)

    # Cooper, Harvey, and Kennedy's examples
    def test_chk1(self):
        nverts = 5
        edges = [(0,1),(0,2),(1,3),(2,4),(3,4),(4,3)]
        expected = {0:0, 1:0, 2:0, 3:0, 4:0}
        self.do_test_lt(nverts, edges, expected)

    def test_chk2(self):
        nverts = 6
        edges = [(0,1),(0,2),(1,5),(2,4),(2,3),(5,4),(4,5),(4,3),(3,4)]
        expected = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0}
        self.do_test_lt(nverts, edges, expected)

    # Georgiadis, Tarjan, and Werneck's examples
    @staticmethod
    def linearvit(k):
        nverts = 3 + k
        edges = [(0,1),(0,2),(1,3),(2,(3+k-1))]
        for i in range(k - 1):
            edges.append(((3+i),(3+i+1)))
            edges.append(((3+i+1),(3+i)))
        expected = {i:0 for i in range(nverts)}
        return nverts, edges, expected

    @staticmethod
    def itworst(k):
        # w_i = 4*i + 1
        # x_i = 4*i + 2
        # y_i = 4*i + 3
        # z_i = 4*i + 4
        nverts = 1 + 4*k
        #         r,w0  r,x0  r,zn-1  xn-1,y0   yn-1,z0
        edges = [(0,1),(0,2),(0,4*k),(4*k-2,3),(4*k-1,4)]
        for i in range(k-1):
            edges.append(( (4*i+1) , (4*(i+1)+1) ))
            edges.append(( (4*i+2) , (4*(i+1)+2) ))
            edges.append(( (4*i+3) , (4*(i+1)+3) ))
            edges.append(( (4*i+4) , (4*(i+1)+4) ))
            edges.append(( (4*(i+1)+4) , (4*i+4) ))
        for i in range(k):
            for j in range(k):
                edges.append(( (4*i+3) , (4*j+1) ))
        expected = {i:0 for i in range(nverts)}
        for i in range(k-1):
            # xi+1: xi
            expected[4*(i+1)+2] = 4*i+2
            # yi+1: yi
            expected[4*(i+1)+3] = 4*i+3
        # y0: xn-1
        expected[3] = 4*k-2
        return nverts, edges, expected

    def test_linearvit(self):
        for i in range(2, 30):
            nverts, edges, expected = self.linearvit(i)
            self.do_test_lt(nverts, edges, expected)

    def test_itworst(self):
        for i in range(2, 30):
            nverts, edges, expected = self.itworst(i)
            self.do_test_lt(nverts, edges, expected)

if __name__ == '__main__':
    nverts, edges, expected = TestLengauerTarjan.itworst(10)
    graph = TestLengauerTarjan.TestGraph(list(range(nverts)), edges)
    lt = LengauerTarjan(graph)
    lt.semidominators()
    idom = lt.idominators()
    idom = {k.index: v.index for k, v in idom.items()}
    with open('dominator.dot', 'w') as f:
        debug_dominator_tree(graph, idom, f)
