"""Classes related to a DeviceChannel."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

from thermoworks_cloud.utils import parse_datetime, map_firestore_fields, parse_nested_object


@dataclass
class Reading:
    """A reading from a device channel (temperature or humidity)."""

    value: Optional[float] = field(default=None, metadata={
                                   "firestore_type": "doubleValue"})
    """"The units as a string like "F", "C", or "H" (for humidity)"""
    units: Optional[str] = field(default=None, metadata={
                                 "firestore_type": "stringValue"})


@dataclass
class Alarm:
    """An alarm on a device channel."""

    enabled: Optional[bool] = field(
        default=None, metadata={"firestore_type": "booleanValue"})
    alarming: Optional[bool] = field(
        default=None, metadata={"firestore_type": "booleanValue"})
    value: Optional[int] = field(default=None, metadata={
                                 "firestore_type": "integerValue", "converter": int})
    """"The units as a string like "F", "C", or "H" (for humidity)"""
    units: Optional[str] = field(default=None, metadata={
                                 "firestore_type": "stringValue"})
    muted: Optional[bool] = field(
        default=None, metadata={"firestore_type": "booleanValue"})
    last_notified: Optional[datetime] = field(
        default=None,
        metadata={"api_name": "lastNotified", "firestore_type": "timestampValue", "converter": parse_datetime})


@dataclass
class RecentReading:
    """A recent reading on a device channel."""

    ts: Optional[str] = field(default=None, metadata={"firestore_type": "stringValue"})
    v: Optional[str] = field(default=None, metadata={"firestore_type": "stringValue"})
    u: Optional[str] = field(default=None, metadata={"firestore_type": "stringValue"})


@dataclass
class Trim:
    """Trim/calibration information for a device channel."""

    value: Optional[float] = field(default=None, metadata={"firestore_type": "doubleValue"})
    unit: Optional[str] = field(default=None, metadata={"firestore_type": "stringValue"})


@dataclass
class MinMaxReading:
    """A minimum or maximum reading on a device channel."""

    reading: Optional[Reading] = None
    date_reading: Optional[datetime] = field(
        default=None,
        metadata={
            "firestore_type": "timestampValue",
            "converter": parse_datetime
        }
    )


@dataclass
class DeviceChannel:  # pylint: disable=too-many-instance-attributes
    """A device channel on a device.

    All fields are optional as different device types may have different properties.
    """

    last_telemetry_saved: Optional[datetime] = field(
        default=None,
        metadata={
            "firestore_type": "timestampValue",
            "converter": parse_datetime
        }
    )
    """"The last time a telemetry packet was received from the device channel."""
    value: Optional[float] = field(default=None, metadata={
                                   "firestore_type": ["doubleValue","integerValue"]})
    """"The units as a string like "F", "C", or "H" (for humidity)"""
    units: Optional[str] = field(default=None, metadata={
                                 "firestore_type": "stringValue"})
    """"The only observed value for this field is "NORMAL"."""
    status: Optional[str] = field(default=None, metadata={
                                  "firestore_type": "stringValue"})
    type: Optional[str] = field(default=None, metadata={
                                "firestore_type": "stringValue"})
    """Customer provided 'name' for this device channel."""
    label: Optional[str] = field(default=None, metadata={
                                 "firestore_type": "stringValue"})
    last_seen: Optional[datetime] = field(
        default=None,
        metadata={
            "firestore_type": "timestampValue",
            "converter": parse_datetime
        }
    )
    alarm_high: Optional[Alarm] = field(
        default=None, metadata={"api_name": "alarmHigh"})
    alarm_low: Optional[Alarm] = field(
        default=None, metadata={"api_name": "alarmLow"})
    """The device channel number"""
    number: Optional[str] = field(default=None, metadata={
                                  "firestore_type": "stringValue"})
    minimum: Optional[MinMaxReading] = None
    maximum: Optional[MinMaxReading] = None
    show_avg_temp: Optional[bool] = field(
        default=None,
        metadata={
            "api_name": "showAvgTemp",
            "firestore_type": "booleanValue"
        }
    )
    color: Optional[str] = field(default=None, metadata={
                                 "firestore_type": "stringValue"})
    rate_of_change: Optional[float] = field(
        default=None, metadata={"api_name": "rateOfChange", "firestore_type": "doubleValue"})
    rate_of_change_unit: Optional[str] = field(
        default=None, metadata={"api_name": "rateOfChangeUnit", "firestore_type": "stringValue"})
    estimated_alarm_status: Optional[str] = field(
        default=None, metadata={"api_name": "estimatedAlarmStatus", "firestore_type": "stringValue"})
    enabled: Optional[bool] = field(
        default=None, metadata={"firestore_type": "booleanValue"})
    calibration: Optional[float] = field(
        default=None, metadata={"firestore_type": "doubleValue"})
    calibration_unit: Optional[str] = field(
        default=None, metadata={"api_name": "calibrationUnit", "firestore_type": "stringValue"})
    trim: Optional[Trim] = None
    recent_readings: Optional[list] = None

    # Dictionary to store any additional properties not explicitly defined
    additional_properties: Optional[Dict] = None


