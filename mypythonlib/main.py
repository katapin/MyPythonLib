"""Methods to perform basic checks like existence of input files and so on."""

import sys, os
import functools, inspect
from enum import StrEnum, auto
from typing import Union, Type, TypeVar
from ._private.logger import _OutputProcessor, Colors
from ._private.pathlibext import FilePath, FilePathAbs, TPath, TAbsPath

__all__ = [
    "Actions",
    "check_file_exists",
    "check_file_not_exist_or_remove",
    "change_terminal_caption",
    "die",
    "getownname",
    "logger_turn_on",
    "callandlog",
    "logtext",
    "print_colored_text",
    "printbold",
    "printgreen",
    "printcyan",
    "printcaption",
    "printerr",
    "printred",
    "printwarn",
    "printyellow",
    "printinfo",
    "printandlog"
]

#################################################################
#### Print colored messages and log the output

logger = _OutputProcessor()


def set_logfile(path: TPath | None, append: bool = False):
    if path is not None:
        if append == False and os.path.exists(path):
            raise OSError(f"Can't create '{path}', the file already exists.")
        logger.open_logfile(path)
    else:
        logger.close_logfile()


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


# Create functions with names 'print+color' and add them into namespace
# They return the printed text to pass it to Exception message
printred = printyellow = printcyan = printgreen = printbold = None  # To not show 'Undefined name' error below
for color in Colors:
    locals()['print' + color.name] = functools.partial(logger.print_colored_and_log, color=color)
printandlog = functools.partial(logger.print_colored_and_log, color=None)
printerr = functools.partial(printred, msgtype='Error:')
printwarn = functools.partial(printyellow, msgtype='Warning:')
printinfo = functools.partial(logger.print_colored_and_log, color=None, msgtype='Info:')
printcaption = printcyan
logtext = logger.onlylog
callandlog = logger.callandlog


def print_colored_text(text: str, color: Colors):
    """Color the output (without logging)."""
    Colors(color).print(text)



def getownname():
    """Return the name of the function that calls this."""
    return inspect.stack()[1][3]


def change_terminal_caption(text: str):
    print('\33]0;{}\a'.format(text), end='', flush=True)


def die(text: str, progname: str = None):
    """Print error message and exit."""
    printerr(text, progname)
    sys.exit(1)


###########################################################################
#### Perform checkes in custom scripts #################


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