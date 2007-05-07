# Copyright: 2005-2006 Brian Harring <ferringb@gmail.com>
# License: GPL2

"""Metaclass to inject dependencies into method calls.

Essentially, method a must be run prior to method b, invoking method a
if b is called first.
"""

from snakeoil.lists import iflatten_instance
from snakeoil.currying import partial

__all__ = ["ForcedDepends"]

def ensure_deps(self, name, *a, **kw):
    ignore_deps = "ignore_deps" in kw
    if ignore_deps:
        del kw["ignore_deps"]
        s = [name]
    else:
        s = yield_deps(self, self.stage_depends, name)

    r = True
    for dep in s:
        if dep not in self._stage_state:
            r = getattr(self, dep).raw_func(*a, **kw)
            if r:
                self._stage_state.add(dep)
            else:
                return r
    return r

def yield_deps(inst, d, k):
    # While at first glance this looks like should use expandable_chain,
    # it shouldn't. --charlie
    if k not in d:
        yield k
        return
    s = [k, iflatten_instance(d.get(k, ()))]
    while s:
        if isinstance(s[-1], basestring):
            yield s.pop(-1)
            continue
        exhausted = True
        for x in s[-1]:
            v = d.get(x)
            if v:
                s.append(x)
                s.append(iflatten_instance(v))
                exhausted = False
                break
            yield x
        if exhausted:
            s.pop(-1)


class ForcedDepends(type):
    """
    Metaclass forcing methods to run in a certain order.

    Dependencies are controlled by the existance of a stage_depends
    dict in the class namespace. Its keys are method names, values are
    either a string (name of preceeding method), or list/tuple
    (proceeding methods).

    U{pkgcore projects pkgcore.intefaces.format.build_base is an example consumer<http://pkgcore.org>}
    to look at for usage.
    """
    def __call__(cls, *a, **kw):
        o = super(ForcedDepends, cls).__call__(*a, **kw)
        if not getattr(cls, "stage_depends"):
            return o

        if not hasattr(o, "_stage_state"):
            o._stage_state = set()

        # wrap the funcs

        for x in set(x for x in iflatten_instance(o.stage_depends.iteritems())
                     if x):
            f = getattr(o, x)
            f2 = partial(ensure_deps, o, x)
            f2.raw_func = f
            setattr(o, x, f2)

        return o
