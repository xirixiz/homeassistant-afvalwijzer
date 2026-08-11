"""Test calendar for AfvalWijzer."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockEntityPlatform,
)

from custom_components.afvalwijzer.calendar import (
    AfvalwijzerCalendar,
    AfvalwijzerTypeCalendar,
    _async_remove_all_calendars,
    _async_remove_legacy_calendar,
    _async_remove_stale_calendars,
    async_setup_entry,
)
from custom_components.afvalwijzer.common.sensor_utils import (
    build_device_info,
    initial_color_for_waste_type,
)
from custom_components.afvalwijzer.const.const import (
    CONF_ENABLE_CALENDAR,
    CONF_SEPARATE_CALENDARS,
    DOMAIN,
)
from homeassistant.helpers import entity_registry as er


def _mock_coordinator(*, raw=None, with_today=None, config=None):
    mock_data = MagicMock()
    mock_data.config = config or {"include_today": True, "provider": "afvalthuis"}
    mock_data.waste_data_raw = raw or []
    mock_data.waste_data_with_today = with_today or {}
    return mock_data


class _FakeCoordinator:
    """Fake coordinator for async_setup_entry tests (supports async_add_listener)."""

    def __init__(self, *, config=None, with_today=None, raw=None):
        self.config = config or {"include_today": True, "provider": "afvalthuis"}
        self.waste_data_with_today = with_today or {}
        self.waste_data_raw = raw or []
        self.listeners = []

    def async_add_listener(self, cb):
        self.listeners.append(cb)
        return lambda: None


def _make_entry(coordinator, hass, entry_id="test_entry"):
    entry = SimpleNamespace()
    entry.entry_id = entry_id
    entry.async_on_unload = MagicMock()
    hass.data[DOMAIN] = {entry_id: {"coordinator": coordinator}}
    return entry


def _make_hass():
    hass = SimpleNamespace()
    hass.data = {}
    return hass


@pytest.mark.asyncio
async def test_calendar_event_parsing_fallback():
    """Without a raw schedule the calendar falls back to next-per-type data."""
    mock_data = _mock_coordinator(
        with_today={
            "gft": "2026-07-09",
            "pmd": date(2026, 7, 10),
            "restafval": datetime(2026, 7, 11),
            "papier": "2026-07-12T00:00:00",
        }
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 4
    assert events[0].summary == "Afvalthuis: GFT"
    assert events[1].summary == "Afvalthuis: PMD"
    assert events[2].summary == "Afvalthuis: Restafval"
    assert events[3].summary == "Afvalthuis: Papier"


@pytest.mark.asyncio
async def test_calendar_full_schedule_multiple_dates_per_type():
    """The raw schedule yields every future pickup, not just the next one."""
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2026-07-09"},
            {"type": "gft", "date": "2026-07-23"},
            {"type": "gft", "date": "2026-08-06"},
            {"type": "restafval", "date": "2026-07-16"},
            {"type": "restafval", "date": "2026-08-13"},
        ]
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 8, 31)
    )
    assert len(events) == 5

    # Only the events inside the requested range are returned
    july_events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )
    assert len(july_events) == 3
    assert {e.start for e in july_events} == {
        date(2026, 7, 9),
        date(2026, 7, 16),
        date(2026, 7, 23),
    }


@pytest.mark.asyncio
async def test_calendar_full_schedule_handles_cache_iso_strings():
    """Raw schedule entries restored from cache store dates as ISO strings."""
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2026-07-09T00:00:00"},
            {"type": "restafval", "date": "2026-07-10T00:00:00+02:00"},
            {"type": "kapot", "date": "geen"},
        ]
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 2
    assert events[0].start == date(2026, 7, 9)
    assert events[1].start == date(2026, 7, 10)


@pytest.mark.asyncio
async def test_calendar_respects_exclude_list():
    """Waste types on the exclude list do not appear in the calendar."""
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2026-07-09"},
            {"type": "papier", "date": "2026-07-10"},
        ],
        config={
            "include_today": True,
            "provider": "afvalthuis",
            "exclude_list": "papier",
        },
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 1
    assert events[0].summary == "Afvalthuis: GFT"


def test_calendar_next_event_groups_types_on_same_date():
    """The next-event state groups all types collected on the same day."""
    today = date.today().isoformat()
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": today},
            {"type": "papier", "date": today},
            {"type": "gft", "date": "2099-01-01"},
        ],
        config={"include_today": True, "provider": "mijnafvalwijzer"},
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")
    event = calendar.event

    assert event is not None
    assert event.start == date.today()
    assert event.summary == "Mijnafvalwijzer: GFT, Papier"


def test_remove_legacy_calendar_cleans_up_pre_2026_1018_orphan():
    """Anyone updating straight from 2026.1017 has an orphan under the old global unique_id."""
    registry = MagicMock()
    registry.async_get_entity_id.return_value = "calendar.afvalwijzer_calendar"

    with patch(
        "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
    ):
        _async_remove_legacy_calendar(SimpleNamespace())

    registry.async_get_entity_id.assert_called_once_with(
        "calendar", DOMAIN, "afvalwijzer_calendar_filtered"
    )
    registry.async_remove.assert_called_once_with("calendar.afvalwijzer_calendar")


def test_remove_legacy_calendar_no_op_when_absent():
    """Nothing is removed once the legacy entity is already gone."""
    registry = MagicMock()
    registry.async_get_entity_id.return_value = None

    with patch(
        "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
    ):
        _async_remove_legacy_calendar(SimpleNamespace())

    registry.async_remove.assert_not_called()


def test_combined_calendar_uses_translated_device_composed_name():
    """The combined calendar's name comes from translation_key, device supplies the prefix."""
    calendar = AfvalwijzerCalendar(_mock_coordinator(), "test_entry_id")

    assert calendar._attr_has_entity_name is True
    assert calendar._attr_translation_key == "calendar"
    assert not hasattr(calendar, "_attr_name")


