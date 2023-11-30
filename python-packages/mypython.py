"""Methods to perform basic checks like existence of input files and so on."""

import sys, os, time
import functools, inspect, subprocess
from enum import StrEnum, auto
from collections.abc import Mapping, Sequence, Iterable
from typing import Any, Union, Type, TypeVar, Self
from pathlib import Path, PurePosixPath


# logging.basicConfig(format = '%(filename)-5s %(levelname)-8s [%(asctime)s]  %(message)s', level = logging.DEBUG)

#####################################################
### Classes for manipulation with file paths ########


class FilePath(PurePosixPath):
    """Extension of pathlib's PurePath."""

    _class_abspath = None  # abspath  brother class, to be redefined below

    def __new__(cls, *args):
        drv, root, parts = cls._parse_args(args)
        # Explicitly call the own method with cls argument passed to not
        # break myfits.ExtPath
        return FilePath._from_parsed_parts.__func__(cls, drv, root, parts)

    @classmethod
    def _from_parsed_parts(cls, drv, root, parts):
        """Construct object from parts

        It overrides PurePath's classmethod of the same name
        to automatically switch between relative and absolute path.
        """
        if root:  # Path absolute
            obj = object.__new__(cls._class_abspath)  # Create empty object
        else:    # Path not absolute
            if cls is cls._class_abspath :   # but the target class is for abspath
                raise ValueError(
                    "Can't create '{}' object from relative path '{}'.".
                    format(cls.__name__, '/'.join(parts)))
            else:
                obj = object.__new__(cls)
        obj._drv = drv
        obj._root = root
        obj._parts = parts
        return obj

    @property
    def fspath(self):
        """Return pure path as a string (the same as os.fspath(self))."""
        return self.__fspath__()

    def absolute(self):
        """Add CWD to the file path to make it absolute."""
        return self if self.is_absolute() else self._class_abspath(os.getcwd(), self)

    def with_stem_starting(self, text: str) -> Self:
        """Append string to the start of the filename."""
        return self.with_name(f'{text}{self.name}')

    def with_stem_ending(self, text: str) -> Self:
        """Append string to the end of the filename (before suffix)."""
        return self.with_name(f'{self.stem}{text}{self.suffix}')

    def with_suffix_append(self, suffix: str) -> Self:
        """Add another suffix to the existing filepath."""
        if isinstance(suffix, str):
            if not suffix.startswith('.'):
                suffix = '.' + suffix
            if len(suffix) > 1:
                return self.with_suffix(self.suffix + suffix)
        raise ValueError(f"Invalid suffix '{suffix}'")

    def with_parent(self, parent: str) -> Self:
        """Return a new Filepath object with another sefl.parent"""
        drv, root, parts = self._parse_args([parent])  # Call PurePath._parse_args
        parts.append(self.name)
        return self._from_parsed_parts(drv, root, parts)

    def with_parent_append(self, basepath) -> Self:
        new_parent = str(basepath) + '/' + str(self.parent)
        return self.with_parent(new_parent)


class FilePathAbs(FilePath, Path):
    """Extension of the FilePath class for absolute paths."""


