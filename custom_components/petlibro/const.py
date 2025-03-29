from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

DOMAIN = "petlibro"

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_API_TOKEN = "api_token"
CONF_REGION = "region"
CONF_MIN_UPDATE_INTERVAL = "min_update_interval"
CONF_MAX_UPDATE_INTERVAL = "max_update_interval"
CONF_ADAPTIVE_POLLING = "adaptive_polling"

# Supported platforms
PLATFORMS = ["sensor", "switch", "button", "binary_sensor", "number", "select", "text"]  # Add any other platforms as needed

# Update interval for device data in seconds
UPDATE_INTERVAL_SECONDS = 60  # You can adjust this value based on your needs

# Entity keys for diagnostic sensors
API_CONNECTION_SENSOR_KEY = "api_connection_status"
COMMAND_QUEUE_SENSOR_KEY = "command_queue_status"

# Data freshness thresholds in seconds
FRESHNESS_THRESHOLD_CRITICAL = 3600  # 1 hour - data considered stale
FRESHNESS_THRESHOLD_WARNING = 1800   # 30 minutes - data freshness warning

# API and command queue retry settings
DEFAULT_MAX_BACKOFF_TIME = 120  # 2 minutes maximum backoff time

# Command queue status
COMMAND_QUEUE_IDLE = "idle"
COMMAND_QUEUE_BUSY = "busy"

# Notification Configuration
CONF_NOTIFY_CONNECTION_OFFLINE = "notify_connection_offline"
CONF_NOTIFY_CONNECTION_RESTORED = "notify_connection_restored"
CONF_NOTIFY_COMMANDS_QUEUED = "notify_commands_queued"
CONF_NOTIFY_COMMANDS_EXECUTED = "notify_commands_executed"
CONF_NOTIFY_COMMANDS_FAILED = "notify_commands_failed"
CONF_NOTIFY_CRITICAL_BATTERY = "notify_critical_battery"
CONF_NOTIFY_CRITICAL_WATER_LEVEL = "notify_critical_water_level"
CONF_NOTIFY_CRITICAL_FOOD_LEVEL = "notify_critical_food_level"
CONF_USE_MOBILE_NOTIFICATIONS = "use_mobile_notifications"
CONF_NOTIFICATION_SERVICE = "notification_service"
CONF_NOTIFICATION_COOLDOWN = "notification_cooldown"

DEFAULT_NOTIFICATION_CONFIG = {
    CONF_NOTIFY_CONNECTION_OFFLINE: True,
    CONF_NOTIFY_CONNECTION_RESTORED: True,
    CONF_NOTIFY_COMMANDS_QUEUED: True,
    CONF_NOTIFY_COMMANDS_EXECUTED: True,
    CONF_NOTIFY_COMMANDS_FAILED: True,
    CONF_NOTIFY_CRITICAL_BATTERY: True,
    CONF_NOTIFY_CRITICAL_WATER_LEVEL: True,
    CONF_NOTIFY_CRITICAL_FOOD_LEVEL: True,
    CONF_USE_MOBILE_NOTIFICATIONS: False,
    CONF_NOTIFICATION_SERVICE: "notify.mobile_app",
    CONF_NOTIFICATION_COOLDOWN: 300,
}