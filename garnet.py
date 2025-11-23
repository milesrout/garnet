from copy import copy
import collections
import enum
import itertools
import unittest

import garnetast as ast
from parse import parse
from checkvars import checkvars
from convertssa import convertssa

def main():
    from examples import prog1 as source
    prog = parse(source)
    const, escaped, free = checkvars(prog)
    result = convertssa(prog, const, escaped, free)

if __name__ == '__main__':
    main()
