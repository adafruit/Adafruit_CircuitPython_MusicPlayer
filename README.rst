Introduction
============

An SD card music player for CircuitPython. It plays FLAC, MP3 and Ogg Vorbis,
builds an artist, album and track index of the card, and shows menus on an
e-ink screen.

.. code-block:: python

    import adafruit_musicplayer

    adafruit_musicplayer.run()

Tested on an RP2350 Feather with e-ink, and headless on the Fruit Jam. Support
for the Fruit Jam TouchDeck screen and touch is planned for 1.1.

Dependencies
============
This library depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_ 11 or later
* `Adafruit CircuitPython FLAC <https://github.com/adafruit/Adafruit_CircuitPython_FLAC>`_
* `Adafruit CircuitPython Ogg <https://github.com/adafruit/Adafruit_CircuitPython_OGG>`_
* `Adafruit CircuitPython TLV320 <https://github.com/adafruit/Adafruit_CircuitPython_TLV320>`_
* `Adafruit CircuitPython seesaw <https://github.com/adafruit/Adafruit_CircuitPython_seesaw>`_
* `Bus Device <https://github.com/adafruit/Adafruit_CircuitPython_BusDevice>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_
or individual libraries can be installed using
`circup <https://github.com/adafruit/circup>`_.

Installing to a Connected CircuitPython Device with Circup
==========================================================

Make sure that you have ``circup`` installed in your Python environment.
Install it with the following command if necessary:

.. code-block:: shell

    pip3 install circup

With ``circup`` installed and your CircuitPython device connected use the
following command to install:

.. code-block:: shell

    circup install adafruit_musicplayer

This also installs FLAC, Ogg, TLV320, seesaw and Bus Device. Or the following
command to update an existing version:

.. code-block:: shell

    circup update

Hardware
========

* RP2350 Feather with PSRAM, at 300 MHz
* TLV320DAC3100, with MCLK from a PWM pin
* 2.13" SSD1680 e-ink, and a microSD card, on one SPI bus
* NeoKey 1x4 and ANO rotary encoder on STEMMA QT

Default pins: I2S ``A0`` ``A1`` ``A2``, MCLK ``D5``, SD CS ``D24``, e-ink CS
``D25``, DC ``RX``, reset ``TX``, busy ``A3``. Pass changes to ``run()``, for
example ``adafruit_musicplayer.run(sd_cs=board.D10)``.

The volume starts at -20 dB. Change it with ``volume_db``, from 0 to -63, for
example ``adafruit_musicplayer.run(volume_db=-30)``.

Controls
========

* ANO wheel: move the highlight, or volume on Now Playing
* ANO select: open, or play
* ANO up: back. ANO down: Now Playing. ANO left and right: page down and up
* NeoKey 1 to 4: play, pause, reverse, forward. Hold 3 or 4 to rewind or
  fast-forward

Checking the wiring
===================

.. code-block:: python

    import adafruit_musicplayer

    adafruit_musicplayer.check()

Reports the SD card, DAC, NeoKey, ANO and screen, on the serial console and on
the screen.

The index
=========

The first start reads the card into ``/FRISSON.IDX``, about a minute for 5,700
tracks. Delete that file after changing the music.

Known limits
============

* Rewind and fast-forward work on FLAC (adafruit-circuitpython-flac 1.0.3 or
  newer) and MP3. Ogg has no ``seek()`` yet, so they do nothing on Ogg files.
* Ogg Vorbis plays up to 22 kHz stereo at 300 MHz (tested on a Fruit Jam). 44.1
  and 48 kHz stereo Ogg underrun; use FLAC or MP3 for those. ``run()`` does not
  support the Fruit Jam pins yet.
* MP3 is RP2350 (``armv7emsp``) only.
* File names with accented letters fail on exFAT cards, from a CircuitPython bug.

License
=======

The Python is MIT. ``ter_u18b.bdf`` is Terminus, under the SIL Open Font License
1.1. ``mp3_native.armv7emsp.mpy`` contains the Helix MP3 decoder, Portions
Copyright (c) 1995-2002 RealNetworks, Inc., under the RealNetworks Public Source
License 1.0 (RPSL), the same code Adafruit ships in CircuitPython's
``audiomp3`` (from `Adafruit_MP3 <https://github.com/adafruit/Adafruit_MP3>`_).
