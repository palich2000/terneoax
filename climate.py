"""Support for TerneoAX WiFi Thermostats. http://www.terneo.ua """
import logging
from typing import Optional
from .terneo_api import TerneoAX
import voluptuous as vol
from homeassistant.helpers.typing import HomeAssistantType

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    PRESET_AWAY,
    PRESET_HOME,
)
from homeassistant.const import (
    CONF_NAME,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_TIMEOUT,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_HVAC_STATE = "hvac_mode"

VALID_THERMOSTAT_MODES = [HVAC_MODE_HEAT, HVAC_MODE_OFF]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_TIMEOUT, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the TerneoAX thermostat."""

    host = config.get(CONF_HOST)
    timeout = config.get(CONF_TIMEOUT)
    name = config.get(CONF_NAME)
    client = TerneoAX(
        addr=host, timeout=timeout, name=name
    )

    add_entities([TerneoAXThermostat(client, hass)], True)


class TerneoAXThermostat(ClimateDevice):
    """Representation of a TerneoAX thermostat."""

    def __init__(self, client: TerneoAX, hass: HomeAssistantType):
        """Initialize the thermostat."""
        self._client = client
        self._notification_send = False
        self._hass = hass

    def update(self):
        """Update the data from the thermostat."""
        _LOGGER.info("Update: {}".format(self._client.addr))
        if not self._client.update_params():
            _LOGGER.error("Failed to update params")
        if not self._client.update_telemetry():
            _LOGGER.error("Failed to update telemetry")
        else:
            if not self._notification_send and not self._client.is_local_lan_remote_control_enabled():
                self._hass.components.persistent_notification.create(
                    "Please enable remote control on {} [{}] serial number: {} ".format(self._client.addr,
                                                                                        self._client.name,
                                                                                        self._client._sn),
                    "TerneoAX",
                    self._client._sn
                )
                self._notification_send = True
        _LOGGER.info("Update: {} done".format(self._client.addr))

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

        return features

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._client.name

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def target_temperature_step(self) -> Optional[float]:
        """Return the supported step of target temperature."""
        return 1

    @property
    def temperature_unit(self):
        """Return the unit of measurement, as defined by the API."""
        return TEMP_CELSIUS

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return VALID_THERMOSTAT_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.get_current_temp()

    @property
    def hvac_mode(self):
        """Return current operation mode ie. heat, cool, auto."""
        if self._client.mode == self._client.MODE_HEAT:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def hvac_action(self):
        """Return current operation mode ie. heat, cool, auto."""
        if self._client.state == self._client.STATE_IDLE:
            return CURRENT_HVAC_IDLE
        if self._client.state == self._client.STATE_HEATING:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_OFF

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        return {
            ATTR_HVAC_STATE: self._client.state,
        }

    @property
    def target_temperature(self):
        """Return the target temperature we try to reach."""
        if self._client.mode == self._client.MODE_HEAT:
            return self._client.heattemp
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._client.get_lower_temp_limit()

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._client.get_upper_temp_limit()

    @property
    def preset_mode(self):
        """Return current preset."""
        if self._client.away:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def preset_modes(self):
        """Return valid preset modes."""
        return [PRESET_HOME, PRESET_AWAY]

    def _set_operation_mode(self, operation_mode):
        """Change the operation mode (internal)."""
        if operation_mode == HVAC_MODE_HEAT:
            success = self._client.set_mode(self._client.MODE_HEAT)
        else:
            success = self._client.set_mode(self._client.MODE_OFF)

        if not success:
            _LOGGER.error("Failed to change the operation mode {mode}".format(mode=operation_mode))
        return success

    def set_temperature(self, **kwargs) -> None:
        """Set a new target temperature."""
        set_temp = True
        operation_mode = kwargs.get(ATTR_HVAC_MODE, self._client.mode)
        temperature = kwargs.get(ATTR_TEMPERATURE)

        _LOGGER.info(
            "Set temperature mode:{mode} t:{temp} ".format(mode=operation_mode, temp=temperature))

        if operation_mode != self._client.mode:
            set_temp = self._set_operation_mode(operation_mode)

        if set_temp:
            if operation_mode == self._client.MODE_HEAT:
                success = self._client.set_temp_setting(int(temperature))
            else:
                success = False
                _LOGGER.error(
                    "The thermostat is currently not in a mode "
                    "that supports target temperature: %s",
                    operation_mode,
                )

            if not success:
                _LOGGER.error("Failed to change the temperature")

    def set_hvac_mode(self, hvac_mode) -> None:
        """Set new target operation mode."""
        _LOGGER.info("Set mode: {}".format(hvac_mode))
        self._set_operation_mode(hvac_mode)

    def set_preset_mode(self, preset_mode) -> None:
        """Set the hold mode."""
        _LOGGER.info("Set home/away: {}".format(preset_mode))
        if preset_mode == PRESET_AWAY:
            success = self._client.set_away(3600 * 24)  # set away mode time from now (seconds)
        elif preset_mode == PRESET_HOME:
            success = self._client.set_home()  # set home mode
        else:
            _LOGGER.error("Unknown hold mode: %s", preset_mode)
            success = False

        if not success:
            _LOGGER.error("Failed to change the home/away state {}".format(preset_mode))
