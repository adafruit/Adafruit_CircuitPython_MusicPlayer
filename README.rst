Introduction
============

An SD card music player for CircuitPython. It plays FLAC, MP3 and Ogg Vorbis,
builds an artist, album and track index of the card, and shows menus on an
e-ink screen.

.. code-block:: python

    import adafruit_musicplayer

    adafruit_musicplayer.run()

Status: prototype. Not yet offered upstream.

Hardware
========

* RP2350 Feather with PSRAM, at 300 MHz
* TLV320DAC3100, with MCLK from a PWM pin
* 2.13" SSD1680 e-ink, and a microSD card, on one SPI bus
* NeoKey 1x4 and ANO rotary encoder on STEMMA QT

Default pins: I2S ``A0`` ``A1`` ``A2``, MCLK ``D5``, SD CS ``D24``, e-ink CS
``D25``, DC ``RX``, reset ``TX``, busy ``A3``. Pass changes to ``run()``, for
example ``adafruit_musicplayer.run(sd_cs=board.D10)``.

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

* Rewind and fast-forward need ``seek()``, which only the FLAC branch this was
  built with has. Without it they do nothing.
* Ogg Vorbis keeps up to 22 kHz stereo on the Fruit Jam, at the 300 MHz that
  ``run()`` sets. 44.1 and 48 kHz stereo Ogg underrun; use FLAC or MP3 for those.
* MP3 is RP2350 (``armv7emsp``) only.
* File names with accented letters fail on exFAT cards, from a CircuitPython bug.

License
=======

The Python is MIT. ``ter_u18b.bdf`` is Terminus, under the SIL Open Font License
1.1. ``mp3_native.armv7emsp.mpy`` contains the Helix MP3 decoder, under the
RealNetworks RPSL and RCSL. Those terms have not been reviewed for this library.
