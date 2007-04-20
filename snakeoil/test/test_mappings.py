# Copyright: 2005-2006 Marien Zwart <marienz@gentoo.org>
# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2

import operator

from snakeoil.test import TestCase
from snakeoil import mappings
from itertools import chain


def a_dozen():
    return range(12)


class BasicDict(mappings.DictMixin):

    def __init__(self, i=None, **kwargs):
        self._d = {}
        mappings.DictMixin.__init__(self, i, **kwargs)

    def iterkeys(self):
        return iter(self._d)

class MutableDict(BasicDict):

    def __setitem__(self, key, val):
        self._d[key] = val

    def __getitem__(self, key):
        return self._d[key]

    def __delitem__(self, key):
        del self._d[key]


class ImmutableDict(BasicDict):
    __externally_mutable__ = False

class TestDictMixin(TestCase):
    def test_immutability(self):
        d = ImmutableDict()
        self.assertRaises(AttributeError, d.__setitem__, "spork", "foon")
        for x in ("pop", "setdefault", "__delitem__"):
            self.assertRaises(AttributeError, getattr(d, x), "spork")
        for x in ("clear", "popitem"):
            self.assertRaises(AttributeError, getattr(d, x))

    def test_setdefault(self):
        d = MutableDict(baz="cat")
        self.assertEqual(d.setdefault("baz"), "cat")
        self.assertEqual(d.setdefault("baz", "foon"), "cat")
        self.assertEqual(d.setdefault("foo"), None)
        self.assertEqual(d["foo"], None)
        self.assertEqual(d.setdefault("spork", "cat"), "cat")
        self.assertEqual(d["spork"], "cat")

    def test_pop(self):
        d = MutableDict(baz="cat", foo="bar")
        self.assertRaises(KeyError, d.pop, "spork")
        self.assertEqual(d.pop("spork", "bat"), "bat")
        self.assertEqual(d.pop("foo"), "bar")
        self.assertEqual(d.popitem(), ("baz", "cat"))
        self.assertRaises(KeyError, d.popitem)


    def test_init(self):
        d = MutableDict((('foo', 'bar'), ('spork', 'foon')), baz="cat")
        self.assertEqual(d["foo"], "bar")
        self.assertEqual(d["baz"], "cat")
        d.clear()
        self.assertEqual(d, {})

class RememberingNegateMixin(object):

    def setUp(self):
        self.negate_calls = []
        def negate(i):
            self.negate_calls.append(i)
            return -i
        self.negate = negate

    def tearDown(self):
        del self.negate
        del self.negate_calls



class LazyValDictTestMixin(object):

    def test_invalid_operations(self):
        self.assertRaises(AttributeError, operator.setitem, self.dict, 7, 7)
        self.assertRaises(AttributeError, operator.delitem, self.dict, 7)

    def test_contains(self):
        self.failUnless(7 in self.dict)
        self.failIf(12 in self.dict)

    def test_keys(self):
        # Called twice because the first call will trigger a keyfunc call.
        self.failUnlessEqual(sorted(self.dict.keys()), list(xrange(12)))
        self.failUnlessEqual(sorted(self.dict.keys()), list(xrange(12)))

    def test_len(self):
        # Called twice because the first call will trigger a keyfunc call.
        self.assertEqual(12, len(self.dict))
        self.assertEqual(12, len(self.dict))

    def test_getkey(self):
        self.assertEqual(self.dict[3], -3)
        # missing key
        def get():
            return self.dict[42]
        self.assertRaises(KeyError, get)

    def test_caching(self):
        # "Statement seems to have no effect"
        # pylint: disable-msg=W0104
        self.dict[11]
        self.dict[11]
        self.assertEqual(self.negate_calls, [11])


class LazyValDictWithListTest(
    TestCase, LazyValDictTestMixin, RememberingNegateMixin):

    def setUp(self):
        RememberingNegateMixin.setUp(self)
        self.dict = mappings.LazyValDict(range(12), self.negate)

    def tearDown(self):
        RememberingNegateMixin.tearDown(self)

    def test_itervalues(self):
        self.assertEqual(sorted(self.dict.itervalues()), range(-11, 1))

    def test_len(self):
        self.assertEqual(len(self.dict), 12)

    def test_iter(self):
        self.assertEqual(list(self.dict), range(12))

    def test_contains(self):
        self.assertIn(1, self.dict)

    def test_has_key(self):
        self.assertEqual(True, self.dict.has_key(1))

class LazyValDictWithFuncTest(
    TestCase, LazyValDictTestMixin, RememberingNegateMixin):

    def setUp(self):
        RememberingNegateMixin.setUp(self)
        self.dict = mappings.LazyValDict(a_dozen, self.negate)

    def tearDown(self):
        RememberingNegateMixin.tearDown(self)


class LazyValDictTest(TestCase):

    def test_invalid_init_args(self):
        self.assertRaises(TypeError, mappings.LazyValDict, [1], 42)
        self.assertRaises(TypeError, mappings.LazyValDict, 42, a_dozen)