def test_type_calendar_uses_translated_name_with_type_placeholder_and_matching_icon():
    """A per-type calendar's name is translated with the waste type substituted in."""
    calendar = AfvalwijzerTypeCalendar(_mock_coordinator(), "test_entry_id", "gft")

    assert calendar._attr_has_entity_name is True
    assert calendar._attr_translation_key == "type_calendar"
    assert calendar._attr_translation_placeholders == {"type": "GFT"}
    assert not hasattr(calendar, "_attr_name")
    assert calendar._attr_icon == "mdi:flower"
    assert calendar._attr_unique_id == "afvalwijzer_calendar_test_entry_id_gft"


def test_calendar_device_info_groups_under_address_device():
    """Calendars use the same device_info as sensors, grouping under one device per address."""
    coordinator = _mock_coordinator(
        config={
            "include_today": True,
            "provider": "afvalthuis",
            "postal_code": "1234AB",
            "house_number": "1",
        }
    )

    combined = AfvalwijzerCalendar(coordinator, "test_entry_id")
    per_type = AfvalwijzerTypeCalendar(coordinator, "test_entry_id", "gft")

    assert combined.device_info == build_device_info(coordinator.config)
    assert per_type.device_info == combined.device_info


def test_type_calendar_gets_suggested_initial_color_for_known_type():
    """A per-type calendar for a known waste type gets a one-time suggested color."""
    calendar = AfvalwijzerTypeCalendar(_mock_coordinator(), "test_entry_id", "gft")
    assert calendar.initial_color == "#4CAF50"


def test_type_calendar_has_no_initial_color_for_unmapped_type():
    """A waste type without a known convention doesn't get a guessed color."""
    calendar = AfvalwijzerTypeCalendar(_mock_coordinator(), "test_entry_id", "maas")
    assert calendar.initial_color is None


async def test_type_calendar_initial_color_survives_real_ha_validation(hass):
    """The suggested initial_color passes HA's own registry validation.

    Registers the entity through a real entity platform, exercising
    CalendarEntity.get_initial_entity_options() (the actual cv.color_hex()
    check and registry write HA performs) rather than just reading the
    attribute off a bare instance.
    """
    coordinator = _mock_coordinator(
        config={
            "include_today": True,
            "provider": "mijnafvalwijzer",
            "postal_code": "1234AB",
            "house_number": "1",
        }
    )
    calendar = AfvalwijzerTypeCalendar(coordinator, "test_entry_id", "gft")

    platform = MockEntityPlatform(hass, domain="calendar")
    await platform.async_add_entities([calendar])
    await hass.async_block_till_done()

    registry_entry = er.async_get(hass).async_get(calendar.entity_id)
    assert registry_entry.options["calendar"]["color"] == "#4CAF50"


