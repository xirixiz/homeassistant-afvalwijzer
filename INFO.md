
## Example configuration

###### SENSOR - CONFIGURATION.YAML - SCRAPER (DEFAULT)
```yaml
  sensor:
    - platform: afvalwijzer
      provider: mijnafvalwijzer        (required, default = mijnafvalwijzer) either choose mijnafvalwijzer or afvalstoffendienstkalender
      zipcode: 1111AA                  (required, default = 1111AA)
      housenumber:  11                 (required, default = 11)
      count_today: false               (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              (optional, default = Geen) label if no date found
```


###### SENSOR - CONFIGURATION.YAML - API (KEY REQUIRED BUT CANNOT BE OBTAINED!!!)
```yaml
  sensor:
    - platform: afvalwijzer
      data_collector: api              (optional, default = scraper) use the api to collect the data (KEY REQUIRED BUT CANNOT BE OBTAINED!!!)
      provider: mijnafvalwijzer        (required, default = mijnafvalwijzer) either choose mijnafvalwijzer or afvalstoffendienstkalender
      api_token: None                  (required, default = None) KEY REQUIRED BUT CANNOT BE OBTAINED!!!
      zipcode: 1111AA                  (required, default = 1111AA)
      housenumber:  11                 (required, default = 11)
      suffix: A                        (optional, default = A)
      count_today: false               (optional, default = false) to take or not to take Today into account in the next pickup.
      default_label: Geen              (optional, default = Geen) label if no date found
```
