
## Example configuration

###### SENSOR
```yaml
- platform: afvalwijzer # Required
  provider: mijnafvalwijzer # Optional - mijnafvalwijzer (default) or afvalstoffendienstkalender
  zipcode: postcode # Required
  housenumber: huisnummer # Required
  suffix: toevoeging # Optional
  count_today: vandaag meetellen # Optional. true or false - Default = false
  default_label: label # Optional - Default is 'Geen'
```
