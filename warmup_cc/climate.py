"""Platform that offers a connection to a warmup device."""
from datetime import datetime, timedelta
import logging
from typing import Any, Dict

import voluptuous as vol
from .warmup4ie import Warmup4IE, Warmup4IEDevice

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    PRECISION_HALVES,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import InvalidStateError, PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.temperature import convert as convert_temperature

DOMAIN = "warmup_cc"
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

ATTR_UNTIL = "until"

CONF_LOCATION = "location"
CONF_TARGET_TEMP = "target_temp"

DEFAULT_NAME = "warmup4ie"
DEFAULT_TARGET_TEMP = 20

CONST_MODE_PROGRAM = "prog"  # Default room mode (treated as Home/Auto)
CONST_MODE_FIXED = "fixed"  # Fixed temperature mode (treated as Home/Heat)
CONST_MODE_AWAY = "away"  # WarmUp Geo Away or Holiday Mode (treated as Away/Auto)
CONST_MODE_FROST = "frost"  # Frost Mode (treated as Away/Heat)
CONST_MODE_OFF = "off"  # Switch off heating in a zone

HVAC_MAP_WARMUP_HEAT = {
    CONST_MODE_PROGRAM: HVAC_MODE_AUTO,
    CONST_MODE_FIXED: HVAC_MODE_HEAT,
    CONST_MODE_AWAY: HVAC_MODE_AUTO,
    CONST_MODE_FROST: HVAC_MODE_HEAT,
    CONST_MODE_OFF: HVAC_MODE_OFF,
}

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC_HEAT = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
SUPPORT_PRESET = [PRESET_AWAY, PRESET_HOME, PRESET_BOOST]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the climate devices."""
    hass.data.setdefault(DOMAIN, {})

    def service_set_override(call):
        """Handle the service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        temperature = call.data.get(ATTR_TEMPERATURE)
        until = call.data.get(
            ATTR_UNTIL, (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        )
        target_devices = [
            dev for dev in hass.data[DOMAIN]["entities"] if dev.entity_id in entity_id
        ]
        target_device: WarmupThermostat
        for target_device in target_devices:
            target_device.set_override(temperature, until)
            target_device.schedule_update_ha_state(True)

    _LOGGER.info("Setting up platform for Warmup component")
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    warmup = Warmup4IE(user, password)

    if warmup is None or not warmup.setup_finished:
        raise PlatformNotReady
    warmup_client = WarmupClient(warmup)
    to_add = []
    for device in warmup.get_all_devices().values():
        to_add.append(WarmupThermostat(hass, device, warmup_client))
    add_entities(to_add)
    hass.data[DOMAIN]["entities"] = to_add
    hass.services.register(DOMAIN, "set_override", service_set_override)
    return True


class WarmupClient:
    """Wrapper around the API client to throttle requests."""

    def __init__(self, warmup: Warmup4IE):
        """Initialise wrapper."""
        self._warmup = warmup

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Throttles calls to the warmup client update method."""
        _LOGGER.debug("Updating Warmup devices")
        self._warmup.update_all_devices()


class WarmupThermostat(ClimateDevice):
    """Representation of a Warmup device."""

    def __init__(self, hass, device: Warmup4IEDevice, client: WarmupClient):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup Thermostat %s", device.get_room_name())
        self._device = device
        self._client = client

        self.attributes = {}
        self._update_attributes_from_device()

        self._current_temperature = device.current_temperature
        self._target_temperature = device.target_temperature
        self._min_temp = device.min_temp
        self._max_temp = device.max_temp
        self._name = device.get_room_name()

        self._current_operation_mode = device.run_mode
        self._away = False
        self._on = True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return HVAC_MAP_WARMUP_HEAT.get(self._current_operation_mode, HVAC_MODE_AUTO)

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if not self._on:
            return CURRENT_HVAC_OFF
        if not self._away:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._away:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""

        if preset_mode == PRESET_HOME:
            """Turn away mode off."""
            self._away = False
            self._device.set_temperature_to_auto()

        elif preset_mode == PRESET_AWAY:
            """Turn away mode on."""
            self._away = True
            self._device.set_location_to_frost()

        else:
            raise InvalidStateError

        pass

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._current_operation_mode = CONST_MODE_FIXED
        self._device.set_new_temperature(temperature)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode.

        Switch device on if was previously off
        """

        if hvac_mode == HVAC_MODE_OFF:
            self._on = False
            self._device.set_location_to_off()
            self._current_operation_mode = CONST_MODE_OFF

        elif hvac_mode == HVAC_MODE_AUTO:
            self._on = True
            self._device.set_temperature_to_auto()
            self._current_operation_mode = CONST_MODE_PROGRAM

        elif hvac_mode == HVAC_MODE_HEAT:
            self._on = True
            self._device.set_temperature_to_manual()
            self._current_operation_mode = CONST_MODE_FIXED

        else:
            raise InvalidStateError

    def set_override(self, temperature, until):
        """Set a temperature override for this thermostat."""
        self._device.set_override(temperature, until)

    def update(self):
        """Fetch new state data for this device.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._client.update()

        self._current_operation_mode = self._device.get_run_mode()
        self._target_temperature = self._device.target_temperature
        self._current_temperature = self._device.current_temperature
        self._min_temp = self._device.min_temp
        self._max_temp = self._device.max_temp

        self._update_attributes_from_device()

        # set whether device is in away mode
        if (
            self._current_operation_mode == CONST_MODE_AWAY
            or self._current_operation_mode == CONST_MODE_FROST
        ):
            self._away = True
        else:
            self._away = False

        # set whether device is on/off
        if self._current_operation_mode == CONST_MODE_OFF:
            self._on = False
        else:
            self._on = True

    def _update_attributes_from_device(self):
        _attributes = {
            "floor_temperature": self._device.floor_temperature,
            "air_temperature": self._device.air_temperature,
            "away_temperature": self._device.away_temperature,
            "comfort_temperature": self._device.comfort_temperature,
            "cost": self._device.cost,
            "energy": self._device.energy,
            "fixed_temperature": self._device.fixed_temperature,
            "override_temperature": self._device.override_temperature,
            "override_duration_mins": self._device.override_duration_mins,
            "sleep_temperature": self._device.sleep_temperature,
            "run_mode": self._device.run_mode,
            "room_mode": self._device.room_mode,
            "heating_target": self._device.heating_target,
        }
        self.attributes = _attributes

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        return {**super(WarmupThermostat, self).state_attributes, **self.attributes}

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(
            self._device.min_temp, TEMP_CELSIUS, self.hass.config.units.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(
            self._device.max_temp, TEMP_CELSIUS, self.hass.config.units.temperature_unit
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_HALVES

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC_HEAT