# TODO check for valid values for dict.new, since that seems to be
# part of the interface?
class ProtectedDictTest(TestCase):

    def setUp(self):
        self.orig = {1: -1, 2: -2}
        self.dict = mappings.ProtectedDict(self.orig)

    def test_basic_operations(self):
        self.assertEqual(self.dict[1], -1)
        def get(i):
            return self.dict[i]
        self.assertRaises(KeyError, get, 3)
        self.assertEqual(sorted(self.dict.keys()), [1, 2])
        self.failIf(-1 in self.dict)
        self.failUnless(2 in self.dict)
        def remove(i):
            del self.dict[i]
        self.assertRaises(KeyError, remove, 50)

    def test_basic_mutating(self):
        # add something
        self.dict[7] = -7
        def check_after_adding():
            self.assertEqual(self.dict[7], -7)
            self.failUnless(7 in self.dict)
            self.assertEqual(sorted(self.dict.keys()), [1, 2, 7])
        check_after_adding()
        # remove it again
        del self.dict[7]
        self.failIf(7 in self.dict)
        def get(i):
            return self.dict[i]
        self.assertRaises(KeyError, get, 7)
        self.assertEqual(sorted(self.dict.keys()), [1, 2])
        # add it back
        self.dict[7] = -7
        check_after_adding()
        # remove something not previously added
        del self.dict[1]
        self.failIf(1 in self.dict)
        self.assertRaises(KeyError, get, 1)
        self.assertEqual(sorted(self.dict.keys()), [2, 7])
        # and add it back
        self.dict[1] = -1
        check_after_adding()
        # Change an existing value, then remove it:
        self.dict[1] = 33
        del self.dict[1]
        self.assertNotIn(1, self.dict)


class ImmutableDictTest(TestCase):

    def setUp(self):
        self.dict = mappings.ImmutableDict(**{1: -1, 2: -2})

    def test_invalid_operations(self):
        initial_hash = hash(self.dict)
        self.assertRaises(TypeError, operator.delitem, self.dict, 1)
        self.assertRaises(TypeError, operator.delitem, self.dict, 7)
        self.assertRaises(TypeError, operator.setitem, self.dict, 1, -1)
        self.assertRaises(TypeError, operator.setitem, self.dict, 7, -7)
        self.assertRaises(TypeError, self.dict.clear)
        self.assertRaises(TypeError, self.dict.update, {6: -6})
        self.assertRaises(TypeError, self.dict.pop, 1)
        self.assertRaises(TypeError, self.dict.popitem)
        self.assertRaises(TypeError, self.dict.setdefault, 6, -6)
        self.assertEqual(initial_hash, hash(self.dict))

class StackedDictTest(TestCase):

    orig_dict = dict.fromkeys(xrange(100))
    new_dict = dict.fromkeys(xrange(100, 200))

    def test_contains(self):
        std = mappings.StackedDict(self.orig_dict, self.new_dict)
        self.failUnless(1 in std)
        self.failUnless(std.has_key(1))

    def test_stacking(self):
        o = dict(self.orig_dict)
        std = mappings.StackedDict(o, self.new_dict)
        for x in chain(*map(iter, (self.orig_dict, self.new_dict))):
            self.failUnless(x in std)

        map(o.__delitem__, iter(self.orig_dict))
        for x in self.orig_dict:
            self.failIf(x in std)
        for x in self.new_dict:
            self.failUnless(x in std)

    def test_len(self):
        self.assertEqual(sum(map(len, (self.orig_dict, self.new_dict))),
            len(mappings.StackedDict(self.orig_dict, self.new_dict)))

    def test_setattr(self):
        self.assertRaises(TypeError, mappings.StackedDict().__setitem__, (1, 2))

    def test_delattr(self):
        self.assertRaises(TypeError, mappings.StackedDict().__delitem__, (1, 2))

    def test_clear(self):
        self.assertRaises(TypeError, mappings.StackedDict().clear)

    def test_iter(self):
        s = set()
        map(s.add, chain(iter(self.orig_dict), iter(self.new_dict)))
        for x in mappings.StackedDict(self.orig_dict, self.new_dict):
            self.failUnless(x in s)
            s.remove(x)
        self.assertEqual(len(s), 0)

    def test_keys(self):
        self.assertEqual(
            sorted(mappings.StackedDict(self.orig_dict, self.new_dict)),
            sorted(self.orig_dict.keys() + self.new_dict.keys()))


