from .base import BaseCollector
from .mijnafvalwijzer import MijnAfvalwijzerCollector
from .burgerportaal import BurgerportaalCollector
from .opzet import OpzetCollector
from .factory import make_collector

__all__ = [
    "BaseCollector",
    "MijnAfvalwijzerCollector",
    "BurgerportaalCollector",
    "OpzetCollector",
    "make_collector",
]
