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
  postcode: !secret afvalwijzer_postcode
  huisnummer: !secret afvalwijzer_huisnummer
  toevoeging: !secret afvalwijzer_toevoeging
```
  
###### NOTIFY TRASH - GROUP
```yaml
default_view:
  icon: mdi:home
  view: yes
  entities:
    - group.trash_pickup

trash_pickup:
  name: "Trash Pickup"
  control: hidden
  entities:
    - sensor.trash_gft
    - sensor.trash_restafval
    - sensor.trash_papier
    - sensor.trash_pmd
    - sensor.trash_kerstbomen
```

###### NOTIFY TRASH - AUTOMATION
```yaml
- alias: 'Trash - One day before'
  trigger:
  - platform: time
    hours: 20
    minutes: 0
    seconds: 0
  condition:
    - condition: or
      conditions:
      - condition: template
        value_template: '{{- (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_gft.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_restafval.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_pmd.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_papier.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_kerstbomen.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") -}}'
  action:
  - service: notify.family
    data_template:
      message: >-
        {% if (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_gft.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") %}
           Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. De groene bak wordt geleegd op: {{ states.sensor.trash_gft.state }}!
        {% endif %}
        {% if (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_restafval.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") %}
           Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. De grijze bak wordt geleegd op: {{ states.sensor.restafval.state }}!
        {% endif %}
        {% if (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_pmd.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") %}
           Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. Plastic wordt opgehaald op: {{ states.sensor.trash_pmd.state }}!
        {% endif %}
        {% if (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_papier.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") %}
           Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. Papier wordt opgehaald op: {{ states.sensor.trash_papier.state }}!
        {% endif %}
        {% if (now().strftime("%d-%m-%Y")) == (as_timestamp(strptime(states.sensor.trash_kerstbomen.state, "%d-%m-%Y")) - (1 * 86400 )) | timestamp_custom("%d-%m-%Y") %}
           Het is vandaag - {{ now().strftime("%d-%m-%Y") }}. Kerstbomen worden opgehaald op: {{ states.sensor.trash_kerstbomen.state }}!
        {% endif %}
```
