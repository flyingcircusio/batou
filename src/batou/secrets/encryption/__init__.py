import importlib
import sys

USE_LEGACY = None
_encrypt_module = None


def _pick_module():
    global _encrypt_module

    if _encrypt_module:
        return _encrypt_module

    if USE_LEGACY:
        module_hint = ".age_shellout"
    else:
        try:
            import pyrage

            module_hint = ".pyrage_encryption"
        except ImportError:
            module_hint = ".age_shellout"

    _encrypt_module = importlib.import_module(module_hint, __name__)
    return _encrypt_module


def __getattr__(name):
    module = _pick_module()
    value = getattr(module, name)
    setattr(sys.modules[__name__], name, value)
    return value


def __dir__():
    return dir(_pick_module())
