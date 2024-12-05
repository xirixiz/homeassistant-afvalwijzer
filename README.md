# Afvalwijzer

[![custom_updater][customupdaterbadge]][customupdater]
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![Open Source Love png1](https://badges.frapsoft.com/os/v1/open-source.png?v=103)](https://github.com/ellerbrock/open-source-badges/)
[![Validation And Formatting](https://github.com/xirixiz/homeassistant-afvalwijzer/actions/workflows/combined_ci.yml/badge.svg)](https://github.com/xirixiz/homeassistant-afvalwijzer/actions/workflows/combined_ci.yml)
<br><br>
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xirixiz)

_Component to integrate with the following providers._

| Provider                         |
| -------------------------------- |
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
| nijkerk                          |
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

This custom component dynamically creates sensor.afvalwijzer\_\* items. For me personally the items created are gft, restafval, papier, pmd and kerstbomen. Look in the states overview in the developer tools in Home Assistant what the sensor names for your region are and modify where necessary.

**This component will set up the following platform(s).**

| Platform | Description                                                                               |
| -------- | ----------------------------------------------------------------------------------------- |
| `sensor` | Show waste pickup dates for mijnafvalwijzer.nl, afvalstoffendienstkalender.nl or rova.nl. |

![example][exampleimg1]

The second row sorts the waste items by date using the following lovelace code

```yaml
- type: custom:auto-entities
  card:
    type: glance
  filter:
    exclude:
      - entity_id: sensor.afvalwijzer_*next*
      - entity_id: sensor.afvalwijzer_day_after_tomorrow*
      - entity_id: sensor.afvalwijzer_today*
      - entity_id: sensor.afvalwijzer_tomorrow*
      - entity_id: sensor.afvalwijzer_kerstbomen*
      - entity_id: sensor.afvalwijzer_*orgen
      - entity_id: sensor.afvalwijzer_van*
    include:
      - entity_id: sensor.afvalwijzer_*
        options:
          format: date
  sort:
    method: state
- entities:
    - style:
        background: '#62717b'
        height: 1px
        margin-left: auto
        margin-right: auto
      type: divider
  type: entities
- type: markdown
  content: >-
    <center>De volgende leging is {{ states('sensor.afvalwijzer_next_type')
    }}. Dat is over {{ states('sensor.afvalwijzer_next_in_days') }} {% if
    is_state('sensor.afvalwijzer_next_in_days', '1') %}dag{% else %}dagen{%
    endif %}.</center>
```

More information on the reminders (ios in this case):

- https://github.com/xirixiz/my-hass-config/blob/master/packages/waste.yaml
- https://github.com/xirixiz/my-hass-config/blob/05d8755a737676b60faac98dc0cce91d06277939/configuration.yaml#L73

## Installation

### Manual Installation

1. Navigate to your Home Assistant configuration directory (where your `configuration.yaml` is located).
2. Create a folder named `custom_components` if it doesn't exist.
3. Inside the `custom_components` folder, create another folder named `afvalwijzer`.
4. Clone this repository or download the source code and copy all files from the `custom_components/afvalwijzer/` directory to the newly created `afvalwijzer` folder.
5. Restart Home Assistant to load the custom component.

After following these steps, your directory structure should look like this:

```markdown
custom_components/
afvalwijzer/
**init**.py
manifest.json
sensor.py
config_flow.py
...
```

### Installation via HACS

1. Ensure HACS is installed in your Home Assistant setup. If not, follow the [HACS installation guide](https://hacs.xyz/docs/setup/download).
2. Open the HACS panel in Home Assistant.
3. Click on the `Frontend` or `Integrations` tab.
4. Click the `+` button and search for `Afvalwijzer`.
5. Click `Install` to add the component to your Home Assistant setup.
6. Restart Home Assistant after the installation completes.

---

## Configuration

### Add Integration

1. Go to the **Settings** → **Devices & Services** page in Home Assistant.
2. Click **Add Integration** and search for `Afvalwijzer`.
3. Follow the on-screen instructions to complete the setup.
   - Provide your postal code, street number, and any other required details.

After completing the config flow, the integration will dynamically create sensors for waste collection dates based on your chosen provider.

---

##### CUSTOM COMPONENT USAGE

https://github.com/home-assistant/example-custom-config/tree/master/custom_components/example_sensor

##### LOGLEVEL

To enable debug logging for troubleshooting, add the following lines to your `configuration.yaml`:

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
    provider: mijnafvalwijzer # (required, default = mijnafvalwijzer) either choose mijnafvalwijzer, afvalstoffendienstkalender or rova
    postal_code: 1234AB # (required, default = '')
    street_number: 5 # (required, default = '')
    suffix: '' # (optional, default = '')
    exclude_pickup_today: true # (optional, default = true) to take or not to take Today into account in the next pickup.
    default_label: geen # (optional, default = geen) label if no date found
    id: '' # (optional, default = '') use if you'd like to have multiple waste pickup locations in HASS
    exclude_list: '' # (optional, default = '') comma separated list of waste types (case ignored). F.e. "papier, gft"
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
      hours: '/1'
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
          title: 'Afval'
          message: 'Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. Afvaltype(n): {{ states("sensor.afvalwijzer_tomorrow") }} wordt opgehaald op: {{ (now() + timedelta(days=1)).strftime("%d-%m-%Y") }}!'
          data:
            actions:
              - action: 'MARK_WASTE_MOVED' # The key you are sending for the event
                title: 'Afval buiten gezet' # The button title
```

---

[exampleimg1]: afvalwijzer-lovelace.png
[exampleimg2]: afvalwijzer_lovelace.png
[customupdater]: https://github.com/custom-components/custom_updater
[customupdaterbadge]: https://img.shields.io/badge/custom__updater-true-success.svg
