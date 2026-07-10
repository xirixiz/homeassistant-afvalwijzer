"""Test basic integration setup."""

import json
import os


def get_keys(d, prefix=""):
    """Recursively get all keys from a dictionary."""
    keys = set()
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(get_keys(v, key))
        else:
            keys.add(key)
    return keys

def test_en_json_matches_strings_json():
    """Test that en.json is an exact copy of strings.json."""
    with open("custom_components/afvalwijzer/strings.json") as f:
        strings_data = json.load(f)

    with open("custom_components/afvalwijzer/translations/en.json") as f:
        en_data = json.load(f)

    assert strings_data == en_data, "en.json must be an exact copy of strings.json"

def test_translation_keys_match_strings_json():
    """Test that all translation files have the exact same keys as strings.json."""
    with open("custom_components/afvalwijzer/strings.json") as f:
        strings_data = json.load(f)

    strings_keys = get_keys(strings_data)

    translations_dir = "custom_components/afvalwijzer/translations"
    for filename in os.listdir(translations_dir):
        if not filename.endswith(".json") or filename == "en.json":
            continue

        filepath = os.path.join(translations_dir, filename)
        with open(filepath) as f:
            trans_data = json.load(f)

        trans_keys = get_keys(trans_data)

        missing_keys = strings_keys - trans_keys
        extra_keys = trans_keys - strings_keys

        assert not missing_keys, f"{filename} is missing keys: {missing_keys}"
        assert not extra_keys, f"{filename} has extra keys not in strings.json: {extra_keys}"
