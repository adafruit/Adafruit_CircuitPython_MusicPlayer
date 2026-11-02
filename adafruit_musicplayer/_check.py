# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""check(): find each part of the player, without playing anything."""

import board
import busio
import sdcardio
import storage

_I2C_PARTS = (("DAC", 0x18), ("NeoKey", 0x30), ("ANO", 0x49))


def _card(spi, config):
    sd = sdcardio.SDCard(spi, config["sd_cs"], baudrate=24_000_000)
    vfs = storage.VfsFat(sd)
    vfs.stat("/")


def run(config):
    results = []
    spi = board.SPI()
    try:
        _card(spi, config)
        results.append(("SD card", True))
    except (OSError, ValueError) as e:
        print("SD card:", e)
        results.append(("SD card", False))

    found = ()
    try:
        i2c = busio.I2C(board.SCL, board.SDA, frequency=50_000)
        while not i2c.try_lock():
            pass
        found = i2c.scan()
        i2c.unlock()
    except (OSError, RuntimeError, ValueError) as e:  # no pull-ups: nothing on the bus
        print("I2C:", e)
    for name, address in _I2C_PARTS:
        results.append((name, address in found))

    from adafruit_musicplayer import eink  # noqa: PLC0415

    screen = None
    try:
        screen = eink.EinkScreen(spi, config)
        results.append(("Screen", True))
    except (OSError, RuntimeError, ValueError) as e:
        print("Screen:", e)
        results.append(("Screen", False))

    lines = ["%s %s" % ("ok " if good else "BAD", name) for name, good in results]
    print("\n".join(lines))
    if screen:
        screen.show("WIRING CHECK", lines[:4])  # the screen itself is working if this shows
    return all(good for _, good in results)
