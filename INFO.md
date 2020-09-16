
## Example configuration

###### SENSOR - CONFIGURATION.YAML
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        (required, default = mijnafvalwijzer) either choose mijnafvalwijzer or afvalstoffendienstkalender
      api_token: None                  (required, default = None) can only be requested/provided by the provider!
      zipcode: 1111AA                  (required, default = 1111AA)
      housenumber:  11                 (required, default = 11)
      suffix: A                        (optional, default = A)
      count_today: false               (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              (optional, default = Geen) label if no date found
```
