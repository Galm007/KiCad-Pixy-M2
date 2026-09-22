import re
def parse(text):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack=[[]]
    for t in toks:
        if t=='(': stack.append([])
        elif t==')':
            n=stack.pop(); stack[-1].append(n)
        else:
            if t.startswith('"'):
                t=('STR', t[1:-1].replace('\\"','"').replace('\\\\','\\'))
            stack[-1].append(t)
    return stack[0][0]
def sym(x): return isinstance(x,str)
def val(x):
    if isinstance(x,tuple): return x[1]
    return x
def children(node,name):
    return [c for c in node if isinstance(c,list) and c and sym(c[0]) and c[0]==name]
def child(node,name):
    c=children(node,name)
    return c[0] if c else None
def nums(node,i=1,n=None):
    out=[float(x) for x in node[i:] if sym(x) and re.match(r'^-?[\d.]+(e-?\d+)?$',x)]
    return out if n is None else out[:n]
