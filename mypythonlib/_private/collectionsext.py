"""My extension of the python collections."""

from collections.abc import Mapping
from typing import Any

__all__ = ['ROdict']


class ROdict(Mapping):
    """Dict with protected (read only) items.

    A read only item can be created by adding '__' to the key. Further this item
    can be overridden using '__' prefix but cannot be changed directly with its key.
    For objects with copy() method, the dict saves a copy and returns a copy
    of the saved object. Keys must be strings. The main idea was to partially
    reproduce the behaviour of columns in the astropy tables where one can replace
    a data vector by numpy's broadcasting but can't assign other object (or a vector
    of different length). Behaviour for the cases when the key is absent/new/exist
    is separated to  specific functions to be tuned on subclasses (e.g.
    raise exception with custom text).
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


