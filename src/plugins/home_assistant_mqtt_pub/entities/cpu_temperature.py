import logging

from .base import SampleResult


class CpuTemperatureEntity:
    key = "cpu_temperature"
    display_name = "CPU temperature"
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            import wmi
            zones = wmi.WMI(namespace=r"root\wmi").MSAcpi_ThermalZoneTemperature()
        except Exception as exc:
            logging.debug("cpu_temperature WMI failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if not zones:
            return SampleResult.unavailable(reason="no thermal zones reported")
        kelvin_tenths = zones[0].CurrentTemperature
        celsius = (kelvin_tenths / 10.0) - 273.15
        return SampleResult.available(value=round(celsius, 1), unit="°C")