def _parse_min_max_reading(data: dict) -> Optional[MinMaxReading]:
    """Parse minimum or maximum reading data."""
    if not data or "fields" not in data:
        return None

    fields = data["fields"]
    result = MinMaxReading()

    # Parse date_reading
    if "dateReading" in fields and "timestampValue" in fields["dateReading"]:
        result.date_reading = parse_datetime(
            fields["dateReading"]["timestampValue"])

    # Parse reading
    if "reading" in fields and "mapValue" in fields["reading"]:
        result.reading = parse_nested_object(
            fields["reading"]["mapValue"], Reading)

    return result


def _document_to_device_channel(document: dict) -> DeviceChannel:
    """Convert a Firestore Document object into a Device object."""
    fields = document.get("fields", {})
    device_channel = map_firestore_fields(fields, DeviceChannel)

    try:
        # Handle complex objects
        if "alarmHigh" in fields and "mapValue" in fields["alarmHigh"]:
            device_channel.alarm_high = parse_nested_object(
                fields["alarmHigh"]["mapValue"], Alarm)

        if "alarmLow" in fields and "mapValue" in fields["alarmLow"]:
            device_channel.alarm_low = parse_nested_object(
                fields["alarmLow"]["mapValue"], Alarm)

        if "minimum" in fields and "mapValue" in fields["minimum"]:
            device_channel.minimum = _parse_min_max_reading(
                fields["minimum"]["mapValue"])

        if "maximum" in fields and "mapValue" in fields["maximum"]:
            device_channel.maximum = _parse_min_max_reading(
                fields["maximum"]["mapValue"])

        # Handle trim field (nested map)
        if "trim" in fields and "mapValue" in fields["trim"]:
            device_channel.trim = parse_nested_object(
                fields["trim"]["mapValue"], Trim)

        # Handle recent_readings field (array of maps)
        if "recentReadings" in fields and "arrayValue" in fields["recentReadings"]:
            readings = []
            for item in fields["recentReadings"]["arrayValue"].get("values", []):
                if "mapValue" in item:
                    r = RecentReading()
                    item_fields = item["mapValue"].get("fields", {})
                    if "ts" in item_fields:
                        r.ts = item_fields["ts"].get("stringValue")
                    if "v" in item_fields:
                        r.v = item_fields["v"].get("stringValue")
                    if "u" in item_fields:
                        r.u = item_fields["u"].get("stringValue")
                    readings.append(r)
            device_channel.recent_readings = readings

    except (KeyError, TypeError, ValueError) as _:
        # If there's an error parsing a specific field, continue with what we have
        pass

    return device_channel