class TempfilePath(FilePathAbs):
    """Class for manipulation tempfiles' names."""

    # _files = weakref.WeakValueDictionary()  # dict to store path_str:object pairs
    # _preserved = weakref.WeakSet()  # set of preserved files
    _files = set()
    _preserved = set()

    nameroot = 'tmp{:d}_'.format(os.getpid())

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls, *args)
        if obj.exists():
            raise OSError(f"Can't create tempfile. File '{obj}' already exists.")
        if str(obj) in cls._files:
            raise ValueError(f"Path '{obj}' is already used by different tempfile.")
        try:  # Check file is writable
            obj.touch()
            obj.unlink()
        except OSError as ex:
            raise OSError(f"Can't create Tempfile. Path '{obj}' is not valid or "
                          "the host directory is not writable or absent.") from ex
        return obj

    def __init__(self, *args, preserve=False):
        self._files.add(str(self))

    def __del__(self):
        """Remove the file when the object is being deleted."""
        _str = str(self)
        if _str in self._files and _str not in self._preserved:
            if self.exists():
                self.unlink()
            self._files.remove(_str)

    def __truediv__(self, other):
        """Return self / other."""
        raise TypeError(f"Unsupported operation for {self.__class__}")

    @classmethod
    def cleanup(cls):
        """Force removing all the created files. Should be used only with atexit and such."""
        for _str in cls._files:
            if _str not in cls._preserved:
                if os.path.exists(_str): os.remove(_str)

    @property
    def preserved(self):
        """Turn off automatic removing of the file."""
        return str(self) in self._preserved

    @preserved.setter
    def preserved(self, val: bool):
        if val is True:
            self._preserved.add(self)
        elif val is False:
            self._preserved.discard(self)
        else:
            raise TypeError('Must be bool value')

    @classmethod
    def generate_from(cls, path: Union[str, os.PathLike], new_suffix: str = None,
                      hidden: bool = True, unique: bool = False):
        """Generate the name of a tempfile based on text."""
        prefix = '.' if hidden else ''
        prefix += str(cls.nameroot)
        prefix += '{:}_'.format(hex(time.time_ns())[-6:]) if unique else ''
        pathobj = FilePath(path).absolute().with_stem_starting(prefix)
        if new_suffix != None: pathobj = pathobj.with_suffix(new_suffix)
        return cls(pathobj)

    @classmethod
    def generate(cls, extension='.tmp', hidden: bool = True):
        """Generate an unique name."""
        text = str(hex(time.time_ns())) + str(extension)
        return cls.generate_from(text, hidden=hidden, unique=False)


# AbsPath companions of the path classes
FilePath._class_abspath = FilePathAbs
FilePathAbs._class_abspath = FilePathAbs
TempfilePath._class_abspath = TempfilePath

# Type for check_ functions
TPath = TypeVar('TPath', bound=Union[str, os.PathLike])
TAbsPath = TypeVar('TAbsPath', bound=FilePathAbs)


class ListofPaths(Sequence):
    """Class to operate with lists of files to be processed."""

    def __new__(cls, paths: Iterable[TPath], *, basepath: TPath | None = None):
        return cls._create_with_paths(paths, basepath)

    @classmethod
    def _create_with_paths(cls, lst, prepath=None, postpath=None):
        obj = object.__new__(cls)
        prepath = os.fspath(prepath or '')
        postpath = os.fspath(postpath or '')
        obj._list = [FilePath('/'.join([y for y in (prepath, str(x), postpath) if y]))
                     for x in lst]
        return obj

    def __getitem__(self, index):
        if not isinstance(index, int):
            raise ValueError(f"Index can be only int, not {type(index)}.")
        return self._list[index]

    def __setitem__(self, index, value):
        self._list[index] = FilePath(value)

    def __len__(self):
        return len(self._list)

    def __str__(self):
        return self.__class__.__name__ + f'({str(self._list)})'

    def __add__(self, other: Self) -> Self:
        if isinstance(other, ListofPaths):
            return self.__class__._create_with_paths(self._list + other._list)

    def __truediv__(self, path: str | os.PathLike) -> Self:
        """Return self / path."""
        return self.__class__._create_with_paths(self, postpath=path)

    def __rtruediv__(self, path: str | os.PathLike) -> Self:
        """Return path / self."""
        return self.__class__._create_with_paths(self, prepath=path)

    def names(self) -> Self:
        """Get only file names, remove dirnames."""
        return self.__class__([x.name for x in self])

    def copy(self) -> Self:
        return self.__class__._create_with_paths(self)

    def absolute(self, basepath: TPath | None = None) -> Self:
        """Return List with absolute paths."""
        basepath = basepath or os.getcwd()
        if basepath[0] != '/':
            raise ValueError(f"Path basepath='{basepath}' is not absolute.")
        return self.__class__([FilePathAbs(basepath, x) for x in self._list])


#######################################################
#### Terminal output, logging and colored printing ##############

_COLOR_SEQUENCES = {'red': '91m', 'yellow': '93m', 'green': '92m',
                    'cyan': '96m', 'bold': '01m'}


class _ColorsMixin():
    """Provide self.print() for the 'Color' enum."""

    def print(self, text):
        print('\033[' + _COLOR_SEQUENCES[self.name] + text + '\033[0m')


Colors = StrEnum('Colors', names=list(_COLOR_SEQUENCES.keys()), type=_ColorsMixin)


