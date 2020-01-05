Introduction
============

This is a library for communicating with a wifi-enabled home thermostat made by
`Warmup <https://www.warmup.co.uk/>`_. At the time of writing, this only 
includes the `warmup 4IE <https://www.warmup.co.uk/thermostats/smart/4ie-underfloor-heating>`_.

This code is inspired by a project for SmartThingsHub, see `here <https://github.com/alyc100/SmartThingsPublic/blob/master/devicetypes/alyc100/warmup-4ie.src/warmup-4ie.groovy>`_. Many Thanks to alyc100 for the great work!

Warmup Plc was not involved in the creation of this
software and has not sanctioned or endorsed it in any way.
4IE is a registered trademark of Warmup Plc.

License
=======

This software is available under Apache license. Please see LICENSE.txt.


Usage
=====
The library is primary intended to interface the 4IE with home assistant, but may also be used standalone.

Home Assistant
---------------

To setup this component, you need to register to warmup first.
see https://my.warmup.com/login

Then copy the contents of the warmup_cc subfolder into custom_components 
in your HA **config** folder, e.g.:

.. code-block:: sh

  cd path/to/your/config
  # remove any previous version
  rm -r ./custom_components/warmup_cc 2>/dev/null
  git clone https://github.com/ha-warmup/warmup.git /tmp/warmup
  mkdir -p ./custom_components/warmup_cc
  cp -r /tmp/warmup/warmup_cc/* ./custom_components/warmup_cc
  # clean up
  rm -rf /tmp/warmup/


Then add to your
configuration.yaml:

.. code-block:: yaml

  climate:
    - platform: warmup_cc
      username: YOUR_E_MAIL_ADDRESS
      password: YOUR_PASSWORD

* **username** (required): the username used to login to the warmup web site
* **password** (required): the password used to login to the warmup web site; may be moved to the secrets.yaml file. See `secrets <https://www.home-assistant.io/docs/configuration/secrets/>`_

After restarting home assistant, the component will be loaded automatically.

Standalone
----------
You may install the library via pip using

>>> pip install warmup4ie

After that, import the library, and away we go.

    >>> import warmup4ie
    >>> warmup = warmup4ie.Warmup4IE('<e-mail>', '<password>',
    >>> warmup.get_all_devices()
    >>> device = warmup.get_device_by_name("Underfloor")
    >>> device.get_current_temperature()

Device Versions
---------------

Supported models:

- 4IE

Since I only have access to the 4IE, that is the model that the development 
has occured with. 

Supported Features
------------------

At the moment the library supports reading current temperature, target temperature plus other values from the thermostat
and setting the target temperature, switching between manual, automatic and frost protection mode, switching the device off.
and setting a temporary override.

Release Notes
=============

0.1.0
-----

- inital release

0.1.1
-----

- bug fixes

0.1.2
-----

- bug fixes

0.1.3
-----

- changed http-request to use the new api.
- adapted file names to comply with the new naming structure of HA introduced with 0.92

0.1.4
-----

- added functionality to allow configuration of Warmup4IE thermostat via HA UI Config entry.

0.1.5
-----

- added getter methods for location, location id, room name, room id and serial number

0.1.6
-----

- Changed so that multiple devices are updated in a single HTTP request
- Added Set Override method
- Added access to the following information from the thermostat
    - target_temperature_low
    - target_temperature_high
    - floor_temperature
    - floor_temperature_2
    - air_temperature
    - away_temperature
    - comfort_temperature
    - cost
    - energy
    - fixed_temperature
    - override_temperature
    - override_duration
    - sleep_temperature
    - override_duration_mins

0.1.7
-----

- initialise using new **services** standards https://developers.home-assistant.io/docs/en/dev_101_services.html 

