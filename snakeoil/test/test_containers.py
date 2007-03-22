# Copyright: 2005 Marien Zwart <marienz@gentoo.org>
# License: GPL2


from snakeoil.test import TestCase
from snakeoil import containers


class InvertedContainsTest(TestCase):

    def setUp(self):
        self.set = containers.InvertedContains(range(12))

    def test_basic(self):
        self.failIf(7 in self.set)
        self.failUnless(-7 in self.set)
        self.assertRaises(TypeError, iter, self.set)


class LimitedChangeSetTest(TestCase):

    def setUp(self):
        self.set = containers.LimitedChangeSet(range(12))

    def test_basic(self, changes=0):
        # this should be a no-op
        self.set.rollback(changes)
        # and this is invalid
        self.assertRaises(TypeError, self.set.rollback, changes + 1)
        self.failUnless(0 in self.set)
        self.failIf(12 in self.set)
        self.assertEquals(12, len(self.set))
        self.assertEquals(sorted(list(self.set)), list(range(12)))
        self.assertEquals(changes, self.set.changes_count())
        self.assertRaises(TypeError, self.set.rollback, -1)

    def test_dummy_commit(self):
        # this should be a no-op
        self.set.commit()
        # so this should should run just as before
        self.test_basic()

    def test_adding(self):
        self.set.add(13)
        self.failUnless(13 in self.set)
        self.assertEquals(13, len(self.set))
        self.assertEquals(sorted(list(self.set)), list(range(12)) + [13])
        self.assertEquals(1, self.set.changes_count())
        self.set.add(13)
        self.assertRaises(containers.Unchangable, self.set.remove, 13)

    def test_add_rollback(self):
        self.set.add(13)
        self.set.rollback(0)
        # this should run just as before
        self.test_basic()

    def test_add_commit_remove_commit(self):
        self.set.add(13)
        self.set.commit()
        # should look like right before commit
        self.assertEquals(13, len(self.set))
        self.assertEquals(sorted(list(self.set)), list(range(12)) + [13])
        self.assertEquals(0, self.set.changes_count())
        # and remove...
        self.set.remove(13)
        # should be back to basic, but with 1 change
        self.test_basic(1)
        self.set.commit()
        self.test_basic()

    def test_removing(self):
        self.set.remove(0)
        self.failIf(0 in self.set)
        self.assertEquals(11, len(self.set))
        self.assertEquals(sorted(list(self.set)), list(range(1, 12)))
        self.assertEquals(1, self.set.changes_count())
        self.assertRaises(containers.Unchangable, self.set.add, 0)
        self.assertRaises(KeyError, self.set.remove, 0)

    def test_remove_rollback(self):
        self.set.remove(0)
        self.set.rollback(0)
        self.test_basic()

    def test_remove_commit_add_commit(self):
        self.set.remove(0)
        self.set.commit()
        self.failIf(0 in self.set)
        self.assertEquals(11, len(self.set))
        self.assertEquals(sorted(list(self.set)), list(range(1, 12)))
        self.assertEquals(0, self.set.changes_count())
        self.set.add(0)
        self.test_basic(1)
        self.set.commit()
        self.test_basic()

    def test_longer_transaction(self):
        self.set.add(12)
        self.set.remove(7)
        self.set.rollback(1)
        self.set.add(-1)
        self.set.commit()
        self.assertEquals(sorted(list(self.set)), list(range(-1, 13)))

    def test_str(self):
        self.assertEquals(
            str(containers.LimitedChangeSet([7])), 'LimitedChangeSet([7])')


    def test__eq__(self):
        c = containers.LimitedChangeSet(range(99))
        c.add(99)
        self.assertEquals(c, containers.LimitedChangeSet(range(100)))

class LimitedChangeSetWithBlacklistTest(TestCase):

    def setUp(self):
        self.set = containers.LimitedChangeSet(range(12), [3, 13])

    def test_basic(self):
        self.failUnless(0 in self.set)
        self.failIf(12 in self.set)
        self.assertEquals(12, len(self.set))
        self.assertEquals(sorted(list(self.set)), list(range(12)))
        self.assertEquals(0, self.set.changes_count())
        self.assertRaises(TypeError, self.set.rollback, -1)

    def test_adding_blacklisted(self):
        self.assertRaises(containers.Unchangable, self.set.add, 13)

    def test_removing_blacklisted(self):
        self.assertRaises(containers.Unchangable, self.set.remove, 3)


class ProtectedSetTest(TestCase):

    def setUp(self):
        self.set = containers.ProtectedSet(set(range(12)))

    def test_contains(self):
        self.assertTrue(0 in self.set)
        self.assertFalse(15 in self.set)
        self.set.add(15)
        self.assertTrue(15 in self.set)

    def test_iter(self):
        self.assertEqual(range(12), sorted(self.set))
        self.set.add(5)
        self.assertEqual(range(12), sorted(self.set))
        self.set.add(12)
        self.assertEqual(range(13), sorted(self.set))

    def test_len(self):
        self.assertEqual(12, len(self.set))
        self.set.add(5)
        self.set.add(13)
        self.assertEqual(13, len(self.set))


class TestRefCountingSet(TestCase):

    def test_it(self):
        c = containers.RefCountingSet((1, 2))
        self.assertIn(1, c)
        self.assertIn(2, c)
        c.remove(1)
        self.assertNotIn(1, c)
        self.assertRaises(KeyError, c.remove, 1)
        c.add(2)
        self.assertIn(2, c)
        c.remove(2)
        self.assertIn(2, c)
        c.remove(2)
        self.assertNotIn(2, c)
        c.add(3)
        self.assertIn(3, c)
        c.remove(3)
        self.assertNotIn(3, c)