def print_colored_text(text: str, color: Colors):
    """Color the output."""
    Colors(color).print(text)


class _Logger():
    """Private static class fo provide logging facilities."""

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

    def __prepare_text(self, text: str, *, progname: str = None, msgtype: str = ''):
        """Inject progname ans msgtype to the string message."""
        if progname is None:  # Use None to get default and '' for empty progname
            progname = self._getprogname()
        progtxt = f'[{progname}]:' if progname else ''  # Use ''
        return ' '.join([x for x in [progtxt, msgtype, text] if x])

    def __log_text(self, text: str) -> None:
        """Put the text into the logfile."""
        if self._flogfile:
            timestamp = time.strftime('%Y %b %d %H:%M:%S', time.localtime())
            self._flogfile.write(timestamp + ' - ' + text + '\n')
            self._flogfile.flush()

    def onlylog(self, text: str, progname: str = None, msgtype: str = '') -> None:
        self.__log_text(self.__prepare_text(text, progname=progname, msgtype=msgtype))

    def print_colored_and_log(self, text: str, progname: str = None,
                              msgtype: str = '', color: Colors = None):
        _text = self.__prepare_text(text, progname=progname, msgtype=msgtype)
        if color and self.force_bw == False:
            color.print(_text)
        else:
            print(_text)
        self.__log_text(_text)
        return text


logger = _Logger()


def set_logfile(path: str | FilePath | None, append: bool = False):
    if path is not None:
        if append == False and os.path.exists(path):
            raise OSError(f"Can't create '{path}', the file already exists.")
        logger.open_logfile(path)
    else:
        logger.close_logfile()


def debug(*args):  # print debug output
    """Print dubug message in cyan."""
    text = ' '.join(str(x) for x in args)
    logger.print_colored_and_log(text, color=Colors.cyan, msgtype='DEBUG:')


# Create functions with names 'print+color' and add them into namespace
# They return the printed text to pass it to Exception message
printred = printyellow = printcyan = None  # To not show 'Undefined name' error below
for color in Colors:
    locals()['print' + color.name] = functools.partial(logger.print_colored_and_log, color=color)
printandlog = functools.partial(logger.print_colored_and_log, color=None)
printerr = functools.partial(printred, msgtype='Error:')
printwarn = functools.partial(printyellow, msgtype='Warning:')
printinfo = functools.partial(logger.print_colored_and_log, color=None, msgtype='Info:')
printcaption = printcyan
logtext = logger.onlylog
callandlog = logger.callandlog
DEB = DEUG = debug


def die(text: str, progname: str = None):
    """Print error message and exit."""
    printerr(text, progname)
    sys.exit(1)


def getownname():
    """Return the name of the function that calls this."""
    return inspect.stack()[1][3]


def change_terminal_caption(text: str):
    print('\33]0;{}\a'.format(text), end='', flush=True)


###########################################################################
#### Some functions and classes to use in custom scripts #################


class Actions(StrEnum):
    """Enum of the Actions that we can do if some error arose.

    Available actions:

    * **DIE**       Print error message and quit the script with bad exit code.
    * **ERROR**     Print error message and continue.
    * **WARNING**   Print warning message and continue.
    * **EXCEPTION** Raise exception.
    * **NOTHING**   Print nothing and continue.
    """

    DIE = auto()
    ERROR = auto()
    WARNING = auto()
    EXCEPTION = auto()
    NOTHING = auto()

    def do(self, text: str, *, progname: str = None,
           exception_class: Type[Exception] = Exception, **kwargs):

        cls = self.__class__
        match self:
            case cls.NOTHING:
                return
            case cls.DIE:
                die(text, progname)
            case cls.WARNING:
                printwarn(text, progname)
            case cls.ERROR:
                printerr(text, progname)
            case cls.EXCEPTION:
                raise exception_class(text, **kwargs)


# def _check_option_is_allowed(argument:str, allowed_values:list, with_arg=''):
#     """Check if argument is valid or raise KeyError."""
#     if argument not in allowed_values:
#         if with_arg:
#             raise KeyError("argument value '{}' is not allowed together with argument '{}'".format(argument,with_arg))
#         else:
#             raise KeyError("argument value '{}' is not allowed.".format(argument))
#     return True
#
#
# def check_keywords_are_allowed(dict_to_test:dict, allowed_keys:list):
#     """Check keyword of the dict are valid or raise KeyError."""
#     # if len(dict_to_test) == 0:
#     #     raise KeyError('empty dicts is not allowed')
#     for key in dict_to_test.keys():
#         if key not in allowed_keys:
#             raise KeyError("keyword '{}' is not allowed".format(key))
#     return True


