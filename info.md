
## Example configuration

###### SENSOR
```yaml
- platform: afvalwijzer # Required
  provider: mijnafvalwijzer # Optional - mijnafvalwijzer (default) or afvalstoffendienstkalender
  zipcode: postcode # Required
  housenumber: huisnummer # Required
  suffix: toevoeging # Optional
  default_label: label # Optional - Default is 'Geen'
```