async def test_calendars_share_one_real_device(hass):
    """Combined and per-type calendars register under the same HA device.

    Registers both through a real entity platform tied to a config entry,
    exercising device_registry.async_get_or_create() end to end rather
    than just comparing device_info dicts directly.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "provider": "mijnafvalwijzer",
            "postal_code": "1234AB",
            "house_number": "1",
        },
    )
    entry.add_to_hass(hass)

    coordinator = _mock_coordinator(config=dict(entry.data))
    combined = AfvalwijzerCalendar(coordinator, entry.entry_id)
    per_type = AfvalwijzerTypeCalendar(coordinator, entry.entry_id, "gft")

    platform = MockEntityPlatform(hass, domain="calendar")
    platform.config_entry = entry
    await platform.async_add_entities([combined, per_type])
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    combined_entry = registry.async_get(combined.entity_id)
    per_type_entry = registry.async_get(per_type.entity_id)

    assert combined_entry.device_id is not None
    assert combined_entry.device_id == per_type_entry.device_id


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_calendar_names_resolve_through_real_ha_translation(hass):
    """translation_key/translation_placeholders resolve to real display names.

    A bare MockEntityPlatform doesn't load platform translations by
    default (that only happens during real platform setup), so this
    triggers it explicitly - otherwise the translation_key/placeholder
    wiring could be silently broken and every test would still pass.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "provider": "mijnafvalwijzer",
            "postal_code": "1234AB",
            "house_number": "1",
        },
    )
    entry.add_to_hass(hass)

    coordinator = _mock_coordinator(config=dict(entry.data))
    combined = AfvalwijzerCalendar(coordinator, entry.entry_id)
    per_type = AfvalwijzerTypeCalendar(coordinator, entry.entry_id, "gft")

    platform = MockEntityPlatform(hass, domain="calendar", platform_name=DOMAIN)
    platform.config_entry = entry
    await platform.platform_data.async_load_translations()
    await platform.async_add_entities([combined, per_type])
    await hass.async_block_till_done()

    assert hass.states.get(combined.entity_id).attributes["friendly_name"] == (
        "Afvalwijzer 1234AB 1 Calendar"
    )
    assert hass.states.get(per_type.entity_id).attributes["friendly_name"] == (
        "Afvalwijzer 1234AB 1 GFT Calendar"
    )


def test_initial_color_for_waste_type_known_and_unknown():
    """The color helper returns a hex string for known types, None otherwise."""
    assert initial_color_for_waste_type("gft") == "#4CAF50"
    assert initial_color_for_waste_type("pmd") == "#800000"
    assert initial_color_for_waste_type("plastic") == "#FF9800"
    assert initial_color_for_waste_type("maas") is None
    assert initial_color_for_waste_type("not_a_real_type") is None


def test_type_calendar_entity_id_uses_raw_waste_type_not_translated_name():
    """entity_id is built from the raw waste_type key, matching sensor.py's pattern.

    Without an explicit entity_id, HA falls back to slugifying the full
    translated friendly name (e.g. "Organic waste (GFT)"), producing
    needlessly long/localized entity_ids like
    calendar.afvalwijzer_1234ab_1_organic_waste_gft.
    """
    coordinator = _mock_coordinator(
        config={
            "include_today": True,
            "provider": "afvalthuis",
            "postal_code": "1234AB",
            "house_number": "1",
        }
    )

    calendar = AfvalwijzerTypeCalendar(coordinator, "test_entry_id", "restafval")
    assert calendar.entity_id == "calendar.afvalwijzer_1234ab_1_restafval"


def test_combined_calendar_entity_id_uses_address_only():
    """The combined calendar's entity_id has no waste_type suffix."""
    coordinator = _mock_coordinator(
        config={
            "include_today": True,
            "provider": "afvalthuis",
            "postal_code": "1234AB",
            "house_number": "1",
        }
    )

    calendar = AfvalwijzerCalendar(coordinator, "test_entry_id")
    assert calendar.entity_id == "calendar.afvalwijzer_1234ab_1"


@pytest.mark.asyncio
async def test_type_calendar_filters_events_to_its_own_type():
    """A per-type calendar only reports events for its own waste type."""
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2026-07-09"},
            {"type": "restafval", "date": "2026-07-10"},
        ]
    )

    calendar = AfvalwijzerTypeCalendar(mock_data, "test_entry_id", "gft")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 1
    assert events[0].start == date(2026, 7, 9)
    assert events[0].summary == "Afvalthuis: GFT"