# def _to_abspath(*args, target_class: type = FilePath, **class_kwargs):
#     types_to_check = [target_class]
#     if hasattr(target_class, '_class_abspath'):  # Add absolute path version
#         types_to_check.append(target_class._class_abspath)
#     if len(args) > 1 or not isinstance(args[0], tuple(types_to_check)):
#         filepath = target_class(*args, **class_kwargs)
#     else:
#         filepath = args[0]
#     if not filepath.is_absolute():
#         filepath = filepath.absolute()
#     return filepath


def check_file_exists(filepath: Union[str, FilePath],
                      action: Union[Actions, str] = Actions.DIE,
                      progname: str = None) -> TAbsPath | None:
    """Check if the file exists and return its absolute path.
    
    It returns absolute path of the file or performs the 'action' (raise exception
    by default) and returns None if the file doesn't exist.
    """
    pathobj = FilePath(filepath).absolute()
    if not pathobj.exists():
        Actions(action).do(f"File '{filepath}' is not found", progname=progname,
                           exception_class=FileNotFoundError)
        return None
    return pathobj


def check_file_not_exist_or_remove(
        filepath: Union[FilePath, str],
        override: bool = False, action: Union[Actions, str] = Actions.DIE,
        extra_text: str = '', progname: str = None, remove_warning: bool = True,
        exception_class: Type[Exception] = FileExistsError) -> TAbsPath | None:
    """Check if the file doesn't exist to further create it.
    
    Return absolute path if the file doesn't exist or if it's allowed to override it.
    If the option 'overwrite' is True, the existing file will be removed. 
    Otherwise, it performs the 'action' (raise exception by default) and returns None.
    
    :param filepath: Path to check.
    :param override: If True, existing file will be removed. The default is False.
    :param action: Perform the Actions if file exists and can't be removed.
        The default is Actions.DIE.
    :param extra_text: Additional text to provide addtional informtaion
        in the error message.
    :param progname: Progname to print error message.
    :param remove_warning: Print warning if file exists, but it's allowed to be deleted.
        If false, the file will be deleted silently. The default is True.
    :param exception_class: Exception class for Actions.EXCEPTION. The default is FileExistsError.
    :return: Absolute path to the file being tested.
    """
    pathobj = FilePath(filepath).absolute()
    if pathobj.exists():
        if override:
            pathobj.unlink()
            if remove_warning:
                printwarn(f"File '{filepath}' will be replaced", progname=progname)
        else:
            Actions(action).do(f"File '{filepath}' already exists. " + extra_text,
                               progname=progname, exception_class=exception_class)
            return None
    return pathobj


def logger_turn_on(logfile: Union[str, FilePath],
                   progname: str = None) -> None:
    """Turn on the logging in the user's scripts.

    Helper function that checks presence of the logfile, enables logging and
    writes starting message with sys.argv parameters of the script. If the file
    at provided path exists, it prints error and calls sys.exit().

    :param logfile: Path to logfile.
    :param progname: Name of script to write it in the logfile.
    """
    path = check_file_not_exist_or_remove(
        logfile, override=False, action=Actions.DIE,
        extra_text='Please use another name or remove it manually.')
    set_logfile(path)
    args = sys.argv.copy()
    args[0] = os.path.basename(args[0])
    logtext('Started as "{}"'.format(' '.join(args)), progname)


@functools.singledispatch
def check_files_in_list_exist(filelist, basepath: str = None,
                              action: Actions = Actions.DIE, progname=None):
    """Call Path.exists() for each file in the list.
    
    The filelist argument can be the path to an ascii file, a ListofPaths object
    or just a python list. The list can contain absolute or relative paths and 
    also can be augmented with 'basepath' argument. If the input is an ascii
    file, the relative paths are assumed to refer to the folder that owns 
    the ascii file; strings starting with '#' will be ignored. The function returns 
    the ListofPaths object with absolute paths or performs 'action' if 
    an error occurs.
    """
    raise TypeError("Unsupported type {} of 'filelistobj' argument".format(type(filelist)))


