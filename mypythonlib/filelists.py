

import os
from typing import Self
import functools
from collections.abc import Sequence, Iterable
from ._private.pathlibext import FilePath, FilePathAbs, TPath
from .main import die, Actions, check_file_exists


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

