import importlib
import sys

from . import autocomplete
from .ssleague import *  # noqa: F401, F403

if autocomplete.__name__ in sys.modules:
    print("Reload autocomplete")
    importlib.reload(autocomplete)