@check_files_in_list_exist.register(list | tuple | ListofPaths)
def _check_files_in_list_exist_list(filelist, basepath: str = None,
                                   action: Actions = Actions.DIE, progname: str = None):
    if not isinstance(filelist, ListofPaths):
        filelist = ListofPaths(filelist, basepath=basepath)  # Convert each element to FilePath
    good_files, bad_files = [], []
    for item in map(lambda x: x.absolute(), filelist):
        if item.exists():
            good_files.append(item)
        else:
            bad_files.append(item)
    if len(bad_files) > 0:
        Actions(action).do(
            "File '{}' ({:d} of {:d} in total) is not found".format(
                bad_files[0], len(bad_files), len(filelist)), 
            progname=progname, exception_class=FileNotFoundError)
    return ListofPaths(good_files)


@check_files_in_list_exist.register(FilePathAbs)
def _check_files_in_list_exist_path(filelist: FilePathAbs, basepath: str = None,
                                   action: Actions = Actions.DIE, progname=None, **kwargs):
    basepath = basepath or filelist.parent
    listobj = ListofPaths(read_ascii_filelist(filelist, **kwargs)).absolute(basepath)
    return _check_files_in_list_exist_list(listobj, action=action, progname=progname)

@check_files_in_list_exist.register(str)
def _check_files_in_list_exist_str(filelist: FilePathAbs, basepath: str = None,
                                   action: Actions = Actions.DIE, progname=None, **kwargs):
    filelist = check_file_exists(filelist, Actions.DIE, progname)
    return _check_files_in_list_exist_path(filelist, basepath, action=action, progname=progname)


def read_ascii_filelist(ascii_path: TPath, comment_symbol: str = '#') -> list:
    """Read ascii file ignoring comments."""
    files = []
    with open(ascii_path, 'r') as fl:  # R ead lines from file
        for line in fl:
            stripped = line.strip()
            if not stripped.startswith(comment_symbol):  # Remove lines starting with #
                word = stripped.split(comment_symbol)[0]
                # Now we'll try to check that the file is really a file list and
                # not a random file with text
                if len(word.split(' ')) > 1:
                    die("Wrong format of ASCII filelist. Filenames mustn't contain "
                        f"spaces but string '{word}' does.")
                files.append(word.strip())  # Remove comments at the end of the line
    return files


#################################################
#### Additional useful classes #################


