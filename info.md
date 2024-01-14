
## Example configuration

###### SENSOR - CONFIGURATION.YAML
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        # (required, default = mijnafvalwijzer) either choose mijnafvalwijzer, afvalstoffendienstkalender or rova
      postal_code: 1234AB              # (required, default = '')
      street_number:  5                # (required, default = '')
      suffix: ''                       # (optional, default = '')
      exclude_pickup_today: true       # (optional, default = true) to take or not to take Today into account in the next pickup.
      date_isoformat: false            # (optional, default = false) show the date in full isoformat if desired. Example: "2024-01-14T08:40:33.993521"
      default_label: geen              # (optional, default = geen) label if no date found
      id: ''                           # (optional, default = '') use if you'd like to have multiple waste pickup locations in HASS
      exclude_list: ''                 # (optional, default = '') comma separated list of wast types (case ignored). F.e. "papier, gft, restafval, pmd, etc"
```
