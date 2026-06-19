"""
Level registry: import each level module and collect them in a list.
"""

from . import level_00
from . import level_01
from . import level_02
from . import level_03
from . import level_04

LEVELS = [
    level_00.level,
    level_01.level,
    level_02.level,
    level_03.level,
    level_04.level,
]