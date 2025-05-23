import importlib

from . import autocomplete
from .ssleague import *  # noqa: F401, F403

print(autocomplete.__file__)
print(autocomplete.__name__)
print(autocomplete.__package__)
print(autocomplete.__path__)
importlib.reload(autocomplete)
