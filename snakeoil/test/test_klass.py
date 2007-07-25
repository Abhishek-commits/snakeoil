# Copyright: 2006-2007 Brian Harring <ferringb@gmail.com>
# License: GPL2

from snakeoil.test import TestCase
from snakeoil import klass, currying


class Test_native_GetAttrProxy(TestCase):
    kls = staticmethod(klass.native_GetAttrProxy)

    def test_it(self):
        class foo1(object):
            def __init__(self, obj):
                self.obj = obj
            __getattr__ = self.kls('obj')

        class foo2(object):
            pass

        o2 = foo2()
        o = foo1(o2)
        self.assertRaises(AttributeError, getattr, o, "blah")
        self.assertEqual(o.obj, o2)
        o2.foon = "dar"
        self.assertEqual(o.foon, "dar")
        o.foon = "foo"
        self.assertEqual(o.foon, 'foo')

    def test_attrlist(self):
        def make_class(attr_list=None):
            class foo(object):
                __metaclass__ = self.kls

                if attr_list is not None:
                    locals()['__attr_comparison__'] = attr_list

        self.assertRaises(TypeError, make_class)
        self.assertRaises(TypeError, make_class, [u'foon'])
        self.assertRaises(TypeError, make_class, [None])

    def test_instancemethod(self):
        class foo(object):
            bar = "baz"

        class Test(object):
            method = self.kls('test')
            test = foo()

        test = Test()
        self.assertEqual(test.method('bar'), foo.bar)


class Test_CPY_GetAttrProxy(Test_native_GetAttrProxy):

    kls = staticmethod(klass.GetAttrProxy)
    if klass.GetAttrProxy is klass.native_GetAttrProxy:
        skip = "cpython extension isn't available"

    def test_sane_recursion_bail(self):
        # people are stupid; if protection isn't in place, we wind up blowing
        # the c stack, which doesn't result in a friendly Exception being
        # thrown.
        # results in a segfault.. so if it's horked, this will bail the test
        # runner.

        class c(object):
            __getattr__ = self.kls("obj")

        o = c()
        o.obj = o
        # now it's cyclical.
        self.assertRaises(RuntimeError, getattr, o, "hooey")


class Test_native_contains(TestCase):
    func = staticmethod(klass.native_contains)

    def test_it(self):
        class c(dict):
            __contains__ = self.func
        d = c({"1":2})
        self.assertIn("1", d)
        self.assertNotIn(1, d)


class Test_CPY_contains(Test_native_contains):
    func = staticmethod(klass.contains)

    if klass.contains is klass.native_contains:
        skip = "cpython extension isn't available"


class Test_native_get(TestCase):
    func = staticmethod(klass.native_get)

    def test_it(self):
        class c(dict):
            get = self.func
        d = c({"1":2})
        self.assertEqual(d.get("1"), 2)
        self.assertEqual(d.get("1", 3), 2)
        self.assertEqual(d.get(1), None)
        self.assertEqual(d.get(1, 3), 3)

class Test_CPY_get(Test_native_get):
    func = staticmethod(klass.get)

    if klass.get is klass.native_get:
        skip = "cpython extension isn't available"

class Test_native_generic_equality(TestCase):
    op_prefix = "native_"

    kls = currying.partial(klass.generic_equality,
        ne=klass.native_generic_ne, eq=klass.native_generic_eq)

    def test_it(self):
        class c(object):
            __attr_comparison__ = ("foo", "bar")
            __metaclass__ = self.kls
            def __init__(self, foo, bar):
                self.foo, self.bar = foo, bar

            def __repr__(self):
                return "<c: foo=%r, bar=%r, %i>" % (
                    getattr(self, 'foo', 'unset'),
                    getattr(self, 'bar', 'unset'),
                    id(self))

        self.assertEqual(c(1, 2), c(1, 2))
        c1 = c(1, 3)
        self.assertEqual(c1, c1)
        del c1
        self.assertNotEqual(c(2,1), c(1,2))
        c1 = c(1, 2)
        del c1.foo
        c2 = c(1, 2)
        self.assertNotEqual(c1, c2)
        del c2.foo
        self.assertEqual(c1, c2)

    def test_call(self):
        def mk_class(meta):
            class c(object):
                __metaclass__ = meta
            return c
        self.assertRaises(TypeError, mk_class)


class Test_cpy_generic_equality(Test_native_generic_equality):
    op_prefix = ''
    if klass.native_generic_eq is klass.generic_eq:
        skip = "extension not available"

    kls = staticmethod(klass.generic_equality)


class Test_chained_getter(TestCase):

    kls = klass.chained_getter

    def test_hash(self):
        self.assertEqual(hash(self.kls("foon")), hash("foon"))
        self.assertEqual(hash(self.kls("foon.dar")), hash("foon.dar"))

    def test_caching(self):
        l = [id(self.kls("fa2341f%s" % x)) for x in "abcdefghij"]
        self.assertEqual(id(self.kls("fa2341fa")), l[0])

    def test_eq(self):
        self.assertEqual(self.kls("asdf", disable_inst_caching=True),
            self.kls("asdf", disable_inst_caching=True))

        self.assertNotEqual(self.kls("asdf2", disable_inst_caching=True),
            self.kls("asdf", disable_inst_caching=True))

    def test_it(self):
        class maze(object):
            def __init__(self, kwargs):
                self.__data__ = kwargs

            def __getattr__(self, attr):
                return self.__data__.get(attr, self)

        d = {}
        m = maze(d)
        f = self.kls
        self.assertEqual(f('foon')(m), m)
        d["foon"] = 1
        self.assertEqual(f('foon')(m), 1)
        self.assertEqual(f('dar.foon')(m), 1)
        self.assertEqual(f('.'.join(['blah']*10))(m), m)
        self.assertRaises(AttributeError, f('foon.dar'), m)