class ROdict(Mapping):
    """Dict with protected (read only) items.

    Ready only item can be created by adding '__' to the key. Further this item
    can be overridden using '__' prefix but cannot be changed directly with its key.
    For objects with copy() method, the dict saves a copy and returns a copy
    of the saved object. Keys must be strings.
    """

    def __init__(self, *args: Mapping, **kwargs: Any):
        initdict, self._dict, self._protected = {}, {}, set()
        # if len(args)>0:
        for arg in args:
            initdict.update(self.__to_initdict(arg))
        initdict.update(kwargs)
        for key, val in initdict.items():
            if testres := self._test_under(key):
                self._item_add_new_as_under(testres['key'], val, init=True, dbl=testres['dbl'])
            else:
                self._item_add_new_as_normal(key, val, init=True)

    @staticmethod
    def __to_initdict(obj: Mapping) -> dict:
        """Convert obj to kwargs appropriate for __init__ if obj is of the ROdict type"""
        if not isinstance(obj, Mapping):
            raise TypeError(f"Unsupported type of the argument: {type(obj)}")
        if isinstance(obj, ROdict):
            return {'__' + k: v for k, v in obj._dict.items() if k in obj._protected} | \
                {k: v for k, v in obj._dict.items() if k not in obj._protected}
        else:
            return dict(obj)

    @staticmethod
    def _test_under(key) -> bool | dict:
        """Test whether the passed key stars from '_' or '__'."""
        if not isinstance(key, str):
            raise TypeError(f"Wrong key '{key}'. Only string keys are supported.")
        if key.startswith('_'):  # '_key'
            dbl = False
            key = key[1:]
            if key.startswith('_'):  # '__key'
                key = key[1:]
                dbl = True
            return dict(key=key, dbl=dbl)
        return False

    @staticmethod
    def _val_copy(val):
        if hasattr(val, 'copy'):
            if callable(val.copy):
                return val.copy()
        else:
            return val

    # ########################################
    # Functions to be overridden in subclasses

    def _item_add_new_as_under(self, key, val, dbl: bool, init: bool = False):
        """Add a new item through '_key'."""
        self._item_change_existing_as_under(key, val, dbl)

    def _item_add_new_as_normal(self, key, val, init: bool = False):
        """Add a new item through the normal key (without any '_')."""
        if init is True:
            self._dict[key] = self._val_copy(val)
        else:
            raise TypeError("Adding new items is not allowed")

    def _item_change_existing_as_under(self, key, val, dbl: bool):
        """Replace an existing item through '_key'."""
        self._dict[key] = self._val_copy(val)
        if dbl is True:  # Double underscore: '__key'
            self._protected.add(key)
        else:
            self._protected.discard(key)

    def _item_change_existing_as_normal(self, key, val):
        """Replace an existing item through the normal key."""
        if key in self._protected:
            raise KeyError(f"Entry '{key}' is read-only.")
        else:
            self._dict[key] = self._val_copy(val)

    def _item_get_existing_as_under(self, key, dbl: bool):
        """Read an existing item through '_key'."""
        return self._dict[key]

    def _item_get_missing_as_under(self, key, dbl: bool):
        """Try to access a missing item through '_key'."""
        self._item_get_missing_as_normal(key)

    def _item_get_existing_as_normal(self, key):
        """Read an existing item through the normal key."""
        return self._val_copy(self._dict[key])

    def _item_get_missing_as_normal(self, key):
        """Try to access a missing item through the normal key."""
        raise KeyError(f"Entry '{key}' doesn't exist.")

    def _item_del_existing_as_under(self, key, dbl: bool):
        """Delete an existing item through '_key'."""
        self._protected.discard(key)
        del self._dict[key]

    def _item_del_missing_as_under(self, key, dbl: bool):
        """Try to delete a missing item through '_key'."""
        self._item_del_missing_as_normal(key)

    def _item_del_existing_as_normal(self, key):
        """Delete an existing item through the normal key."""
        raise TypeError("Deletion is not allowed")

    def _item_del_missing_as_normal(self, key):
        """Try to delete a missing item through the normal key."""
        raise KeyError(f"Entry '{key}' doesn't exist.")

    # ####################################

    def __getitem__(self, key):
        """Return self[key]."""
        if testres := self._test_under(key):
            if testres['key'] in self._dict:
                return self._item_get_existing_as_under(**testres)
            else:
                return self._item_get_missing_as_under(**testres)
        else:
            if key in self._dict:
                return self._item_get_existing_as_normal(key)
            else:
                return self._item_get_missing_as_normal(key)

    def __setitem__(self, key, val):
        """Set self[key] to value."""
        if testres := self._test_under(key):
            if testres['key'] in self._dict:
                self._item_change_existing_as_under(testres['key'], val, dbl=testres['dbl'])
            else:
                self._item_add_new_as_under(testres['key'], val, dbl=testres['dbl'], init=False)
        else:
            if key in self._dict:
                self._item_change_existing_as_normal(key, val)
            else:
                self._item_add_new_as_normal(key, val, init=False)

    def __delitem__(self, key):
        """Delete self[key]."""
        if testres := self._test_under(key):
            if testres['key'] in self._dict:
                self._item_del_existing_as_under(**testres)
            else:
                self._item_del_missing_as_under(**testres)
        else:
            if key in self._dict:
                self._item_del_existing_as_normal(key)
            else:
                self._item_del_missing_as_normal(key)

    def rokeys(self):
        """Return iter through list of read-only keys."""
        yield from self._protected

    def __len__(self):
        """Return number of entries in the dict."""
        return len(self._dict)

    def __iter__(self):
        """Iterate through the dict keys."""
        yield from self._dict

    def __str__(self):
        """Return string representation."""
        br = ', '.join(
            [f'{k}*: {v}' for k, v in self._dict.items() if k in self._protected] +
            [f'{k}: {v}' for k, v in self._dict.items() if k not in self._protected])
        return self.__class__.__name__ + f' {{{br}}}'

    def dict(self):
        """Return standard python dict."""
        return dict(self)

    def copy(self):
        """Return a copy."""
        return self.__class__(self)


