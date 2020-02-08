"""
Copyright (c) 2013-2014 Dependable Systems Laboratory, EPFL
Copyright (c) 2018 Cyberhaven

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from collections import MutableMapping
from pytrie import SortedStringTrie as Trie


class CaseInsensitiveStringMixin:
    def __eq__(self, other):
        return self.lower() == other.lower()

    def __cmp__(self, other):
        return self.lower().__cmp__(other.lower())

    def __hash__(self):
        return hash(self.lower())


class CaseInsensitiveStr(CaseInsensitiveStringMixin, str):
    pass


class CaseInsensitiveUnicode(CaseInsensitiveStringMixin, str):
    pass


def case_insensitive(string):
    if isinstance(string, str):
        return CaseInsensitiveUnicode(string)
    if isinstance(string, str):
        return CaseInsensitiveStr(string)
    raise Exception('Invalid object')


class CaseInsensitiveDict(MutableMapping):
    """
    This is a dictionary that is case insensitive for lookups.
    It preserves the case of the keys.
    It also allows looking up the keys by prefix.
    """
    def __init__(self, *args, **kwargs):
        self._dict = {}
        self._trie = Trie(*args, **kwargs)

        d = dict(*args, **kwargs)
        for key, value in d.items():
            self._dict[case_insensitive(key)] = value

    def __contains__(self, key):
        return case_insensitive(key) in self._dict

    def __delitem__(self, key):
        cl = case_insensitive(key)
        del self._trie[key.lower()]
        del self._dict[cl]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __getitem__(self, key):
        return self._dict[case_insensitive(key)]

    def __setitem__(self, key, value):
        cl = case_insensitive(key)
        self._trie[key.lower()] = value
        self._dict[cl] = value

    def has_key(self, key):
        return self.__contains__(key.lower())

    def prefixed_keys(self, prefix):
        return self._trie.keys(prefix.lower())
