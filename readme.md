Readme.md to use with the Home Assistant custom component (custom_components).

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
        value_template: '{{- (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_gft.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_restafval.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_pmd.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_papier.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") -}}'
      - condition: template
        value_template: '{{- (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_kerstbomen.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") -}}'
  action:
  - service: notify.family
    data_template:
      message: >-
        {% if (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_gft.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") %}
           Het is vandaag - {{ now().strftime("%Y-%m-%d") }}. De groene bak wordt geleegd op: {{ states.sensor.trash_gft.state }}!
        {% endif %}
        {% if (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_restafval.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") %}
           Het is vandaag - {{ now().strftime("%Y-%m-%d") }}. De grijze bak wordt geleegd op: {{ states.sensor.restafval.state }}!
        {% endif %}
        {% if (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_pmd.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") %}
           Het is vandaag - {{ now().strftime("%Y-%m-%d") }}. Plastic wordt opgehaald op: {{ states.sensor.trash_pmd.state }}!
        {% endif %}
        {% if (now().strftime("%Y-%m-%d")) == (as_timestamp(strptime(states.sensor.trash_papier.state, "%Y-%m-%d")) - (1 * 86400 )) | timestamp_custom("%Y-%m-%d") %}
           Het is vandaag - {{ now().strftime("%Y-%m-%d") }}. Papier wordt opgehaald op: {{ states.sensor.trash_papier.state }}!
        {% endif %}
```
