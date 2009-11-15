# Copyright: 2005 Brian Harring <ferringb@gmail.com>
# License: GPL2

"""
sequence related operations
"""

from snakeoil.iterables import expandable_chain

def unstable_unique(sequence):
    """
    lifted from python cookbook, credit: Tim Peters
    Return a list of the elements in s in arbitrary order, sans duplicates
    """

    n = len(sequence)
    # assume all elements are hashable, if so, it's linear
    try:
        return list(set(sequence))
    except TypeError:
        pass

    # so much for linear.  abuse sort.
    try:
        t = sorted(sequence)
    except TypeError:
        pass
    else:
        assert n > 0
        last = t[0]
        lasti = i = 1
        while i < n:
            if t[i] != last:
                t[lasti] = last = t[i]
                lasti += 1
            i += 1
        return t[:lasti]

    # blah.  back to original portage.unique_array
    u = []
    for x in sequence:
        if x not in u:
            u.append(x)
    return u

def stable_unique(iterable):
    """
    return unique list from iterable, preserving ordering
    """
    return list(iter_stable_unique(iterable))

def iter_stable_unique(iterable):
    """
    generator yielding unique elements from iterable, preserving ordering
    """
    s = set()
    sl = []
    for x in iterable:
        try:
            if x not in s:
                yield x
                s.add(x)
        except TypeError:
            # unhashable...
            if x not in sl:
                yield x
                sl.append(x)

def native_iflatten_instance(l, skip_flattening=(basestring,)):
    """
    collapse [[1],2] into [1,2]

    @param skip_flattening: list of classes to not descend through
    """
    if isinstance(l, skip_flattening):
        yield l
        return
    iters = expandable_chain(l)
    try:
        while True:
            x = iters.next()
            if hasattr(x, '__iter__') and not isinstance(x, skip_flattening):
                iters.appendleft(x)
            else:
                yield x
    except StopIteration:
        pass

def native_iflatten_func(l, skip_func):
    """
    collapse [[1],2] into [1,2]

    @param skip_func: a callable that returns True when iflatten_func should
        descend no further
    """
    if skip_func(l):
        yield l
        return
    iters = expandable_chain(l)
    try:
        while True:
            x = iters.next()
            if hasattr(x, '__iter__') and not skip_func(x):
                iters.appendleft(x)
            else:
                yield x
    except StopIteration:
        pass


try:
    # No name "readdir" in module osutils
    # pylint: disable-msg=E0611
    from snakeoil._lists import iflatten_instance, iflatten_func
    cpy_builtin = True
except ImportError:
    cpy_builtin = False
    cpy_iflatten_instance = cpy_iflatten_func = None
    iflatten_instance = native_iflatten_instance
    iflatten_func = native_iflatten_func


class ChainedLists(object):
    """
    sequences chained together, without collapsing into a list
    """
    __slots__ = ("_lists", "__weakref__")

    def __init__(self, *lists):
        """
        all args must be sequences
        """
        # ensure they're iterable
        for x in lists:
            iter(x)

        if isinstance(lists, tuple):
            lists = list(lists)
        self._lists = lists

    def __len__(self):
        return sum(len(l) for l in self._lists)

    def __getitem__(self, idx):
        if idx < 0:
            idx += len(self)
            if idx < 0:
                raise IndexError
        for l in self._lists:
            l2 = len(l)
            if idx < l2:
                return l[idx]
            idx -= l2
        else:
            raise IndexError

    def __setitem__(self, idx, val):
        raise TypeError("not mutable")

    def __delitem__(self, idx):
        raise TypeError("not mutable")

    def __iter__(self):
        for l in self._lists:
            for x in l:
                yield x

    def __contains__(self, obj):
        return obj in iter(self)

    def __str__(self):
        return "[ %s ]" % ", ".join(str(l) for l in self._lists)

    def append(self, item):
        self._lists.append(item)

    def extend(self, items):
        self._lists.extend(items)
