from datetime import datetime
import random
from base64 import b64encode
import base64
import inspect
import json

from flask_caching import Cache

from hashlib import md5
import hashlib


class OrderNumberGenerator:
    def generate(self, aCart):
        monkey_species = ['BABOON', 'MONKEY', 'APE', 'GORILLA', 'CAPUCHIN', 'TAMARIN', 'GIBBON']
        specie = random.choice(monkey_species)

        num = 'WEB{0}-{1}-{2}'.format(specie,
                                      datetime.strftime(datetime.now(), '%Y%m%d'),
                                      str(abs(42+hash(datetime.now())))[:4])
        return num


class ResourceCache(Cache):
    """
    A customized version of Cache that works with FlaskApiSpec Resources (removes self arg)
    """
    def _memoize_make_cache_key(
        self,
        make_name=None,
        timeout=None,
        forced_update=False,
        hash_method=hashlib.md5,
    ):
        """Function used to create the cache_key for memoized functions."""

        def make_cache_key(f, *args, **kwargs):
            _timeout = getattr(timeout, "cache_timeout", timeout)
            fname, version_data = self._memoize_version(
                f, args=self._extract_self_arg(f, args), timeout=_timeout, forced_update=forced_update
            )

            #: this should have to be after version_data, so that it
            #: does not break the delete_memoized functionality.
            altfname = make_name(fname) if callable(make_name) else f

            if callable(f):
                keyargs, keykwargs = self._memoize_kwargs_to_args(
                    f, *args, **kwargs
                )
            else:
                keyargs, keykwargs = args, kwargs

            updated = u"{0}{1}{2}".format(altfname, self._extract_self_arg(f, keyargs), keykwargs)

            cache_key = hash_method()
            cache_key.update(updated.encode("utf-8"))
            cache_key = base64.b64encode(cache_key.digest())[:16]
            cache_key = cache_key.decode("utf-8")
            cache_key += version_data

            return cache_key

        return make_cache_key

    @staticmethod
    def _extract_self_arg(f, args):
        argspec_args = inspect.getargspec(f).args

        if argspec_args and argspec_args[0] in ('self', 'cls'):
            if hasattr(args[0], '__name__'):
                return (args[0].__name__,) + args[1:]
            return (args[0].__class__.__name__,) + args[1:]
        return args
