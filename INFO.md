
## Example configuration

###### SENSOR - CONFIGURATION.YAML - SCRAPER (DEFAULT)
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        # (required, default = mijnafvalwijzer) either choose mijnafvalwijzer, rova or afvalstoffendienstkalender
      postal_code: 1111AA              # (required, default = '')
      street_number:  11               # (required, default = '')
      suffix: A                        # (optional, default = '')
      include_date_today: false        # (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              # (optional, default = Geen) label if no date found
```


###### SENSOR - CONFIGURATION.YAML - API (KEY REQUIRED BUT CANNOT BE OBTAINED!!!)
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        # (required, default = mijnafvalwijzer) either choose mijnafvalwijzer, rova or afvalstoffendienstkalender
      api_token: None                  # (required, default = '') KEY REQUIRED BUT CANNOT BE OBTAINED!!!
      postal_code: 1111AA              # (required, default = '')
      street_number:  11               # (required, default = '')
      suffix: A                        # (optional, default = '')
      include_date_today: false        # (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              # (optional, default = Geen) label if no date found
```