def test_type_calendar_next_event_only_considers_its_own_type():
    """The next-event state for a per-type calendar ignores other types."""
    today = date.today().isoformat()
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2099-01-01"},
            {"type": "restafval", "date": today},
        ]
    )

    calendar = AfvalwijzerTypeCalendar(mock_data, "test_entry_id", "gft")
    event = calendar.event

    assert event is not None
    assert event.start == date(2099, 1, 1)
    assert event.summary == "Afvalthuis: GFT"


_NO_STALE_REMOVAL = patch.multiple(
    "custom_components.afvalwijzer.calendar",
    _async_remove_stale_calendars=DEFAULT,
    _async_remove_legacy_calendar=DEFAULT,
    _async_remove_all_calendars=DEFAULT,
    _async_type_calendar_names=AsyncMock(return_value={}),
)


async def test_setup_entry_creates_single_combined_calendar_by_default():
    """Without separate_calendars, setup creates one combined calendar entity."""
    hass = _make_hass()
    coordinator = _FakeCoordinator(with_today={"gft": date(2026, 7, 9)})
    entry = _make_entry(coordinator, hass)

    added = []
    with _NO_STALE_REMOVAL:
        await async_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    assert isinstance(added[0], AfvalwijzerCalendar)


async def test_setup_entry_creates_no_calendar_when_disabled():
    """With enable_calendar off, setup adds nothing and cleans up any existing entities."""
    hass = _make_hass()
    coordinator = _FakeCoordinator(
        config={
            "include_today": True,
            "provider": "afvalthuis",
            CONF_ENABLE_CALENDAR: False,
        },
        with_today={"gft": date(2026, 7, 9)},
    )
    entry = _make_entry(coordinator, hass)

    added = []
    with _NO_STALE_REMOVAL as mocks:
        await async_setup_entry(hass, entry, added.extend)

    assert not added
    mocks["_async_remove_all_calendars"].assert_called_once_with(hass, entry.entry_id)
    mocks["_async_remove_stale_calendars"].assert_not_called()


async def test_setup_entry_creates_one_calendar_per_type_when_enabled():
    """With separate_calendars enabled, setup creates one calendar per waste type."""
    hass = _make_hass()
    coordinator = _FakeCoordinator(
        config={
            "include_today": True,
            "provider": "afvalthuis",
            CONF_SEPARATE_CALENDARS: True,
        },
        with_today={"gft": date(2026, 7, 9), "restafval": date(2026, 7, 10)},
    )
    entry = _make_entry(coordinator, hass)

    added = []
    with _NO_STALE_REMOVAL:
        await async_setup_entry(hass, entry, added.extend)

    assert len(added) == 2
    assert all(isinstance(e, AfvalwijzerTypeCalendar) for e in added)
    assert {e._waste_type for e in added} == {"gft", "restafval"}


async def test_setup_entry_adds_new_type_calendars_on_refresh():
    """A seasonal waste type appearing later gets its own calendar without a reload."""
    hass = _make_hass()
    coordinator = _FakeCoordinator(
        config={
            "include_today": True,
            "provider": "afvalthuis",
            CONF_SEPARATE_CALENDARS: True,
        },
        with_today={"gft": date(2026, 7, 9)},
    )
    entry = _make_entry(coordinator, hass)

    added = []
    with _NO_STALE_REMOVAL:
        await async_setup_entry(hass, entry, added.extend)
    assert len(added) == 1
    assert len(coordinator.listeners) == 1

    coordinator.waste_data_with_today["kerstbomen"] = date(2026, 12, 1)
    coordinator.listeners[0]()

    assert len(added) == 2
    assert added[1]._waste_type == "kerstbomen"

    # Unchanged data does not create duplicates
    coordinator.listeners[0]()
    assert len(added) == 2


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_setup_entry_per_type_calendar_name_matches_sensor_translation(hass):
    """The per-type calendar's translated name matches its sibling sensor's.

    Runs the real async_setup_entry (not the hand-rolled fakes elsewhere in
    this file) so the actual HA translation lookup executes, confirming the
    type_calendar placeholder isn't just a raw-key capitalization.
    """

    class _FakeCoordinatorWithListener:
        def __init__(self, config, with_today):
            self.config = config
            self.waste_data_raw = []
            self.waste_data_with_today = with_today

        def async_add_listener(self, cb, context=None):
            return lambda: None

    cfg = {
        CONF_SEPARATE_CALENDARS: True,
        "postal_code": "1234AB",
        "house_number": "1",
    }
    coordinator = _FakeCoordinatorWithListener(cfg, {"gft": "2026-08-20"})
    entry = MockConfigEntry(domain=DOMAIN, data=cfg)
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    added = []
    await async_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    assert added[0]._attr_translation_placeholders == {"type": "Organic waste (GFT)"}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_setup_entry_per_type_calendar_name_matches_hyphenated_type(hass):
    """A hyphenated raw waste type (e.g. "best-tas") still finds its sensor's translation.

    strings.json keys translations as "best_tas" (underscored), matching
    the normalization sensor_provider.py applies to its own translation_key
    - the calendar side must apply the same normalization or it silently
    falls back to a raw capitalization instead of the sensor's real name.
    """

    class _FakeCoordinatorWithListener:
        def __init__(self, config, with_today):
            self.config = config
            self.waste_data_raw = []
            self.waste_data_with_today = with_today

        def async_add_listener(self, cb, context=None):
            return lambda: None

    cfg = {
        CONF_SEPARATE_CALENDARS: True,
        "postal_code": "1234AB",
        "house_number": "1",
    }
    coordinator = _FakeCoordinatorWithListener(cfg, {"best-tas": "2026-08-20"})
    entry = MockConfigEntry(domain=DOMAIN, data=cfg)
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    added = []
    await async_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    assert added[0]._attr_translation_placeholders == {"type": "BEST-bag"}


