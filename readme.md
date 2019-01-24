Readme.md to use with the Home Assistant custom component (custom_components).

The custom components dynamically creates sensor.trash_* items. For me the items are gft, restafval, papier, pmd and kerstbomen.
Look in the states overview in the developer tools in Home Assistant what the sensor names for your region are and modify where necessary.

###### TRACK UPDATES
This custom component can be tracked with the help of [custom-lovelace](https://github.com/ciotlosm/custom-lovelace).

In your configuration.yaml

 ```
custom_updater:
 component_urls:
   - https://raw.githubusercontent.com/xirixiz/home-assistant-config/master/custom_updater.json
```

###### NOTIFY TRASH - SENSOR
```yaml
- platform: mijnafvalwijzer
  postcode: '1111AA'
  huisnummer: '1'
  toevoeging: 'A'
  label_geen: 'Geen'
```
  
###### NOTIFY TRASH - INPUT BOOLEAN
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

###### NOTIFY TRASH - AUTOMATION
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
      platform: time
      minutes: '/30'
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

