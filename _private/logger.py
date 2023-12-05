
import os
import time
import subprocess
import inspect
from enum import StrEnum
from .pathlibext import FilePath, FilePathAbs


_COLOR_SEQUENCES = {'red': '91m', 'yellow': '93m', 'green': '92m',
                    'cyan': '96m', 'bold': '01m'}


class _ColorsMixin():
    """Provide self.print() for the 'Color' enum."""

    def print(self, text):
        print('\033[' + _COLOR_SEQUENCES[self.name] + text + '\033[0m')


Colors = StrEnum('Colors', names=list(_COLOR_SEQUENCES.keys()), type=_ColorsMixin)


# logging.basicConfig(format = '%(filename)-5s %(levelname)-8s [%(asctime)s]  %(message)s', level = logging.DEBUG)

class _OutputProcessor:
    """Private class fo provide logging facilities

    The main purpose of this class to allow to log the text messages
    as well as the std stream from external programmes called.
    ."""

    __instance = None  # Make a singleton

    def __new__(cls, *args):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, force_bw: bool = False):
        self._flogfile = None  # file descriptor
        self.force_bw = force_bw

    def open_logfile(self, path: str | FilePath):
        self.close_logfile()
        is_exists = os.path.exists(path)
        self._flogfile = open(path, 'a')
        if is_exists:  # Separate new output from previous
            self._flogfile.write('\n')

    def close_logfile(self):
        if self._flogfile:
            self._flogfile.close()
            self._flogfile = None

    def _call_popen(self, cmd: str, stdin: str, catch_output: bool):
        if catch_output:
            child = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                                     stdout=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True)
            child.stdin.write(stdin)
            child.stdin.flush()
            child.stdin.close()
            for line in child.stdout:
                self._flogfile.write(line)
            self._flogfile.flush()
        else:
            child = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                                     stdin=subprocess.PIPE, universal_newlines=True)
            child.stdin.write(stdin)
            child.stdin.flush()
            child.stdin.close()
        child.wait()
        return child

    def callandlog(self, cmd: str, stdin: str = '', separate_logfile: FilePathAbs = None,
                   extra_start: str = '', extra_end: str = '',
                   return_code: bool = False, progname: str = None) -> tuple[bool, int] | bool:
        self.print_colored_and_log(cmd, progname, color=Colors.bold)
        command = extra_start + cmd + extra_end
        if separate_logfile:
            command = 'set -o pipefail; ' + command + ' | tee -a ' + os.fspath(separate_logfile)
            self.onlylog(f"See log in '{separate_logfile}'", progname=None)
            child = self._call_popen(command, stdin, False)
        elif self._flogfile:
            child = self._call_popen(command, stdin, True)
        else:
            child = self._call_popen(command, stdin, False)

        code = child.returncode
        if code == 0:
            self.print_colored_and_log(f"Finished with code {code}", progname, color=Colors.bold)
        else:
            self.print_colored_and_log(f"Finished with code {code}", progname,
                                       msgtype='Warning:', color=Colors.yellow)

        if return_code:
            return bool(not code), code
        return bool(not code)

    @staticmethod
    def _getprogname():
        """Return name of the function which is not an _under and not a class member."""
        modulename = progname = ''
        stack = inspect.stack()
        for frame in stack[3:]:  # i=0 is _getprogname() and i=1 and 2 is the functions inside this module
            module = inspect.getmodule(frame[0])
            progname = frame[3]
            modulename = os.path.basename(module.__file__)
            if modulename not in (__name__ + '.py', 'functools.py') and \
                    progname[0] != '_' and hasattr(module, progname):
                break
        return modulename if progname == '<module>' else progname

    def _prepare_text(self, text: str, *, progname: str = None, msgtype: str = ''):
        """Inject progname ans msgtype to the string message."""
        if progname is None:  # Use None to get default and '' for empty progname
            progname = self._getprogname()
        progtxt = f'[{progname}]:' if progname else ''  # Use ''
        return ' '.join([x for x in [progtxt, msgtype, text] if x])

    def _log_text(self, text: str) -> None:
        """Put the text into the logfile."""
        if self._flogfile:
            timestamp = time.strftime('%Y %b %d %H:%M:%S', time.localtime())
            self._flogfile.write(timestamp + ' - ' + text + '\n')
            self._flogfile.flush()

    def onlylog(self, text: str, progname: str = None, msgtype: str = '') -> None:
        self._log_text(self._prepare_text(text, progname=progname, msgtype=msgtype))

    def print_colored_and_log(self, text: str, progname: str = None,
                              msgtype: str = '', color: Colors = None):
        _text = self._prepare_text(text, progname=progname, msgtype=msgtype)
        if color and self.force_bw == False:
            color.print(_text)
        else:
            print(_text)
        self._log_text(_text)
        return text