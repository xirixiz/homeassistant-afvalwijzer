"""Test basic imports of the Afvalwijzer integration."""

from custom_components import afvalwijzer
from custom_components.afvalwijzer import config_flow
from custom_components.afvalwijzer.collector import (
    afvalalert,
    amsterdam,
    burgerportaal,
    circulus,
    deafvalapp,
    irado,
    klikogroep,
    main_collector,
    mijnafvalwijzer,
    montferland,
    omrin,
    opzet,
    rd4,
    recycleapp,
    reinis,
    rova,
    rwm,
    straatbeeld,
    ximmio,
)
from custom_components.afvalwijzer.common import (
    day_sensor_data,
    main_functions,
    next_sensor_data,
    waste_data_transformer,
)
from custom_components.afvalwijzer.const import const
from custom_components.afvalwijzer.const.const import DOMAIN


def test_import_integration():
    """Test that the integration module can be imported."""
    assert afvalwijzer is not None


def test_import_config_flow():
    """Test that the config flow module can be imported."""

    assert config_flow is not None
    assert hasattr(config_flow, "AfvalwijzerConfigFlow")


def test_import_const():
    """Test that the const module can be imported."""

    assert const is not None
    assert hasattr(const, "DOMAIN")


def test_import_collectors():
    """Test that all collector modules can be imported."""

    collectors = [
        afvalalert,
        amsterdam,
        burgerportaal,
        circulus,
        deafvalapp,
        irado,
        klikogroep,
        main_collector,
        mijnafvalwijzer,
        montferland,
        omrin,
        opzet,
        rd4,
        recycleapp,
        reinis,
        rova,
        rwm,
        straatbeeld,
        ximmio,
    ]

    for collector in collectors:
        assert collector is not None


def test_import_common_modules():
    """Test that common utility modules can be imported."""

    assert day_sensor_data is not None
    assert main_functions is not None
    assert next_sensor_data is not None
    assert waste_data_transformer is not None


def test_domain_constant():
    """Test that the DOMAIN constant is correctly defined."""

    assert DOMAIN == "afvalwijzer"
