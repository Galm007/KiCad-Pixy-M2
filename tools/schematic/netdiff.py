"""Compare two kicadsexpr netlists electrically: nets, their members, and parts.

    python3 netdiff.py before.net after.net      # exit 1 on any difference
"""
import sys
from schlib import parse, kids, kid, sval


def load(path):
    t = open(path).read()
    tree, _ = parse(t, t.index('('))
    nets = {}
    for n in kids(kid(tree, 'nets'), 'net'):
        name = sval(kid(n, 'name')[1])
        nets[name] = sorted((sval(kid(m, 'ref')[1]), sval(kid(m, 'pin')[1])) for m in kids(n, 'node'))
    comps = {}
    for c in kids(kid(tree, 'components'), 'comp'):
        ref = sval(kid(c, 'ref')[1])
        fields = {sval(f[1][1]) if isinstance(f[1], list) else '': sval(f[2]) if len(f) > 2 else ''
                  for f in kids(kid(c, 'fields') or [], 'field')}
        comps[ref] = (sval(kid(c, 'value')[1]),
                      sval(kid(c, 'footprint')[1]) if kid(c, 'footprint') else '',
                      tuple(sorted(fields.items())))
    return nets, comps


a, b = load(sys.argv[1]), load(sys.argv[2])
bad = 0
for what, x, y in (('net', a[0], b[0]), ('part', a[1], b[1])):
    for k in sorted(set(x) | set(y)):
        if x.get(k) != y.get(k):
            bad += 1
            print('%s %s:\n  - %s\n  + %s' % (what, k, x.get(k), y.get(k)))
print('%d nets, %d parts; %d differences' % (len(b[0]), len(b[1]), bad))
sys.exit(1 if bad else 0)
