"""Tests for waste type labels that other integrations map but we used to pass through."""

import pytest

from custom_components.afvalwijzer.collector import (
    amsterdam,
    mijnafvalwijzer,
    opzet,
    ximmio,
)
from custom_components.afvalwijzer.common.main_functions import waste_type_rename


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("DROCO", "papier"),
        ("ZWAKRA", "pmd"),
        ("KERST", "kerstbomen"),
        ("pruning", "snoeiafval"),
        ("residual", "restafval"),
        ("md", "pmd"),
        ("kcalocatie", "kca-locatie"),
        ("dhm", "papier-pmd"),
        ("pbd/papier", "papier-pmd"),
        ("restgft", "rest-gft"),
        ("GREENGREY", "rest-gft"),
        ("etensresten", "gft"),
        ("rest+pmd", "pmd-restafval"),
        ("Zachte plastics", "zachte-plastics"),
        ("Roze zak", "zachte-plastics"),
        ("Groot huisvuil", "grofvuil"),
        ("Huisvuil", "restafval"),
        ("OMB", "restafval"),
        ("Ordures ménagères", "restafval"),
        ("Déchets résiduels", "restafval"),
        ("Déchets ménagers résiduels", "restafval"),
        ("Déchets organiques", "gft"),
        ("Rest afval", "restafval"),
    ],
)
def test_label_is_mapped(label, expected):
    """The label maps to a standard key."""
    assert waste_type_rename(label) == expected


def test_meppel_keukenafval_is_still_vet_goed():
    """The Meppel postal code override still wins over the global mapping."""
    assert waste_type_rename("keukenafval", "7941AB") == "vet-goed"


def test_ximmio_plastic_is_pmd():
    """Ximmio's 'plastic' stream is PMD."""
    data = {
        "dataList": [
            {"_pickupTypeText": "PLASTIC", "pickupDates": ["2026-10-05T00:00:00"]}
        ]
    }

    assert ximmio._parse_waste_data_raw(data) == [{"type": "pmd", "date": "2026-10-05"}]


def test_opzet_plastic_is_pmd():
    """Opzet's 'plastic' stream is PMD."""
    data = [{"menu_title": "Plastic", "ophaaldatum": "2026-10-05"}]

    assert opzet._parse_waste_data_raw(data) == [{"type": "pmd", "date": "2026-10-05"}]


def test_amsterdam_plastic_is_pmd_restafval(monkeypatch):
    """Amsterdam collects plastic with the rest waste."""
    monkeypatch.setattr(
        amsterdam,
        "_process_collection_dates",
        lambda *_: [amsterdam.datetime(2026, 10, 5)],
    )
    item = {
        "afvalwijzerFractieCode": "Plastic",
        "afvalwijzerAfvalkalenderFrequentie": "x",
        "afvalwijzerOphaaldagen": "maandag",
    }

    assert amsterdam._parse_waste_data_raw([item]) == [
        {"type": "pmd-restafval", "date": "2026-10-05"}
    ]


@pytest.mark.parametrize("postal_code", ["", "7941AB"])
def test_mijnafvalwijzer_vet_goed_name_type(postal_code):
    """An item whose nameType is vet-goed becomes vet-goed, whatever its type."""
    response = {
        "ophaaldagen": {
            "data": [
                {"type": "keukenafval", "nameType": "vet-goed", "date": "2026-10-05"},
                {
                    "type": "keukenafval",
                    "nameType": "keukenafval",
                    "date": "2026-10-06",
                },
            ]
        }
    }

    result = mijnafvalwijzer._parse_waste_data_raw(response, postal_code)

    assert result[0] == {"type": "vet-goed", "date": "2026-10-05"}
    assert result[1]["date"] == "2026-10-06"
