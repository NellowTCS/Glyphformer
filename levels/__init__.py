"""
Level registry: import each level module and collect them in a list.
Add new levels here by importing and appending.
"""

from . import level_00
from . import level_01
from . import level_02

LEVELS = [
    level_00.level,
    level_01.level,
    level_02.level,
]
