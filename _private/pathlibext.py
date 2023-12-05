"""Some classes extending the standard library's PurePath."""

import os
import time
from typing import Self, TypeVar, Union
from pathlib import Path, PurePosixPath

__all__ = ['FilePath',
           'FilePathAbs',
           'TempfilePath']

TPath = TypeVar('TPath', bound=Union[str, os.PathLike])
TAbsPath = TypeVar('TAbsPath', bound='FilePathAbs')


class FilePath(PurePosixPath):
    """Extension of pathlib's PurePath.

    The main purpose of this class is to provide methods for editing
    the stem of the filename (like adding suffix or prefix) and be
    the baseclass for TempfilePath and ExtPath classes.
    """

    _class_abspath = None  # abspath  brother class, to be redefined below

    def __new__(cls, *args):
        drv, root, parts = cls._parse_args(args)
        # Explicitly call the own method with cls argument passed to not
        # break myfits.ExtPath
        return FilePath._from_parsed_parts.__func__(cls, drv, root, parts)

    @classmethod
    def _from_parsed_parts(cls, drv, root, parts):
        """Construct object from parts

        Unfortunately PurePath use some 'magic' bypassing the standard
        initializer and constructor. So we have override the PurePath's
        classmethod that actually creates the object.
        """
        if root:  # Path is absolute
            obj = object.__new__(cls._class_abspath)  # Create empty object
        else:    # Path is not absolute
            if cls is cls._class_abspath:   # but the target class is for abspath
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
    """Class for manipulation names of tempfiles.

    This class is designed to create names of less important files
    (e.g. intermediate stages in data processing pipelines) for
    passing them to external excutables. These files are usually
    unnecessary but sometimes one may desire to check their content.
    So they must have unique but understandable names (hashes are
    not appropriate) and should be removed by default. We'll use
    the pid as a prefix (to recognize which run produced the specific
    file) and a unix nanoseconds to make the name unique. Also, the
    user can pass the name manually.
    """

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
    def generate_from(cls, path: str | os.PathLike, new_suffix: str = None,
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