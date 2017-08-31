# Copyright: 2017 Tim Harder <radhermit@gmail.com>
# License: BSD/GPL2

"""Generic support for running commandline tools."""

from functools import partial
import logging
import os
import signal
import sys

from snakeoil import compatibility, formatters
from snakeoil.demandload import demandload

demandload(
    'traceback',
    'snakeoil.errors:dump_error',
)


class Tool(object):
    """Abstraction for commandline tools."""

    def __init__(self, parser, args=None, namespace=None, outfile=None, errfile=None):
        """Initialize the utility to run.

        :type parser: :obj:`ArgumentParser` subclass instance
        :param parser: argparser instance defining valid arguments for the given tool.
        :type args: sequence of strings
        :param args: arguments to parse, defaulting to C{sys.argv[1:]}.
        :type namespace: argparse.Namespace object
        :param namespace: Namespace object to use for created attributes.
        :type outfile: file-like object
        :param outfile: File to use for stdout, defaults to C{sys.stdout}.
        :type errfile: file-like object
        :param errfile: File to use for stderr, defaults to C{sys.stderr}.
        """
        self.parser = parser
        self.args = args
        self.options = namespace

        if outfile is None:
            outfile = sys.stdout
        if errfile is None:
            errfile = sys.stderr

        out_fd = err_fd = None
        if hasattr(outfile, 'fileno') and hasattr(errfile, 'fileno'):
            if compatibility.is_py3k:
                # annoyingly, fileno can exist but through unsupport
                import io
                try:
                    out_fd, err_fd = outfile.fileno(), errfile.fileno()
                except (io.UnsupportedOperation, IOError):
                    pass
            else:
                try:
                    out_fd, err_fd = outfile.fileno(), errfile.fileno()
                except IOError:
                    # shouldn't be possible, but docs claim it, thus protect.
                    pass

        if out_fd is not None and err_fd is not None:
            out_stat, err_stat = os.fstat(out_fd), os.fstat(err_fd)
            if out_stat.st_dev == err_stat.st_dev \
                    and out_stat.st_ino == err_stat.st_ino and \
                    not errfile.isatty():
                # they're the same underlying fd.  thus
                # point the handles at the same so we don't
                # get intermixed buffering issues.
                errfile = outfile

        self._outfile = outfile
        self._errfile = errfile
        self.out = parser.out = formatters.PlainTextFormatter(outfile)
        self.err = parser.err = formatters.PlainTextFormatter(errfile)

    def parse_args(self, args=None, namespace=None):
        """Parse the given arguments using argparse.

        :type args: sequence of strings
        :param args: arguments to parse, defaulting to C{sys.argv[1:]}.
        :type namespace: argparse.Namespace object
        :param namespace: Namespace object to use for created attributes.
        """
        options = self.parser.parse_args(args=args, namespace=namespace)

        # reconfigure formatters for colored output if enabled
        if getattr(options, 'color', True):
            formatter_factory = partial(
                formatters.get_formatter, force_color=getattr(options, 'color', False))
            self.out = formatter_factory(self._outfile)
            self.err = formatter_factory(self._errfile)

        if logging.root.handlers:
            # Remove the default handler.
            logging.root.handlers.pop(0)
        logging.root.addHandler(FormattingHandler(self.err))

        return options

    def handle_exec_exception(self, e):
        """Handle custom runtime exceptions."""
        # force tracebacks for unhandled exceptions
        tb = sys.exc_info()[-1]
        dump_error(e, "Unhandled exception occurred", handle=self._errfile, tb=tb)

    def main(self):
        """Execute the main script function."""
        options = None
        exitstatus = -10

        # ignore broken pipes
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        try:
            self.options = self.parse_args(args=self.args, namespace=self.options)
            main_func = getattr(self.options, 'main_func', None)
            if main_func is None:
                raise RuntimeError("argparser missing main method")
            exitstatus = main_func(self.options, self.out, self.err)
        except KeyboardInterrupt:
            self._errfile.write('keyboard interrupted- exiting')
            if self.parser.debug:
                self._errfile.write('\n')
                traceback.print_exc()
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            os.killpg(os.getpgid(0), signal.SIGINT)
        except compatibility.IGNORED_EXCEPTIONS:
            raise
        except Exception as e:
            # handle custom execution-related exceptions
            self.handle_exec_exception(e)

        if self.options is not None:
            # set terminal title on exit
            if exitstatus:
                self.out.title('%s failed' % (self.options.prog,))
            else:
                self.out.title('%s succeeded' % (self.options.prog,))

        raise SystemExit(exitstatus)


class FormattingHandler(logging.Handler):
    """Logging handler printing through a formatter."""

    def __init__(self, formatter):
        logging.Handler.__init__(self)
        # "formatter" clashes with a Handler attribute.
        self.out = formatter

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            color = 'red'
        elif record.levelno >= logging.WARNING:
            color = 'yellow'
        else:
            color = 'cyan'
        first_prefix = (self.out.fg(color), self.out.bold, record.levelname,
                        self.out.reset, ' ', record.name, ': ')
        later_prefix = (len(record.levelname) + len(record.name)) * ' ' + ' : '
        self.out.first_prefix.extend(first_prefix)
        self.out.later_prefix.append(later_prefix)
        try:
            for line in self.format(record).split('\n'):
                self.out.write(line, wrap=True)
        finally:
            self.out.later_prefix.pop()
            for i in xrange(len(first_prefix)):
                self.out.first_prefix.pop()