class IndeterminantDictTest(TestCase):

    def test_disabled_methods(self):
        d = mappings.IndeterminantDict(lambda *a: None)
        for x in ("clear", ("update", {}), ("setdefault", 1),
            "__iter__", "__len__", "__hash__", ("__delitem__", 1),
            ("__setitem__", 2), ("popitem", 2), "iteritems", "iterkeys",
            "keys", "items", "itervalues", "values"):
            if isinstance(x, tuple):
                self.assertRaises(TypeError, getattr(d, x[0]), x[1])
            else:
                self.assertRaises(TypeError, getattr(d, x))

    def test_starter_dict(self):
        d = mappings.IndeterminantDict(
            lambda key: False, starter_dict={}.fromkeys(xrange(100), True))
        for x in xrange(100):
            self.assertEqual(d[x], True)
        for x in xrange(100, 110):
            self.assertEqual(d[x], False)

    def test_behaviour(self):
        val = []
        d = mappings.IndeterminantDict(
            lambda key: val.append(key), {}.fromkeys(xrange(10), True))
        self.assertEqual(d[0], True)
        self.assertEqual(d[11], None)
        self.assertEqual(val, [11])
        def func(*a):
            raise KeyError
        self.assertRaises(
            KeyError, mappings.IndeterminantDict(func).__getitem__, 1)


    def test_get(self):
        def func(key):
            if key == 2:
                raise KeyError
            return True
        d = mappings.IndeterminantDict(func, {1:1})
        self.assertEqual(d.get(1, 1), 1)
        self.assertEqual(d.get(1, 2), 1)
        self.assertEqual(d.get(2), None)
        self.assertEqual(d.get(2, 2), 2)
        self.assertEqual(d.get(3), True)


class TestOrderedDict(TestCase):

    @staticmethod
    def gen_dict():
        return mappings.OrderedDict(enumerate(xrange(100)))

    def test_items(self):
        self.assertEqual(list(self.gen_dict().iteritems()),
            list(enumerate(xrange(100))))
        self.assertEqual(self.gen_dict().items(),
            list(enumerate(xrange(100))))

    def test_values(self):
        self.assertEqual(list(self.gen_dict().itervalues()),
            list(xrange(100)))
        l = ["asdf", "fdsa", "Dawefa", "3419", "pas", "1"]
        l = [s+"12" for s in l] + l
        l = ["1231adsfasdfagqwer"+s for s in l] + l
        self.assertEqual(
            list(mappings.OrderedDict(
                    (v, k) for k, v in enumerate(l)).itervalues()),
            list(xrange(len(l))))

    def test_keys(self):
        self.assertEqual(list(self.gen_dict().iterkeys()), list(xrange(100)))
        self.assertEqual(self.gen_dict().keys(), list(xrange(100)))

    def test_iter(self):
        self.assertEqual(list(self.gen_dict()), list(xrange(100)))
        l = ["asdf", "fdsa", "Dawefa", "3419", "pas", "1"]
        l = [s+"12" for s in l] + l
        l = ["1231adsfasdfagqwer"+s for s in l] + l
        self.assertEqual(list(mappings.OrderedDict((x, None) for x in l)), l)

    def test_del(self):
        d = self.gen_dict()
        del d[50]
        self.assertEqual(list(d), list(range(50) + range(51, 100)))
        self.assertRaises(KeyError, operator.delitem, d, 50)
        self.assertRaises(KeyError, operator.delitem, d, 'spork')

    def test_set(self):
        d = self.gen_dict()
        d.setdefault(120)
        d.setdefault(110)
        self.assertEqual(list(d), list(range(100)) + [120, 110])

    def test_clear(self):
        self.gen_dict().clear()


class FoldingDictTest(TestCase):

    def testPreserve(self):
        dct = mappings.PreservingFoldingDict(
            str.lower, {'Foo':'bar', 'fnz':{1: 2}}.iteritems())
        self.assertEqual(dct['fnz'], {1: 2})
        self.assertEqual(dct['foo'], 'bar')
        self.assertEqual(sorted(['bar', {1: 2}]), sorted(dct.values()))
        self.assertEqual(dct.copy(), dct)
        self.assertEqual(dct['foo'], dct.get('Foo'))
        self.assert_('foo' in dct)
        keys = ['Foo', 'fnz']
        keysList = list(dct)
        for key in keys:
            self.assert_(key in dct.keys())
            self.assert_(key in keysList)
            self.assert_((key, dct[key]) in dct.items())
        self.assertEqual(len(keys), len(dct))
        self.assert_(dct.pop('foo') == 'bar')
        self.assert_('foo' not in dct)
        del dct['fnz']
        self.assert_('fnz' not in dct)
        dct['Foo'] = 'bar'
        dct.refold(lambda _: _)
        self.assert_('foo' not in dct)
        self.assert_('Foo' in dct)
        self.assertEqual(dct.items(), [('Foo', 'bar')])
        dct.clear()
        self.assertEqual({}, dict(dct))

    def testNoPreserve(self):
        dct = mappings.NonPreservingFoldingDict(
            str.lower, {'Foo':'bar', 'fnz':{1: 2}}.iteritems())
        self.assertEqual(sorted(['bar', {1: 2}]), sorted(dct.values()))
        self.assertEqual(dct.copy(), dct)
        keys = ['foo', 'fnz']
        keysList = [key for key in dct]
        for key in keys:
            self.assert_(key in dct.keys())
            self.assert_(key in dct)
            self.assert_(key in keysList)
            self.assert_((key, dct[key]) in dct.items())
        self.assertEqual(len(keys), len(dct))
        self.assertEqual(dct.pop('foo'), 'bar')
        del dct['fnz']
        self.assertEqual(dct.keys(), [])
        dct.clear()
        self.assertEqual({}, dict(dct))
