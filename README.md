# Afvalwijzer

[![custom_updater][customupdaterbadge]][customupdater]
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![Open Source Love png1](https://badges.frapsoft.com/os/v1/open-source.png?v=103)](https://github.com/ellerbrock/open-source-badges/)
[![Validation And Formatting](https://github.com/xirixiz/homeassistant-afvalwijzer/actions/workflows/combined_ci.yml/badge.svg)](https://github.com/xirixiz/homeassistant-afvalwijzer/actions/workflows/combined_ci.yml)
<br><br>
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/xirixiz)

_Component to integrate with the following providers/communities._

## Supported waste collectors

| Provider                       | Opmerking / bron                 |
| -------------------------------| -------------------------------- |
| ACV                            | ximmio                           |
| Afval3xBeter                   | opzet                            |
| AfvalAlert                     |                                  |
| Afvalstoffendienst             | opzet                            |
| Alkmaar                        |                                  |
| Almere                         | ximmio                           |
| Alphen aan den Rijn            | opzet                            |
| AreaReiniging                  | ximmio                           |
| Assen                          | burgerportaal                    |
| Avalex                         | ximmio                           |
| Avri                           | ximmio                           |
| BAR                            | burgerportaal                    |
| Blink                          | ximmio                           |
| Circulus                       |                                  |
| Cranendonck                    | opzet                            |
| Cure                           | mijnafvalwijzer                  |
| Cyclus NV                      | opzet                            |
| DAR                            | opzet                            |
| DeAfvalApp                     |                                  |
| De Fryske Marren               | opzet                            |
| DenHaag                        | opzet                            |
| Drimmelen                      |                                  |
| Eemsdelta                      | omrin                            |
| GAD                            | opzet                            |
| Geertruidenberg                | opzet                            |
| Groningen                      | burgerportaal                    |
| Harderwijk                     | omrin                            |
| Hellendoorn                    | ximmio                           |
| HVC                            | opzet                            |
| Irado                          |                                  |
| Land van Cuijk                 | deafvalapp                       |
| Lingewaard                     | opzet                            |
| Maassluis                      | klikogroep                       |
| Meerlanden                     | ximmio                           |
| Meppel                         |                                  |
| Middelburg-Vlissingen          | opzet                            |
| Mijn Afvalwijzer               |                                  |
| Mijnafvalzaken                 | opzet                            |
| Montferland                    |                                  |
| Montfoort                      | opzet                            |
| Nijkerk                        |                                  |
| Ôffalkalinder                  | opzet                            |
| Omrin                          |                                  |
| Oude IJsselstreek              | klikogroep                       |
| Peel en Maas                   | opzet                            |
| PreZero                        | opzet                            |
| Purmerend                      | opzet                            |
| RAD                            | ximmio                           |
| RD4                            |                                  |
| RecycleApp                     |                                  |
| Reinis                         | ximmio                           |
| RMN                            |                                  |
| ROVA                           |                                  |
| RWM                            | opzet                            |
| RWN                            | burgerportaal                    |
| Saver                          | opzet                            |
| Schouwen-Duiveland             | opzet                            |
| Sliedrecht                     | opzet                            |
| Spaarnelanden                  | opzet                            |
| Sudwest Fryslan                | opzet                            |
| SUEZ                           | opzet                            |
| Tilburg                        | burgerportaal                    |
| Twente Milieu                  | ximmio                           |
| Uithoorn                       | opzet                            |
| Venlo                          | ximmio                           |
| Venray                         |                                  |
| Voorschoten                    | opzet                            |
| Waalre                         |                                  |
| Waardlanden                    |                                  |
| Woerden                        | ximmio                           |
| ZRD                            | opzet                            |

This custom component dynamically creates sensor.afvalwijzer\_\* items. For me personally the items created are gft, restafval, papier, pmd and kerstbomen. Look in the states overview in the developer tools in Home Assistant what the sensor names for your region are and modify where necessary.

If you are searching for a component with the focus on container cleaning services, you can us the following component. [ha-afvalcontainer-cleaning by @PatrickSt1991](https://github.com/PatrickSt1991/ha-afvalcontainer-cleaning).

**This component will set up the following platform(s).**

| Platform | Description             |
|----------|-------------------------|
| `sensor` | Show waste pickup dates |

![example][exampleimg1]

The second row sorts the waste items by date using the following lovelace code

**The example yaml is to be used directly in the main ```cards: ``` node on the dashboard not inside a card yaml. <br/>
This yaml uses a custom card being [auto-entities](https://github.com/thomasloven/lovelace-auto-entities), make sure its installed***

Keep in mind your sensor might differ from the example due to different waste naming or different types of waste in your area.

**Example yaml (same look as shown in the screenshot). This yaml uses a custom card being [stack-in-card](https://github.com/custom-cards/stack-in-card), make sure its installed**

Keep in mind your sensor might differ from the example due to different waste naming or different types of waste in your area.

```yaml
type: custom:stack-in-card
cards:
  - type: horizontal-stack
    cards:
      - type: picture-entity
        entity: sensor.afvalwijzer_today_formatted
        show_name: false
        show_state: false
        state_image:
          GFT: /local/afvalwijzer/GFT.png
          Geen: /local/afvalwijzer/Geen.png
          PMD: /local/afvalwijzer/PMD.png
          Papier: /local/afvalwijzer/Papier.png
          Restafval: /local/afvalwijzer/Restafval.png
      - type: picture-entity
        entity: sensor.afvalwijzer_tomorrow_formatted
        show_name: false
        show_state: false
        state_image:
          GFT: /local/afvalwijzer/GFT.png
          Geen: /local/afvalwijzer/Geen.png
          PMD: /local/afvalwijzer/PMD.png
          Papier: /local/afvalwijzer/Papier.png
          Restafval: /local/afvalwijzer/Restafval.png
      - type: picture-entity
        entity: sensor.afvalwijzer_day_after_tomorrow_formatted
        show_name: false
        show_state: false
        state_image:
          GFT: /local/afvalwijzer/GFT.png
          Geen: /local/afvalwijzer/Geen.png
          PMD: /local/afvalwijzer/PMD.png
          Papier: /local/afvalwijzer/Papier.png
          Restafval: /local/afvalwijzer/Restafval.png

  - type: entities
    entities:
      - type: divider

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
        - entity_id: sensor.afvalwijzer_*_formatted
          options:
            format: date
    sort:
      method: state

  - type: entities
    entities:
      - type: divider

  - type: markdown
    content: >-
      <center>De volgende leging is {{ states('sensor.afvalwijzer_next_type')
      }}. Dat is over {{ states('sensor.afvalwijzer_next_in_days') }} {% if
      is_state('sensor.afvalwijzer_next_in_days', '1') %}dag{% else %}dagen{%
      endif %}.</center>

  - type: entities
    show_header_toggle: false
    state_color: false
    entities:
      - type: divider
      - entity: input_boolean.waste_moved
      - entity: input_boolean.waste_reminder
```

Example waste.yaml packages you could use for formatted template sensors.
Keep in mind your sensor might differ from the example due to different waste naming or different types of waste in your area.

```yaml
################################################
## Packages
################################################
homeassistant:
  customize:
    sensor.afvalwijzer_today:
      friendly_name: Vandaag
    sensor.afvalwijzer_tomorrow:
      friendly_name: Morgen
    sensor.afvalwijzer_day_after_tomorrow:
      friendly_name: Overmorgen

    sensor.afvalwijzer_next_item:
      friendly_name: Next pickup item
    sensor.afvalwijzer_next_in_days:
      friendly_name: Next pickup in days

    sensor.afvalwijzer_gft:
      friendly_name: GFT
      entity_picture: /local/afvalwijzer/GFT.png
    sensor.afvalwijzer_papier:
      friendly_name: Papier
      entity_picture: /local/afvalwijzer/Papier.png
    sensor.afvalwijzer_pmd:
      friendly_name: PMD
      entity_picture: /local/afvalwijzer/PMD.png
    sensor.afvalwijzer_restafval:
      friendly_name: Restafval
      entity_picture: /local/afvalwijzer/Restafval.png

    sensor.afvalwijzer_gft_formatted:
      friendly_name: GFT
      entity_picture: /local/afvalwijzer/GFT.png
    sensor.afvalwijzer_papier_formatted:
      friendly_name: Papier
      entity_picture: /local/afvalwijzer/Papier.png
    sensor.afvalwijzer_pmd_formatted:
      friendly_name: PMD
      entity_picture: /local/afvalwijzer/PMD.png
    sensor.afvalwijzer_restafval_formatted:
      friendly_name: Restafval
      entity_picture: /local/afvalwijzer/Restafval.png

################################################
## Template sensors
################################################
template:
  - sensor:
      - name: Afvalwijzer GFT formatted
        unique_id: afvalwijzer_gft_formatted
        state: >-
          {% set ts = states('sensor.afvalwijzer_gft') | as_timestamp(default=none) %}
          {{ ts | timestamp_custom('%d-%m-%Y') if ts is not none else 'Geen' }}

      - name: Afvalwijzer Papier formatted
        unique_id: afvalwijzer_papier_formatted
        state: >-
          {% set ts = states('sensor.afvalwijzer_papier') | as_timestamp(default=none) %}
          {{ ts | timestamp_custom('%d-%m-%Y') if ts is not none else 'Geen' }}

      - name: Afvalwijzer PMD formatted
        unique_id: afvalwijzer_pmd_formatted
        state: >-
          {% set ts = states('sensor.afvalwijzer_pmd') | as_timestamp(default=none) %}
          {{ ts | timestamp_custom('%d-%m-%Y') if ts is not none else 'Geen' }}

      - name: Afvalwijzer Restafval formatted
        unique_id: afvalwijzer_restafval_formatted
        state: >-
          {% set ts = states('sensor.afvalwijzer_restafval') | as_timestamp(default=none) %}
          {{ ts | timestamp_custom('%d-%m-%Y') if ts is not none else 'Geen' }}

      - name: Afvalwijzer next item formatted
        unique_id: afvalwijzer_next_item_formatted
        state: >-
          {{ {
            'gft': 'GFT',
            'papier': 'Papier',
            'pmd': 'PMD',
            'restafval': 'Restafval'
          }.get(states('sensor.afvalwijzer_next_item'), 'Geen') }}

      - name: Afvalwijzer today formatted
        unique_id: afvalwijzer_today_formatted
        state: >-
          {{ {
            'gft': 'GFT',
            'papier': 'Papier',
            'pmd': 'PMD',
            'restafval': 'Restafval'
          }.get(states('sensor.afvalwijzer_today'), 'Geen') }}

      - name: Afvalwijzer tomorrow formatted
        unique_id: afvalwijzer_tomorrow_formatted
        state: >-
          {{ {
            'gft': 'GFT',
            'papier': 'Papier',
            'pmd': 'PMD',
            'restafval': 'Restafval'
          }.get(states('sensor.afvalwijzer_tomorrow'), 'Geen') }}

      - name: Afvalwijzer day after tomorrow formatted
        unique_id: afvalwijzer_day_after_tomorrow_formatted
        state: >-
          {{ {
            'gft': 'GFT',
            'papier': 'Papier',
            'pmd': 'PMD',
            'restafval': 'Restafval'
          }.get(states('sensor.afvalwijzer_day_after_tomorrow'), 'Geen') }}
```

## Installation

### Manual Installation

1. Navigate to your Home Assistant configuration directory (where your `configuration.yaml` is located).
2. Create a folder named `custom_components` if it doesn't exist.
3. Inside the `custom_components` folder, create another folder named `afvalwijzer`.
4. Clone this repository or download the source code and copy all files from the `custom_components/afvalwijzer/`
   directory to the newly created `afvalwijzer` folder.
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

1. Ensure HACS is installed in your Home Assistant setup. If not, follow
   the [HACS installation guide](https://hacs.xyz/docs/setup/download).
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

After completing the config flow, the integration will dynamically create sensors for waste collection dates based on
your chosen provider.

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

###### SENSOR - CONFIGURATION.YAML

```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        # (required, default = mijnafvalwijzer) choose the provider for your community.
      postal_code: 1234AB              # (required, default = '')
      street_number: 5                 # (required, default = '')
      suffix: ''                       # (optional, default = '')
      exclude_pickup_today: true       # (optional, default = true) to take or not to take Today into account in the next pickup.
      date_isoformat: false            # (optional, default = false) show the date in full isoformat if desired. Example: "2024-01-14T08:40:33.993521"
      default_label: geen              # (optional, default = geen) label if no date found
      id: ''                           # (optional, default = '') use if you'd like to have multiple waste pickup locations in HASS
      exclude_list: ''                 # (optional, default = '') comma separated list of wast types (case ignored). F.e. "papier, gft, restafval, pmd, etc"
```

---

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
      event_type: mobile_app_notification_action
      event_data:
        action: "MARK_WASTE_MOVED"
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

###### WASTE COLLECTOR MESSAGES - MARKDOWN CARD

```yaml
type: markdown
content: >
  {% for notif in state_attr('sensor.afvalwijzer_notifications', 'notifications') | sort(attribute='id', reverse=true) %}

  ### {{ notif.title }}

  {{ notif.content }}

  {% endfor %}
visibility:
  - condition: numeric_state
    entity: sensor.afvalwijzer_notifications
    above: 0
```

<details>
<summary> Image preview</summary>

![example][exampleimg2]

</details>

###### WASTE COLLECTOR MESSAGES - AUTOMATION

```yaml
alias: Notify waste collection messages
description: "Notify the latest waste collector message to mobile app"
triggers:
  - trigger: state
    entity_id: sensor.afvalwijzer_notifications
    from: null
    to: null
conditions:
  - condition: template
    value_template: "{{ states('sensor.afvalwijzer_notifications') | int > 0 }}"
actions:
  - action: notify.mobile_app
    data:
      title: Afvalwijzer notification
      message: >-
        {% set notifs = state_attr('sensor.afvalwijzer_notifications',
        'notifications') %} {{ notifs[-1].content }}
```

---

[exampleimg1]: images/afvalwijzer-lovelace_1.png

[exampleimg2]: images/afvalwijzer-lovelace_2.png

[customupdater]: https://github.com/custom-components/custom_updater

[customupdaterbadge]: https://img.shields.io/badge/custom__updater-true-success.svg
