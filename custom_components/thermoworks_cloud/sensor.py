"""Sensors representing a Thermoworks thermometer."""
from collections.abc import Mapping
import logging

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers.device_registry import format_mac, DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import DOMAIN

from .models import (
    DeviceWithBattery,
    DeviceWithLastSeen,
    DeviceWithTransmitInterval,
    DeviceWithWifi,
    DeviceWithFan,
    ThermoworksChannel,
    get_missing_attributes,
)

from .coordinator import ThermoworksCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)

# Channel type constants
CHANNEL_TYPE_COMPUTED = "computed"
CHANNEL_TYPE_RFX_MEAT = "rfx meat sensor"
CHANNEL_TYPE_PRO_SERIES = "Pro-Series"

# Channel types that support alarm high/low sensors
CHANNEL_TYPES_WITH_ALARMS = {CHANNEL_TYPE_COMPUTED, CHANNEL_TYPE_PRO_SERIES}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""

    coordinator: ThermoworksCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    new_entities = []
    for device in coordinator.data.devices:

        # Only create battery sensor if the device has battery capability
        if DeviceWithBattery.is_protocol_compliant(device):
            new_entities.append(
                BatterySensor(
                    entity_id=async_generate_entity_id(
                        ENTITY_ID_FORMAT,
                        f"{device.get_identifier()}_battery",
                        hass=hass,
                    ),
                    coordinator=coordinator,
                    device=device,
                )
            )
        else:
            _LOGGER.debug(
                "Not creating battery sensor for device %s, "
                "missing required attributes: %s", device.display_name(
                ), get_missing_attributes(device, DeviceWithBattery)
            )

        # Only create signal sensor if the device has WiFi capability
        if DeviceWithWifi.is_protocol_compliant(device):
            new_entities.append(
                SignalSensor(
                    entity_id=async_generate_entity_id(
                        ENTITY_ID_FORMAT,
                        f"{device.get_identifier()}_signal",
                        hass=hass,
                    ),
                    coordinator=coordinator,
                    device=device,
                )
            )
        else:
            _LOGGER.debug(
                "Not creating wifi sensor for device %s, "
                "missing required attributes: %s", device.display_name(
                ), get_missing_attributes(device, DeviceWithWifi)
            )

        if DeviceWithLastSeen.is_protocol_compliant(device):
            new_entities.append(
                LastSeenSensor(
                    entity_id=async_generate_entity_id(
                        ENTITY_ID_FORMAT,
                        f"{device.get_identifier()}_last_seen",
                        hass=hass,
                    ),
                    coordinator=coordinator,
                    device=device,
                )
            )
        else:
            _LOGGER.debug(
                "Not creating last_seen sensor for device %s, "
                "missing required attributes: %s", device.display_name(),
                get_missing_attributes(device, DeviceWithLastSeen)
            )

        if DeviceWithTransmitInterval.is_protocol_compliant(device):
            new_entities.append(
                TransmitIntervalSensor(
                    entity_id=async_generate_entity_id(
                        ENTITY_ID_FORMAT,
                        f"{device.get_identifier()}_transmit_interval",
                        hass=hass,
                    ),
                    coordinator=coordinator,
                    device=device,
                )
            )
        else:
            _LOGGER.debug(
                "Not creating transmit_interval sensor for device %s, "
                "missing required attributes: %s", device.display_name(),
                get_missing_attributes(device, DeviceWithTransmitInterval)
            )

        # Fan sensors — only if fan data is present
        if device.fan is not None:
            new_entities.append(FanSetTempSensor(
                entity_id=async_generate_entity_id(ENTITY_ID_FORMAT, f"{device.get_identifier()}_fan_set_temp", hass=hass),
                coordinator=coordinator, device=device))
            new_entities.append(FanStateSensor(
                entity_id=async_generate_entity_id(ENTITY_ID_FORMAT, f"{device.get_identifier()}_fan_state", hass=hass),
                coordinator=coordinator, device=device))
            new_entities.append(FanConnectedSensor(
                entity_id=async_generate_entity_id(ENTITY_ID_FORMAT, f"{device.get_identifier()}_fan_connected", hass=hass),
                coordinator=coordinator, device=device))

        # Session start
        if device.session_start is not None:
            new_entities.append(SessionStartSensor(
                entity_id=async_generate_entity_id(ENTITY_ID_FORMAT, f"{device.get_identifier()}_session_start", hass=hass),
                coordinator=coordinator, device=device))

        for device_channel in coordinator.data.device_channels.get(device.get_identifier(), []):

            # Humidity sensor
            if device_channel.units == "H":
                new_entities.append(
                    HumiditySensor(
                        entity_id=async_generate_entity_id(
                            ENTITY_ID_FORMAT,
                            f"{device.get_identifier()}_ch_{device_channel.number}_humidity",
                            hass=hass,
                        ),
                        coordinator=coordinator,
                        device_serial=device.get_identifier(),
                        device_channel=device_channel,
                    )
                )

            # Temperature sensor — all channels with F or C units
            elif device_channel.units in ("F", "C"):
                new_entities.append(
                    TemperatureSensor(
                        entity_id=async_generate_entity_id(
                            ENTITY_ID_FORMAT,
                            f"{device.get_identifier()}_ch_{device_channel.number}_temperature",
                            hass=hass,
                        ),
                        coordinator=coordinator,
                        device_serial=device.get_identifier(),
                        device_channel=device_channel,
                    )
                )
            else:
                _LOGGER.warning(
                    "Unsupported sensor unit '%s' for device %s channel %s - skipping",
                    device_channel.units,
                    device.display_name(),
                    device_channel.display_name()
                )

            # Alarm high (target temp) — only for computed channels
            if (
                device_channel.channel_type in CHANNEL_TYPES_WITH_ALARMS
                and device_channel.alarm_high is not None
            ):
                new_entities.append(AlarmHighSensor(
                    entity_id=async_generate_entity_id(
                        ENTITY_ID_FORMAT,
                        f"{device.get_identifier()}_ch_{device_channel.number}_high_temperature",
                        hass=hass,
                    ),
                    coordinator=coordinator,
                    device_serial=device.get_identifier(),
                    device_channel=device_channel,
                ))

            # Alarm low — only for computed channels
            if (
                device_channel.channel_type in CHANNEL_TYPES_WITH_ALARMS
                and device_channel.alarm_low is not None
            ):
                new_entities.append(AlarmLowSensor(
                    entity_id=async_generate_entity_id(
                        ENTITY_ID_FORMAT,
                        f"{device.get_identifier()}_ch_{device_channel.number}_low_temperature",
                        hass=hass,
                    ),
                    coordinator=coordinator,
                    device_serial=device.get_identifier(),
                    device_channel=device_channel,
                ))



    if len(new_entities) > 0:
        _LOGGER.debug("New entities to create: %d", len(new_entities))
        async_add_entities(new_entities)
    else:
        _LOGGER.debug("No new entities created")


class BatterySensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Implementation of a sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "battery"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        entity_id: str,
        coordinator: ThermoworksCoordinator,
        device: DeviceWithBattery,
    ) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(
                f"Cannot update sensor {self.name}: device {self._device.display_name()} is not found")
        if not DeviceWithBattery.is_protocol_compliant(device):
            raise UpdateFailed(
                f"Cannot update sensor {self.name}: device {self._device.display_name()} is missing required "
                f"attribute(s): {get_missing_attributes(device, DeviceWithBattery)}")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")},
            name=self._device.label,
            sw_version=self._device.firmware,
            manufacturer="ThermoWorks",
            model=self._device.device_name,
            serial_number=self._device.serial,
        )

    @property
    def icon(self) -> str | None:
        if self._device.battery_state is not None and self._device.battery_state == "charging":
            return "mdi:battery-charging-100"
        return None

    @property
    def native_value(self) -> int | float:
        return float(self._device.battery)

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}"


class LastSeenSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Implementation of a last seen timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_translation_key = "last_seen"

    def __init__(self, entity_id, coordinator, device) -> None:
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(f"Cannot update sensor {self.name}: device {self._device.display_name()} is not found")
        if not DeviceWithLastSeen.is_protocol_compliant(device):
            raise UpdateFailed(
                f"Cannot update sensor {self.name}: device {self._device.display_name()} is missing required "
                f"attribute(s): {get_missing_attributes(device, DeviceWithLastSeen)}")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")})

    @property
    def native_value(self) -> str | None:
        if self._device.last_seen is None:
            return None
        if hasattr(self._device.last_seen, "isoformat"):
            return dt_util.as_utc(self._device.last_seen)
        last_seen = dt_util.parse_datetime(str(self._device.last_seen))
        return dt_util.as_utc(last_seen) if last_seen else None

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}-last-seen"


class TransmitIntervalSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Implementation of a transmit interval sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_has_entity_name = True
    _attr_translation_key = "transmit_interval"

    def __init__(self, entity_id, coordinator, device) -> None:
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(f"Cannot update sensor {self.name}: device {self._device.display_name()} is not found")
        if not DeviceWithTransmitInterval.is_protocol_compliant(device):
            raise UpdateFailed(
                f"Cannot update sensor {self.name}: device {self._device.display_name()} is missing required "
                f"attribute(s): {get_missing_attributes(device, DeviceWithTransmitInterval)}")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")})

    @property
    def native_value(self) -> int | None:
        return self._device.transmit_interval_in_seconds

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}-transmit-interval"


class ChannelSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Base class for thermoworks channel sensors."""

    _device_channel: ThermoworksChannel
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        entity_id: str,
        coordinator: ThermoworksCoordinator,
        device_serial: str,
        device_channel: ThermoworksChannel,
    ) -> None:
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device_channel = device_channel
        self._device_serial = device_serial

    @callback
    def _handle_coordinator_update(self) -> None:
        device_channel = self.coordinator.get_device_channel_by_id(
            device_id=self._device_serial, channel_id=self._device_channel.number
        )
        if not device_channel:
            raise UpdateFailed(
                f"Cannot update sensor {self.name}: device channel {self._device_channel.display_name()} is not found")
        self._device_channel = device_channel
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device_serial)}")})

    @property
    def name(self) -> str:
        return self._device_channel.display_name().capitalize()

    @property
    def translation_placeholders(self) -> Mapping[str, str]:
        return {"channel_name": self._device_channel.display_name()}

    @property
    def native_value(self) -> int | float:
        return float(self._device_channel.value)

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device_serial)}-{self._device_channel.number}"


class TemperatureSensor(ChannelSensor):
    """Implementation of a thermoworks temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_translation_key = "temperature"

    @property
    def native_unit_of_measurement(self) -> str:
        if self._device_channel.units == "F":
            return UnitOfTemperature.FAHRENHEIT
        if self._device_channel.units == "C":
            return UnitOfTemperature.CELSIUS
        raise ValueError(
            f"Unable to determine unit of measurement from unit string '{self._device_channel.units}'"
        )


class HumiditySensor(ChannelSensor):
    """Implementation of a thermoworks humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_translation_key = "humidity"
    _attr_native_unit_of_measurement = PERCENTAGE


class AlarmHighSensor(ChannelSensor):
    """Target (high alarm) temperature for a computed channel."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_translation_key = "temperature"
    _attr_suggested_display_precision = 0

    @property
    def name(self) -> str:
        return f"{self._device_channel.display_name().capitalize()} high temperature"

    @property
    def native_value(self) -> int | float | None:
        if self._device_channel.alarm_high is None:
            return None
        return float(self._device_channel.alarm_high)

    @property
    def native_unit_of_measurement(self) -> str:
        if self._device_channel.alarm_high_units == "F":
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device_serial)}-{self._device_channel.number}-alarm-high"


class AlarmLowSensor(ChannelSensor):
    """Low alarm temperature for a computed channel."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_translation_key = "temperature"
    _attr_suggested_display_precision = 0

    @property
    def name(self) -> str:
        return f"{self._device_channel.display_name().capitalize()} low temperature"

    @property
    def native_value(self) -> int | float | None:
        if self._device_channel.alarm_low is None:
            return None
        return float(self._device_channel.alarm_low)

    @property
    def native_unit_of_measurement(self) -> str:
        if self._device_channel.alarm_low_units == "F":
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device_serial)}-{self._device_channel.number}-alarm-low"


class FanSetTempSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Fan target temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "fan_set_temp"
    _attr_suggested_display_precision = 0

    def __init__(self, entity_id, coordinator, device):
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(f"Device {self._device.display_name()} not found")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")})

    @property
    def native_unit_of_measurement(self) -> str:
        units = getattr(self._device, 'device_display_units', 'F') or 'F'
        return UnitOfTemperature.FAHRENHEIT if units == 'F' else UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        if self._device.fan is None:
            return None
        return self._device.fan.set_temp

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}-fan-set-temp"


class FanStateSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Fan running state sensor (0=off, 1=on)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "fan_state"

    def __init__(self, entity_id, coordinator, device):
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(f"Device {self._device.display_name()} not found")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")})

    @property
    def native_value(self):
        if self._device.fan is None:
            return None
        return self._device.fan.state

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}-fan-state"


class FanConnectedSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Fan physically connected sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "fan_connected"

    def __init__(self, entity_id, coordinator, device):
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(f"Device {self._device.display_name()} not found")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")})

    @property
    def native_value(self):
        if self._device.fan is None:
            return None
        return self._device.fan.connected

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}-fan-connected"


class SessionStartSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Cook session start timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_translation_key = "session_start"

    def __init__(self, entity_id, coordinator, device):
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(f"Device {self._device.display_name()} not found")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")})

    @property
    def native_value(self):
        if self._device.session_start is None:
            return None
        if hasattr(self._device.session_start, 'isoformat'):
            return dt_util.as_utc(self._device.session_start)
        parsed = dt_util.parse_datetime(str(self._device.session_start))
        return dt_util.as_utc(parsed) if parsed else None

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}-session-start"


class SignalSensor(CoordinatorEntity[ThermoworksCoordinator], SensorEntity):
    """Implementation of a signal strength sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "signal"
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
    _attr_suggested_display_precision = 0

    def __init__(self, entity_id, coordinator, device) -> None:
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._device = device

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device_by_id(self._device.get_identifier())
        if not device:
            raise UpdateFailed(f"Cannot update sensor {self.name}: device {self._device.display_name()} is not found")
        if not DeviceWithWifi.is_protocol_compliant(device):
            raise UpdateFailed(
                f"Cannot update sensor {self.name}: device {self._device.display_name()} is missing required "
                f"attribute(s): {get_missing_attributes(device, DeviceWithWifi)}")
        self._device = device
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"{format_mac(self._device.get_identifier())}")})

    @property
    def native_value(self) -> int | float:
        return float(self._device.wifi_strength)

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}-{format_mac(self._device.get_identifier())}-signal"
