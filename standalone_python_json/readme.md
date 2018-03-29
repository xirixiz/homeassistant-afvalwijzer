Thanks to the input of https://github.com/RolfKoenders/smarthome

Can be used with - mijnafvalwijzer_standalone_json.py

###### NOTIFY TRASH - SENSOR
```yaml
- platform: rest
  resource: https://raw.githubusercontent.com/xxxx/xxxx/master/mijnafvalwijzer.json
  name: Trash_Today
  scan_interval: 3600
  value_template: >
    {% set now = as_timestamp(now()) %}
    {% set today = now | timestamp_custom("%d/%m/%Y") %}
    {% set containerType = value_json.days[ today ] %}
    {% if containerType | trim != "" %}
      {% set trash = value_json.legend[ containerType ] %}
      {{ trash }}
    {% else %}
      Geen
    {% endif %}

- platform: rest
  resource: https://raw.githubusercontent.com/xxxx/xxxx/master/mijnafvalwijzer.json
  name: Trash_Tomorrow
  scan_interval: 3600
  value_template: >
    {% set now = as_timestamp(now()) %}
    {% set oneDay = 86400 %}
    {% set nextDay = now + oneDay %}
    {% set tomorrow = nextDay | timestamp_custom("%d/%m/%Y") %}
    {% set containerType = value_json.days[ tomorrow ] %}
    {% if containerType | trim != "" %}
      {% set trash = value_json.legend[ containerType ] %}
      {{ trash }}
    {% else %}
      Geen
    {% endif %}
```

###### NOTIFY TRASH - AUTOMATION
```yaml
- alias: 'Notify of which container will be pickedup today'
  initial_state: true
  hide_entity: false
  trigger:
  - platform: time
    at: '07:00:00'
  condition:
  - condition: state
    entity_id: input_boolean.notify_trash
    state: 'on'
  - condition: template
    value_template: "{{ states('sensor.trash_today') != 'Geen' }}"
  - condition: template
    value_template: "{{ states.sensor.trash_today.state | trim != '' }}"
  action:
  - service: notify.family
    data_template:
      message: 'Vandaag kan de {{ states.sensor.trash_today.state }} container aan de straat.'

- alias: 'Notify of which container will be pickedup tomorrow'
  initial_state: true
  hide_entity: false
  trigger:
    platform: time
    at: '20:00:00'
  condition:
    - condition: state
      entity_id: input_boolean.notify_trash
      state: 'on'
    - condition: template
      value_template: "{{ states('sensor.trash_tomorrow') != 'Geen' }}"
    - condition: template
      value_template: "{{ states.sensor.trash_tomorrow.state | trim != '' }}"
  action:
    - service: telegram_bot.send_message
      data_template:
        title: 'Afvalinzameling'
        target: !secret telegram_rolf_id
        message: 'Morgen kan de {{ states.sensor.trash_tomorrow.state }} container aan de straat.'
        disable_notification: false
```          

###### NOTIFY TRASH - CUSTOMIZATION
```yaml
sensor.trash_today:
  friendly_name: 'Vandaag'
  icon: mdi:delete
sensor.trash_tomorrow:
  friendly_name: 'Morgen'
  icon: mdi:delete
```      

###### NOTIFY TRASH - INPUT BOOLEAN
```yaml
notify_trash:
  name: 'Notificaties'
  initial: 'on'
  icon: mdi:bell-ring
```  
