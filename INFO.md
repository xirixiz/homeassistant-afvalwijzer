
## Example configuration

###### SENSOR - CONFIGURATION.YAML
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        # (required, default = mijnafvalwijzer) either choose mijnafvalwijzer, afvalstoffendienstkalender or rova
      postal_code: 1234AB              # (required, default = '')
      street_number:  5                # (required, default = '')
      suffix: ''                       # (optional, default = '')
      include_date_today: false        # (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              # (optional, default = Geen) label if no date found
      id: ''                           # (optional, default = '') use if you'd like to have multiple waste pickup locations in HASS
```
