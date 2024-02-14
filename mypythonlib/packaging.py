"""Methods for manipulations with packages."""

from importlib.resources import files


def getmainname(packagedunder: str) -> str:
    """Return name of the main package from __package__."""
    if packagedunder is not None:
        return packagedunder.split('.')[0]


def getrootpath(packagedunder: str):
    """Return PosixPath to the package root dir"""
    return files(getmainname(packagedunder))