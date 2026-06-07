"""Constants for the Thermoworks Cloud integration."""

DOMAIN = "thermoworks_cloud"
# Setting to 3 minutes as default
DEFAULT_SCAN_INTERVAL_SECONDS = 180
# Minimum scan interval
MIN_SCAN_INTERVAL_SECONDS = 60  # 1 minute
# Active cook detection polling interval
ACTIVE_COOK_SCAN_INTERVAL_SECONDS = 60  # 1 minute when cook is active

CONF_CLOUD_PROVIDER = "cloud_provider"

PROVIDER_THERMOWORKS = "thermoworks"
PROVIDER_ETI = "eti"

CLOUD_PROVIDERS = {
    PROVIDER_THERMOWORKS: {
        "name": "ThermoWorks Cloud",
        "api_key": None,  # Use library defaults
        "app_id": None,
        "referer": None,
    },
    PROVIDER_ETI: {
        "name": "ETI Cloud",
        "api_key": "AIzaSyBD4snlT2LllO4k0NywX5qYjJ7M7WfU4_I",
        "app_id": "1:701566661301:web:7a9bc711c05985ead144fc",
        "referer": "https://cloud.etiltd.com/",
    },
}
