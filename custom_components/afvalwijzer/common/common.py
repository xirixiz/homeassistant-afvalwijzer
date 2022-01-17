from afvalwijzer.const.const import _LOGGER


class Common(object):
    def _gen_waste_data_after_date_selected(self):
        try:
            waste_data_after_date_selected = list(
                filter(
                    lambda waste: waste["date"] >= self.date_selected,
                    self.waste_data_formatted,
                )
            )
        except Exception as err:
            _LOGGER.error(
                "Other error occurred _gen_waste_data_after_date_selected: %s", err
            )
        return waste_data_after_date_selected