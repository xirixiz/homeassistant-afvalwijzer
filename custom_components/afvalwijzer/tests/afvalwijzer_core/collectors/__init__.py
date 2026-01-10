from .base import BaseCollector
from .burgerportaal import BurgerportaalCollector
from .factory import make_collector
from .mijnafvalwijzer import MijnAfvalwijzerCollector
from .opzet import OpzetCollector

__all__ = [
    "BaseCollector",
    "MijnAfvalwijzerCollector",
    "BurgerportaalCollector",
    "OpzetCollector",
    "make_collector",
]
