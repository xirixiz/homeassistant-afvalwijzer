# Afvalwijzer

[![BuyMeCoffee][buymecoffeebedge]][buymecoffee]
[![custom_updater][customupdaterbadge]][customupdater]
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![Open Source Love png1](https://badges.frapsoft.com/os/v1/open-source.png?v=103)](https://github.com/ellerbrock/open-source-badges/)

_Component to integrate with [afvalwijzer][afvalwijzer] and [afvalstoffendienstkalender][afvalstoffendienstkalender]._

This custom component dynamically creates sensor.trash_* items. For me personally the items created are gft, restafval, papier, pmd and kerstbomen. Look in the states overview in the developer tools in Home Assistant what the sensor names for your region are and modify where necessary.

Special thanks go out to https://github.com/heyajohnny/afvalinfo for allowing me to use the scraper code he created once the api solutions was disabled by the provider(s)!

**This component will set up the following platforms.**

Platform | Description
-- | --
`sensor` | Show trash pickup dates for mijnafvalwijzer.nl or afvalstoffendienstkalender.nl.

![example][exampleimg1]

The second row sorts the trash items by date using the following lovelace code
```yaml
  - type: 'custom:auto-entities'
    card:
      type: glance
    filter:
      include:
        - entity_id: sensor.trash_gft
        - entity_id: sensor.trash_papier
        - entity_id: sensor.trash_pmd
        - entity_id: sensor.trash_restafval
    sort:
      attribute: next_pickup_in_days
      method: attribute
      numeric: true
```

More information on the reminders (ios in this case):
https://github.com/xirixiz/my-hass-config/blob/master/packages/trash.yaml
https://github.com/xirixiz/my-hass-config/blob/05d8755a737676b60faac98dc0cce91d06277939/configuration.yaml#L73

## Installation

1. Using you tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `afvalwijzer`.
4. Download _all_ the files from the `custom_components/afvalwijzer/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Look at the `Example Configuration` section for further configuration.

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/afvalwijzer/__init__.py
custom_components/afvalwijzer/manifest.json
custom_components/afvalwijzer/sensor.py
```

##### CUSTOM COMPONENT USAGE
https://github.com/home-assistant/example-custom-config/tree/master/custom_components/example_sensor

##### TRACK UPDATES
This custom component can be tracked with the help of [custom-lovelace](https://github.com/ciotlosm/custom-lovelace).

In your configuration.yaml

```yaml
custom_updater:
 component_urls:
   - https://raw.githubusercontent.com/xirixiz/homeassistant-afvalwijzer/master/custom_updater.json
```

In order to extend the log level, modify the following (configuration.yaml probably)

```yaml
logger:
  default: info
  logs:
    custom_components.afvalwijzer: debug
```

## Example configuration

Here's an example of my own Home Asisstant config: https://github.com/xirixiz/home-assistant

###### SENSOR - CONFIGURATION.YAML - SCRAPER (DEFAULT)
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        (required, default = mijnafvalwijzer) either choose mijnafvalwijzer or afvalstoffendienstkalender
      zipcode: 1111AA                  (required, default = 1111AA)
      housenumber:  11                 (required, default = 11)
      count_today: false               (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              (optional, default = Geen) label if no date found
```


###### SENSOR - CONFIGURATION.YAML - API (KEY REQUIRED BUT CANNOT BE OBTAINED!!!)
```yaml
  sensor:
    - platform: afvalwijzer
      data_collector: api              (optional, default = scraper) use the api to collect the data (KEY REQUIRED BUT CANNOT BE OBTAINED!!!)
      provider: mijnafvalwijzer        (required, default = mijnafvalwijzer) either choose mijnafvalwijzer or afvalstoffendienstkalender
      api_token: None                  (required, default = None) KEY REQUIRED BUT CANNOT BE OBTAINED!!!
      zipcode: 1111AA                  (required, default = 1111AA)
      housenumber:  11                 (required, default = 11)
      suffix: A                        (optional, default = A)
      count_today: false               (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              (optional, default = Geen) label if no date found
```

###### INPUT BOOLEAN (FOR AUTOMATION)
```yaml
input_boolean:
  trash_moved:
    name: Trash has been moved
    initial: 'off'
    icon: mdi:delete-empty
  trash_reminder:
    name: Trash reminder enabled
    initial: 'on'
```

###### AUTOMATION
```yaml
automation:
  - alias: Reset trash notification
    trigger:
      platform: state
      entity_id: input_boolean.trash_moved
      to: 'on'
      for:
        hours: 12
    action:
      - service: input_boolean.turn_off
        entity_id: input_boolean.trash_moved
      - service: input_boolean.turn_on
        entity_id: input_boolean.trash_reminder

  - alias: Mark trash as moved from notification
    trigger:
      platform: event
      event_type: ios.notification_action_fired
      event_data:
        actionName: MARK_TRASH_MOVED
    action:
      - service: input_boolean.turn_on
        entity_id: input_boolean.trash_moved

  - alias: Trash has not been moved
    trigger:
      platform: time_pattern
      minutes: '/60'
      seconds: 00
    condition:
      condition: and
      conditions:
        - condition: state
          entity_id: input_boolean.trash_moved
          state: 'off'
        - condition: state
          entity_id: input_boolean.trash_reminder
          state: 'on'
        - condition: time
          after: '18:00:00'
          before: '23:00:00'
        - condition: template
          value_template: "{{ states('sensor.trash_tomorrow') != 'Geen' }}"
    action:
      - service: notify.family
        data:
          title: "Afval"
          message: 'Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. Afvaltype(n): {{ states.sensor.trash_tomorrow.state }} wordt opgehaald op: {{ (as_timestamp(now()) + (24*3600)) | timestamp_custom("%d-%m-%Y", True) }}!'
          data:
            push:
              badge: 0
              category: 'afval'
```

***

[exampleimg1]: afvalwijzer-lovelace.png
[exampleimg2]: afvalwijzer_lovelace.png
[buymecoffee]: https://www.buymeacoffee.com/xirixiz
[buymecoffeebedge]: https://camo.githubusercontent.com/cd005dca0ef55d7725912ec03a936d3a7c8de5b5/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f6275792532306d6525323061253230636f666665652d646f6e6174652d79656c6c6f772e737667
[afvalwijzer]: https://mijnafvalwijzer.nl
[afvalstoffendienstkalender]: http://afvalstoffendienstkalender.nl
[customupdater]: https://github.com/custom-components/custom_updater
[customupdaterbadge]: https://img.shields.io/badge/custom__updater-true-success.svg
