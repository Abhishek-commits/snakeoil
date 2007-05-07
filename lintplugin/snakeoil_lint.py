
"""Pylint plugin checking for trailing whitespace."""


import sys

from pylint import interfaces, checkers
from logilab.astng import nodes, raw_building, utils, Name


class SnakeoilChecker(checkers.BaseChecker):

    __implements__ = (interfaces.IRawChecker, interfaces.IASTNGChecker)

    name = 'snakeoil'

    # XXX move some of those over to RewriteDemandload somehow
    # (current monkey patch running the rewriter does not support that)

    msgs = {
        'CPC01': ('line too long: length %d',
                  'More complete version of the standard line too long check.'),
        'CPC02': ('trailing whitespace', 'trailing whitespace sucks.'),
        'WPC01': ('demandload with arglen < 2 ignored',
                  'A call which is probably a demandload has too little'
                  'arguments.'),
        'WPC02': ('demandload with non-string-constant arg ignored',
                  'A call which is probably a demandload has a second arg '
                  'that is not a string constant. Fix the code to cooperate '
                  'with the dumb checker.'),
        'WPC03': ('old-style demandload call',
                  'A call which uses the old way of callling demandload,'
                  'with spaces.'),
        'WPC04': ('non new-style class',
                  'All classes should be new-style classes.'),
        'WPC05': ('raise statement with two args',
                  'A raise statement which has a message raised with the '
                  'exception instead of as an argument to the exception '
                  'class.'),
        'WPC06': ('raise of Exception base class',
                  'A raise statement in which Exception is raised- make a '
                  'subclass of it and raise that instead.'),
        }

    def process_module(self, stream):
        for linenr, line in enumerate(stream):
            line = line.rstrip('\r\n')
            if len(line) > 80:
                self.add_message('CPC01', linenr, args=len(line))
            if line.endswith(' ') or line.endswith('\t'):
                self.add_message('CPC02', linenr)

    def visit_class(self, node):
        if not node.bases:
            self.add_message('WPC04', node=node)

    def visit_raise(self, node):
        if node.expr2 is not None:
            self.add_message('WPC05', node=node)
        expr = node.expr1
        if expr is not None and isinstance(expr, Name) and \
            expr.name == "Exception":
            self.add_message('WPC06', node=node)

class RewriteDemandload(utils.ASTWalker):

    def __init__(self, linter):
        utils.ASTWalker.__init__(self, self)
        self.linter = linter

    def visit_callfunc(self, node):
        """Hack fake imports into the tree after demandload calls."""
        # XXX inaccurate hack
        if not node.node.as_string().endswith('demandload'):
            return
        # sanity check.
        if len(node.args) < 2:
            self.linter.add_message('WPC01', node=node)
            return
        if not isinstance(node.args[1], nodes.Const):
            self.linter.add_message('WPC02', node=node)
            return
        if node.args[1].value.find(" ") != -1:
            self.linter.add_message('WPC03', node=node)
            return
        for mod in (module.value for module in node.args[1:]):
            if not isinstance(mod, str):
                self.linter.add_message('WPC02', node=node)
                continue
            col = mod.find(':')
            if col == -1:
                # Argument to Import probably works like this:
                # "import foo, foon as spork" is
                # nodes.Import([('foo', None), ('foon', 'spork')])
                # (not entirely sure though, have not found documentation.
                # The asname/importedname might be the other way around fex).
                newstuff = nodes.Import([(mod, None)])
                newstuff.fromlineno = node.fromlineno
                raw_building._attach_local_node(node.frame(), newstuff, mod)
            else:
                for name in mod[col+1:].split(','):
                    if sys.version_info < (2, 5):
                        newstuff = nodes.From(mod[:col], ((name, None),))
                    else:
                        newstuff = nodes.From(mod[:col], ((name, None),), 0)
                    newstuff.fromlineno = 1
                    raw_building._attach_local_node(node.frame(), newstuff,
                                                    name)


def register(linter):
    """Required method to get our checker registered."""

    rewriter = RewriteDemandload(linter)
    # XXX HACK: monkeypatch the linter to transform the tree before
    # the astng checkers get at it.
    #
    # Why do we do this? Because a whole bunch of places work with
    # copies of astng data, not the data itself, by the time a normal
    # checker runs it is too late to manipulate the data reliably. And
    # pylint does not provide a hook that gets run at the right point
    # to do this tree rewriting. So we monkeypatch in the hook.
    #
    # Ideally we would do something like
    #
    # linter.register_preprocessor(rewriter)
    #
    # and the linter would call walk(astng) on everything registered
    # that way before the IASTNGCheckers run (not sure if it should be
    # before or after the raw checkers run, probably does not matter).
    # Perhaps give those preprocessors a priority attribute too.
    # Definitely give them a msgs attribute.

    original_check_astng_module = linter.check_astng_module
    def snakeoil_check_astng_module(astng, checkers):
        rewriter.walk(astng)
        original_check_astng_module(astng, checkers)
    linter.check_astng_module = snakeoil_check_astng_module

    linter.register_checker(SnakeoilChecker(linter))
