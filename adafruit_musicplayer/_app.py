# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Starts everything in the right order, then runs the main loop."""

import os
import time

import adafruit_flac
import adafruit_tlv320
import board
import busio
import pwmio
import sdcardio
import storage

from adafruit_musicplayer import _dac, eink, keys, library, menus, player

# The file with the largest blocks and frames sizes the FLAC decoder's buffers.
# Opened on a smaller one, they get reallocated in PSRAM for bigger files, and
# 24/96 only keeps up from SRAM. Any file does if this one isn't on the card.
_BIGGEST_BLOCKS = "/Aphex_Twin-Selected_Ambient_Works/12-aphex_twin-12.flac"


def _stop(spi, config, title, *lines):
    """Say what's wrong, on the screen if there is one, and stay here."""
    print(title, *lines)
    try:
        screen = eink.EinkScreen(spi, config)
        screen.show(title, lines)
    except (ImportError, ValueError, RuntimeError, OSError) as e:
        print("no screen:", e)
    while True:
        time.sleep(1)


def _first_flac(vfs):
    """A FLAC to size the decoder on: the biggest, else the index's first."""
    try:
        vfs.stat(_BIGGEST_BLOCKS)
        return _BIGGEST_BLOCKS
    except OSError:
        pass
    try:
        with vfs.open(library.INDEX, "r") as f:
            path = f.readline().split("\t")[0]
    except OSError:
        return None
    return path if path[-5:].lower() == ".flac" else None


def _open_i2c():
    # 50 kHz: with the NeoKey and ANO on STEMMA QT, 400 kHz misses devices and
    # can hang the bus. For about a second after the bus starts, transactions
    # fail, then it settles. Wait for 10 good reads of the TLV in a row.
    i2c = busio.I2C(board.SCL, board.SDA, frequency=50_000)
    while not i2c.try_lock():
        pass
    good = 0
    settle_until = time.monotonic() + 3
    while good < 10 and time.monotonic() < settle_until:
        try:
            i2c.writeto_then_readfrom(0x18, b"\x00", bytearray(1))
            good += 1
        except OSError:
            good = 0
    i2c.unlock()
    return i2c


def run(config, audio, out_buf):  # noqa: PLR0912, PLR0914, PLR0915
    """Never returns."""
    mclk = pwmio.PWMOut(config["mclk"], frequency=_dac.MCLK_HZ, duty_cycle=32768)  # noqa: F841
    spi = board.SPI()
    try:
        sd = sdcardio.SDCard(spi, config["sd_cs"], baudrate=24_000_000)
    except (OSError, ValueError) as e:
        _stop(spi, config, "NO SD CARD", "Is a card in?", "Check SD wiring", str(e)[:23])
    # Read the card through the VfsFat object, so CIRCUITPY needs no /sd folder.
    vfs = storage.VfsFat(sd)

    flac = None
    path = _first_flac(vfs)
    if path:
        try:
            flac = adafruit_flac.FLACDecoder(vfs.open(path, "rb"))
        except player.BAD_FILE as e:  # opened on the first track that plays instead
            print("no decoder yet:", path, e)
    mp3 = None
    try:  # after the FLAC buffers, before the library takes the rest
        from adafruit_musicplayer import mp3file  # noqa: PLC0415

        mp3 = mp3file.MP3Decoder()
    except (ImportError, ValueError) as e:  # no build for this chip
        print("no MP3 decoder:", e)

    lib = library.Library(vfs, lambda n, total: n % 50 or print("indexing", n, "of", total))
    print(len(lib.tracks), "tracks,", len(lib.albums), "albums")
    if not len(lib.tracks):
        _stop(spi, config, "NO MUSIC", "No .flac .mp3 .ogg", "found on the card")

    i2c = _open_i2c()
    try:
        dac = adafruit_tlv320.TLV320DAC3100(i2c)
    except ValueError as e:
        _stop(spi, config, "NO DAC", "No TLV320 at 0x18", "Check I2C wiring", str(e)[:23])

    the_player = player.Player(
        lib, vfs, audio, out_buf, dac, flac=flac, mp3=mp3, volume_db=config["volume_db"]
    )
    ui = menus.Menus(lib, the_player)

    try:
        pad = keys.Keys(i2c)
        print("NeoKey", bool(pad.neokey), " ANO", bool(pad.ano))
    except ValueError as e:  # neither NeoKey nor ANO plugged in
        print("no keys:", e)
        pad = None

    try:
        screen = eink.EinkScreen(spi, config)
    except (ImportError, ValueError, RuntimeError) as e:
        print("no screen:", e)
        screen = None

    start = os.getenv("MUSICPLAYER_PLAY")  # settings.toml: a track to play at boot, for testing
    for album in lib.albums if start else ():
        queue = album[2]
        for n, i in enumerate(queue):
            if lib.tracks[i][0] == start:
                the_player.play(queue, n)
                ui.now_playing()
    if the_player.current is None and (pad is None or pad.neokey is None):
        the_player.play(lib.albums[0][2], 0, True)  # nothing to choose with: play the first album
        ui.now_playing()

    printed = -1
    last = time.monotonic_ns()
    while True:
        if the_player.update():
            ui.version += 1  # next track: the footer and now playing change
        ui.tick()
        if pad:
            events = pad.poll()
            for kind, value in events:
                ui.handle(kind, value)
            if events and screen:
                screen.poke()
        if ui.version != printed:
            printed = ui.version
            print(ui.text())
        if screen:
            screen.update(ui)
        t = time.monotonic_ns()
        if t - last >= 30_000_000_000:
            print("  underruns", the_player.out.underruns)
            last = t
