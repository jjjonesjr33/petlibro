from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

DOMAIN = "petlibro"

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_API_TOKEN = "api_token"
CONF_REGION = "region"

# Supported platforms
PLATFORMS = ["sensor", "switch", "button", "binary_sensor", "number", "select"]  # Add any other platforms as needed

# Update interval for device data in seconds
UPDATE_INTERVAL_SECONDS = 60  # You can adjust this value based on your needs