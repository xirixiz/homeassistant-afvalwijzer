# Afvalwijzer
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]
[![custom_updater][customupdaterbadge]][customupdater]
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![Open Source Love png1](https://badges.frapsoft.com/os/v1/open-source.png?v=103)](https://github.com/ellerbrock/open-source-badges/)
[![Validation And Formatting](https://github.com/xirixiz/homeassistant-afvalwijzer/actions/workflows/combined_ci.yml/badge.svg)](https://github.com/xirixiz/homeassistant-afvalwijzer/actions/workflows/combined_ci.yml)

_Component to integrate with the following providers._

| Provider                         |
| ---------------------------------|
| acv                              |
| afvalstoffendienstkalender (all) |
| alkmaar                          |
| alphenaandenrijn                 |
| areareiniging                    |
| assen                            |
| avalex                           |
| avri                             |
| bar                              |
| berkelland                       |
| blink                            |
| circulus                         |
| cranendonck                      |
| cyclus                           |
| dar                              |
| deafvalapp                       |
| denhaag                          |
| eemsdelta (iCalendar)            |
| gad                              |
| hellendoorn                      |
| hvc                              |
| lingewaard                       |
| meppel                           |
| meerlanden                       |
| middelburg                       |
| mijnafvalwijzer                  |
| montfoort                        |
| peelenmaas                       |
| prezero                          |
| purmerend                        |
| rad                              |
| reinis                           |
| rd4                              |
| rova                             |
| rmn                              |
| schouwenand                      |
| spaarnelanden                    |
| sudwestfryslan                   |
| suez                             |
| twentemilieu                     |
| veldhoven                        |
| venray                           |
| voorschoten                      |
| waalre                           |
| waardlanden                      |
| westland                         |
| woerden                          |
| ximmio                           |
| zrd                              |

This custom component dynamically creates sensor.afvalwijzer_* items. For me personally the items created are gft, restafval, papier, pmd and kerstbomen. Look in the states overview in the developer tools in Home Assistant what the sensor names for your region are and modify where necessary.

**This component will set up the following platform(s).**

| Platform | Description                                                                               |
| -------- | ----------------------------------------------------------------------------------------- |
| `sensor` | Show waste pickup dates for mijnafvalwijzer.nl, afvalstoffendienstkalender.nl or rova.nl. |

![example][exampleimg1]

The second row sorts the waste items by date using the following lovelace code
```yaml
  - type: 'custom:auto-entities'
    card:
      type: glance
    filter:
      include:
        - entity_id: sensor.afvalwijzer_gft
        - entity_id: sensor.afvalwijzer_papier
        - entity_id: sensor.afvalwijzer_pmd
        - entity_id: sensor.afvalwijzer_restafval
    sort:
      attribute: days_until_collection_date
      method: attribute
      numeric: true
```

More information on the reminders (ios in this case):
- https://github.com/xirixiz/my-hass-config/blob/master/packages/waste.yaml
- https://github.com/xirixiz/my-hass-config/blob/05d8755a737676b60faac98dc0cce91d06277939/configuration.yaml#L73

## Installation

1. Using your tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `afvalwijzer`.
4. Download _all_ the files from the `custom_components/afvalwijzer/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant before further configuration.
7. Look at the `Example Configuration` section for further configuration.
8. Restart Home Assistant again when configuration is done to activate the configuration.

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/afvalwijzer/__init__.py
custom_components/afvalwijzer/manifest.json
custom_components/afvalwijzer/sensor.py
```

##### CUSTOM COMPONENT USAGE
https://github.com/home-assistant/example-custom-config/tree/master/custom_components/example_sensor

##### LOGLEVEL
In order to extend the log level, modify the following (configuration.yaml probably)

```yaml
logger:
  default: info
  logs:
    custom_components.afvalwijzer: debug
```

## EXAMPLE CONFIGURATION

Here's an example of my own Home Asisstant config: https://github.com/xirixiz/home-assistant


###### SENSOR - CONFIGURATION.YAML
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        # (required, default = mijnafvalwijzer) either choose mijnafvalwijzer, afvalstoffendienstkalender or rova
      postal_code: 1234AB              # (required, default = '')
      street_number:  5                # (required, default = '')
      suffix: ''                       # (optional, default = '')
      exclude_pickup_today: true       # (optional, default = true) to take or not to take Today into account in the next pickup.
      default_label: geen              # (optional, default = geen) label if no date found
      id: ''                           # (optional, default = '') use if you'd like to have multiple waste pickup locations in HASS
      exclude_list: ''                 # (optional, default = '') comma separated list of waste types (case ignored). F.e. "papier, gft"
```

###### INPUT BOOLEAN (FOR AUTOMATION)
```yaml
input_boolean:
  waste_moved:
    name: Waste has been moved
    initial: 'off'
    icon: mdi:delete-empty
  waste_reminder:
    name: Waste reminder enabled
    initial: 'on'
```

###### AUTOMATION
```yaml
automation:
  - alias: Reset waste notification
    trigger:
      platform: state
      entity_id: input_boolean.waste_moved
      to: 'on'
      for:
        hours: 12
    action:
      - service: input_boolean.turn_off
        entity_id: input_boolean.waste_moved
      - service: input_boolean.turn_on
        entity_id: input_boolean.waste_reminder

  - alias: Mark waste as moved from notification
    trigger:
      platform: event
      event_type: ios.notification_action_fired
      event_data:
        actionName: MARK_WASTE_MOVED
    action:
      - service: input_boolean.turn_on
        entity_id: input_boolean.waste_moved

  - alias: Waste has not been moved
    trigger:
      platform: time_pattern
      hours: "/1"
    condition:
      condition: and
      conditions:
        - condition: state
          entity_id: input_boolean.waste_moved
          state: 'off'
        - condition: state
          entity_id: input_boolean.waste_reminder
          state: 'on'
        - condition: time
          after: '18:00:00'
          before: '23:00:00'
        - condition: template
          value_template: "{{ states('sensor.afvalwijzer_tomorrow') != 'geen' }}"
    action:
      - service: notify.family
        data:
          title: "Afval"
          message: 'Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. Afvaltype(n): {{ states.sensor.afvalwijzer_tomorrow.state }} wordt opgehaald op: {{ (as_timestamp(now()) + (24*3600)) | timestamp_custom("%d-%m-%Y", True) }}!'
          data:
            actions:
              - action: "MARK_WASTE_MOVED" # The key you are sending for the event
                title: "Afval buiten gezet" # The button title
```

***

[exampleimg1]: afvalwijzer-lovelace.png
[exampleimg2]: afvalwijzer_lovelace.png
[buymecoffee]: [!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/gbraad)
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg
[customupdater]: https://github.com/custom-components/custom_updater
[customupdaterbadge]: https://img.shields.io/badge/custom__updater-true-success.svg
