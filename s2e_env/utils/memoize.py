import collections
import functools


class memoize(object):
    """
    Memoize dectorator.

    Caches a function's return value each time it is called. If called later
    with the same arguments, the cache value is returned (not reevaluated).

    Taken from https://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
    """

    def __init__(self, func):
        self._func = func
        self._cache = {}

    def __call__(self, *args):
        if not isinstance(args, collections.Hashable):
            return self._func(args)
        if args in self._cache:
            return self._cache[args]
        else:
            value = self._func(*args)
            self._cache[args] = value
            return value

    def __repr__(self):
        # Return the function's docstring
        return self._func.__doc__

    def __get__(self, obj, objtype):
        # Support instance methods
        return functools.partial(self.__call__, obj)
