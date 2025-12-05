from copy import copy
import collections
import contextlib
import enum
import itertools
import unittest

import garnetast as ast
from parse import parse
from checkvars import checkvars
from convertssa import convertssa
from sel.riscv64 import inssel
from dom import calcdominators
from regalloc import regalloc

def main():
    from examples import prog2 as source
    prog = parse(source)
    const, escaped, free = checkvars(prog)
    proc = convertssa(prog, const, escaped, free)
    proc1 = inssel(proc)
    with open('dominator.dot', 'w') as file:
        print('digraph {', file=file)
        dom = calcdominators(proc1)
        cols = regalloc(proc1, dom)
        vis = DebugVisualiser(proc1, dom, cols)
        vis.debug(file=file)
        for subproc in proc1.procedures:
            dom = calcdominators(subproc)
            cols = regalloc(subproc, dom)
            vis = DebugVisualiser(subproc, dom, cols)
            vis.debug(file=file)
        print('}', file=file)

class DebugVisualiser:
    def __init__(self, proc, dom, cols):
        self.proc = proc
        self.dom = dom
        self.cols = cols

    def debug(self, proc=None, file=None):
        if proc is None:
            proc = self.proc
        if file is None:
            cm = open('dominator.dot', 'w')
        else:
            cm = contextlib.nullcontext(file)
        with cm as file:
            with contextlib.redirect_stdout(file):
                self._debug(proc)

    def _debug(self, proc):
        names = {}
        counter = itertools.count(1)
        for block in proc.blocks:
            for i, inst in enumerate(block.insts):
                if inst not in names:
                    if inst in self.cols[block]:
                        names[inst] = 'r' + str(self.cols[block][inst])
                    else:
                        names[inst] = 'v' + str(next(counter))
        idom = {k.label: v.label for k, v in self.dom.idom.items()}
        #print('digraph {')
        for block in proc.blocks:
            print('\t', block.label, f'[shape=box nojustify=true label="', end='')
            params = ', '.join(param.label for param in block.params)
            if params:
                params = '(' + params + ')'
            print(f'{block.label}{params}:', end='\\l')
            for inst in block.insts:
                inst.debug(names, end='\\l')
            if block.cont is not None:
                block.cont.debug(names, end='\\l')
            else:
                print('\tNo jump', end='\\l')
            def getname(value):
                if hasattr(value, 'label'):
                    return value.label
                return names[value]
            print('" xlabel="', end='')
            print('"]')
            for i in range(len(block.succs)):
                print('\t', block.label, '->', block.succs[i].label)
        for i, j in idom.items():
            print('\t', i, '->', j, '[color=red,constraint=false]')
        #print('}')

if __name__ == '__main__':
    main()
