# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_musicplayer`
================================================================================

An SD card music player for CircuitPython: FLAC, MP3 and Ogg Vorbis, an artist,
album and track index, and menus on an e-ink screen.

.. code-block:: python

    import adafruit_musicplayer

    adafruit_musicplayer.run()

* Author(s): Mikey Sklar

Implementation Notes
--------------------

**Hardware:** RP2350 with PSRAM, TLV320DAC3100, 2.13" SSD1680 e-ink, microSD,
NeoKey 1x4 and ANO rotary encoder.

**Software and Dependencies:**

* CircuitPython 11 or later
* adafruit_flac, adafruit_ogg, adafruit_tlv320, adafruit_seesaw
"""

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MusicPlayer.git"


def _config(overrides):
    """The pins and settings, with the caller's changes."""
    import board  # noqa: PLC0415

    config = {
        "bit_clock": board.A0,
        "word_select": board.A1,
        "data": board.A2,
        "mclk": board.D5,
        "sd_cs": board.D24,
        "eink_cs": board.D25,
        "eink_dc": board.RX,
        "eink_reset": board.TX,
        "eink_busy": board.A3,
        "volume_db": 0,
        "title": "MUSIC PLAYER",
    }
    for name, value in overrides.items():
        if name not in config:
            raise ValueError("unknown setting: " + name)
        config[name] = value
    return config


def run(**settings):
    """Start the player. Does not return.

    :param settings: Changes to the defaults: ``bit_clock``, ``word_select``,
      ``data``, ``mclk``, ``sd_cs``, ``eink_cs``, ``eink_dc``, ``eink_reset``,
      ``eink_busy``, ``volume_db`` (0 to -63) and ``title``.
    """
    import microcontroller  # noqa: PLC0415

    # FLAC at 24/96 needs the headroom next to the e-ink and key polling.
    microcontroller.cpu.frequency = 300_000_000
    config = _config(settings)

    # The order sets what lands in internal SRAM, and 24/96 only keeps up from
    # SRAM: the decoder's kernel first, then the audio buffers and the I2S DMA
    # copies, then everything else (see _app.py for the decoder and the index).
    import adafruit_flac  # noqa: PLC0415, F401

    from adafruit_musicplayer import _output  # noqa: PLC0415

    audio, out_buf = _output.reserve(config)

    from adafruit_musicplayer import _app  # noqa: PLC0415

    _app.run(config, audio, out_buf)


def check(**settings):
    """Test the wiring, one part at a time, without playing anything. Prints
    each result and shows them on the screen if it works. Returns True if
    everything was found.

    :param settings: The same changes to the defaults as `run`.
    """
    from adafruit_musicplayer import _check  # noqa: PLC0415

    return _check.run(_config(settings))