def _registry_entry(entity_id, unique_id, domain="calendar"):
    return SimpleNamespace(entity_id=entity_id, unique_id=unique_id, domain=domain)


def test_remove_stale_calendars_removes_combined_when_switching_to_separate():
    """Switching to separate_calendars removes the old combined entity's registry record."""
    combined = _registry_entry(
        "calendar.afvalwijzer_1234ab_1", "afvalwijzer_calendar_test_entry"
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[combined],
        ),
    ):
        _async_remove_stale_calendars(_make_hass(), "test_entry", True)

    registry.async_remove.assert_called_once_with("calendar.afvalwijzer_1234ab_1")


def test_remove_stale_calendars_removes_per_type_when_switching_to_combined():
    """Switching back to the combined calendar removes any per-type entities."""
    per_type = _registry_entry(
        "calendar.afvalwijzer_1234ab_1_gft", "afvalwijzer_calendar_test_entry_gft"
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[per_type],
        ),
    ):
        _async_remove_stale_calendars(_make_hass(), "test_entry", False)

    registry.async_remove.assert_called_once_with("calendar.afvalwijzer_1234ab_1_gft")


def test_remove_stale_calendars_leaves_matching_entities_alone():
    """Entities that already belong in the current mode are left untouched."""
    combined = _registry_entry(
        "calendar.afvalwijzer_1234ab_1", "afvalwijzer_calendar_test_entry"
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[combined],
        ),
    ):
        _async_remove_stale_calendars(_make_hass(), "test_entry", False)

    registry.async_remove.assert_not_called()


def test_remove_stale_calendars_ignores_other_domains():
    """Non-calendar entities for the same config entry (e.g. sensors) are never touched."""
    sensor_entry = _registry_entry(
        "sensor.afvalwijzer_1234ab_1_restafval",
        "some_sensor_unique_id",
        domain="sensor",
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[sensor_entry],
        ),
    ):
        _async_remove_stale_calendars(_make_hass(), "test_entry", True)

    registry.async_remove.assert_not_called()


def test_remove_all_calendars_removes_every_calendar_entity():
    """Disabling the calendar entirely removes both combined and per-type entities."""
    combined = _registry_entry(
        "calendar.afvalwijzer_1234ab_1", "afvalwijzer_calendar_test_entry"
    )
    per_type = _registry_entry(
        "calendar.afvalwijzer_1234ab_1_gft", "afvalwijzer_calendar_test_entry_gft"
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[combined, per_type],
        ),
    ):
        _async_remove_all_calendars(_make_hass(), "test_entry")

    assert registry.async_remove.call_count == 2
    removed = {c.args[0] for c in registry.async_remove.call_args_list}
    assert removed == {
        "calendar.afvalwijzer_1234ab_1",
        "calendar.afvalwijzer_1234ab_1_gft",
    }


def test_remove_all_calendars_ignores_other_domains():
    """Non-calendar entities for the same config entry (e.g. sensors) are never touched."""
    sensor_entry = _registry_entry(
        "sensor.afvalwijzer_1234ab_1_restafval",
        "some_sensor_unique_id",
        domain="sensor",
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[sensor_entry],
        ),
    ):
        _async_remove_all_calendars(_make_hass(), "test_entry")

    registry.async_remove.assert_not_called()
