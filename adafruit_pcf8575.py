# SPDX-FileCopyrightText: Copyright (c) 2022 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_pcf8575`
==================

CircuitPython library for Adafruit PCF8575 GPIO expander


* Author(s): ladyada

Implementation Notes
--------------------

**Hardware:**

* `Adafruit PCF8575 GPIO Expander <https://www.adafruit.com/product/5611>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads
* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

"""

try:
    from typing import Optional
    import busio
except ImportError:
    pass


from adafruit_bus_device.i2c_device import I2CDevice
from micropython import const
import digitalio

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PCF8575.git"

PCF8575_I2CADDR_DEFAULT: int = const(0x20)  # Default I2C address


class PCF8575:
    """Interface library for PCF8575 GPIO expanders

    :param ~busio.I2C i2c_bus: The I2C bus the PCF8575 is connected to.
    :param int address: The I2C device address. Default is :const:`0x20`
    """

    def __init__(
        self, i2c_bus: busio.I2C, address: int = PCF8575_I2CADDR_DEFAULT
    ) -> None:
        self.i2c_device = I2CDevice(i2c_bus, address)
        self._writebuf = bytearray([0, 0])
        self._readbuf = bytearray([0, 0])

    def get_pin(self, pin: int) -> "DigitalInOut":
        """Convenience function to create an instance of the DigitalInOut class
        pointing at the specified pin of this PCF8575 device.

        :param int pin: pin to use for digital IO, 0 to 15
        """
        assert 0 <= pin <= 15
        return DigitalInOut(pin, self)

    def write_gpio(self, val: int) -> None:
        """Write a full 16-bit value to the GPIO register

        :param int val: The value to write to the register
        """

        self._writebuf[0] = val & 0xFF
        self._writebuf[1] = (val >> 8) & 0xFF
        with self.i2c_device as i2c:
            i2c.write(self._writebuf)

    def read_gpio(self) -> int:
        """Read the full 16-bits of data from the GPIO register"""
        with self.i2c_device as i2c:
            i2c.readinto(self._readbuf)
        return self._readbuf[0] | (self._readbuf[1] << 8)

    def write_pin(self, pin: int, val: bool) -> None:
        """Set a single GPIO pin high/pulled-up or driven low

        :param int pin: The pin number
        :param bool val: The state to set
        """

        buff = self._writebuf[0] | (self._writebuf[1] << 8)
        if val:
            # turn on the pullup (write high)
            self.write_gpio(buff | (1 << pin))
        else:
            # turn on the transistor (write low)
            self.write_gpio(buff & ~(1 << pin))

    def read_pin(self, pin: int) -> bool:
        """Read a single GPIO pin as high/pulled-up or driven low

        :param int pin: The pin number
        """

        return bool((self.read_gpio() >> pin) & 0x1)


"""
`digital_inout`
====================================================
Digital input/output of the PCF8575.
* Author(s): Tony DiCola
"""


class DigitalInOut:
    """Digital input/output of the PCF8575.  The interface is exactly the
    same as the digitalio.DigitalInOut class, however:

      * PCF8575 does not support pull-down resistors
      * PCF8575 does not actually have a sourcing transistor, instead there's
        an internal pullup

    Exceptions will be thrown when attempting to set unsupported pull
    configurations.
    """

    def __init__(self, pin_number: int, pcf: PCF8575) -> None:
        """Specify the pin number of the PCF8575 0..15, and instance.

        :param int pin_number: The pin number
        :param PCF8575 pcf: The associated PCF8575 instance
        """

        self._pin = pin_number
        self._pcf = pcf
        self._dir = (
            digitalio.Direction.INPUT
        )  # this is meaningless but we need something!

    # kwargs in switch functions below are _necessary_ for compatibility
    # with DigitalInout class (which allows specifying pull, etc. which
    # is unused by this class).  Do not remove them, instead turn off pylint
    # in this case.
    # pylint: disable=unused-argument
    def switch_to_output(self, value: bool = False, **kwargs) -> None:
        """Switch the pin state to a digital output with the provided starting
        value (True/False for high or low, default is False/low).

        Note that keyword arguments are not parsed, and only included for
        compatibility with code expecting :py:class:`digitalio.DigitalInOut`.

        :param bool value: The value to set upon switching to output; default
            is ``False``
        """
        self.direction = digitalio.Direction.OUTPUT
        self.value = value

    def switch_to_input(self, pull: Optional[digitalio.Pull] = None, **kwargs) -> None:
        """Switch the pin state to a digital input which is the same as
        setting the light pullup on.  Note that true tri-state or
        pull-down resistors are NOT supported!

        Note that keyword arguments are not parsed, and only included for
        compatibility with code expecting :py:class:`digitalio.DigitalInOut`.
        """

        self.direction = digitalio.Direction.INPUT
        self.pull = pull

    # pylint: enable=unused-argument

    @property
    def value(self) -> bool:
        """The value of the pin, either ``True`` for high/pulled-up or
        ``False`` for low.
        """
        return self._pcf.read_pin(self._pin)

    @value.setter
    def value(self, val: bool) -> None:
        self._pcf.write_pin(self._pin, val)

    @property
    def direction(self) -> digitalio.Direction:
        """Setting a pin to OUTPUT drives it low, setting it to
        an INPUT enables the light pullup.
        """
        return self._dir

    @direction.setter
    def direction(self, val: digitalio.Direction) -> None:
        if val == digitalio.Direction.INPUT:
            # for inputs, turn on the pullup (write high)
            self._pcf.write_pin(self._pin, True)
            self._dir = val
        elif val == digitalio.Direction.OUTPUT:
            # for outputs, turn on the transistor (write low)
            self._pcf.write_pin(self._pin, False)
            self._dir = val
        else:
            raise ValueError("Expected INPUT or OUTPUT direction!")

    @property
    def pull(self) -> digitalio.Pull:
        """
        Pull-up is always activated so this will always return the same,
        thing: :py:attr:`digitalio.Pull.UP`
        """
        return digitalio.Pull.UP

    @pull.setter
    def pull(self, val: digitalio.Pull) -> None:
        if val is digitalio.Pull.UP:
            # for inputs, turn on the pullup (write high)
            self._pcf.write_pin(self._pin, True)
        else:
            raise NotImplementedError("Pull-down resistors not supported.")
