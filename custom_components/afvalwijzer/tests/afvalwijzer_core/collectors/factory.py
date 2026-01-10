from collections.abc import Callable

from ..const import (
    COLLECTORS_BURGERPORTAAL,
    COLLECTORS_MIJNAFVALWIJZER,
    COLLECTORS_OPZET,
)
from .burgerportaal import BurgerportaalCollector
from .mijnafvalwijzer import MijnAfvalwijzerCollector
from .opzet import OpzetCollector


def make_collector(
    family: str,
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    waste_type_rename: Callable[[str], str | None],
):
    family = (family or "auto").strip().lower()
    provider = (provider or "").strip().lower()

    if family == "opzet":
        return OpzetCollector(
            provider=provider,
            postal_code=postal_code,
            street_number=street_number,
            suffix=suffix,
            waste_type_rename=waste_type_rename,
        )

    if family == "mijnafvalwijzer":
        return MijnAfvalwijzerCollector(
            provider=provider,
            postal_code=postal_code,
            street_number=street_number,
            suffix=suffix,
            waste_type_rename=waste_type_rename,
        )

    if family == "burgerportaal":
        return BurgerportaalCollector(
            provider=provider,
            postal_code=postal_code,
            street_number=street_number,
            suffix=suffix,
            waste_type_rename=waste_type_rename,
        )

    if family == "auto":
        if provider in COLLECTORS_MIJNAFVALWIJZER:
            return MijnAfvalwijzerCollector(
                provider=provider,
                postal_code=postal_code,
                street_number=street_number,
                suffix=suffix,
                waste_type_rename=waste_type_rename,
            )

        if provider in COLLECTORS_BURGERPORTAAL:
            return BurgerportaalCollector(
                provider=provider,
                postal_code=postal_code,
                street_number=street_number,
                suffix=suffix,
                waste_type_rename=waste_type_rename,
            )
        if provider in COLLECTORS_OPZET:
            return OpzetCollector(
                provider=provider,
                postal_code=postal_code,
                street_number=street_number,
                suffix=suffix,
                waste_type_rename=waste_type_rename,
            )

    raise ValueError(f"Unknown collector family: {family}")
