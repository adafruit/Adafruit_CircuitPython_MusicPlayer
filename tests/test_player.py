# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""The Player and Menus together, with the decoders and hardware replaced."""

import io
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for name in ("adafruit_tlv320", "board", "busio", "pwmio", "sdcardio", "storage"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules.setdefault(
    "microcontroller",
    types.SimpleNamespace(cpu=types.SimpleNamespace(frequency=300_000_000)),
)


class Out:
    def __init__(self, *a, **k):
        self.paused = False
        self.playing = False
        self.underruns = 0
        self._half = 1024
        self._half_ns = 0
        self.played = None

    def play(self, decoder):
        self.played = decoder
        self.playing = True

    def stop(self):
        self.playing = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def update(self):
        pass


class Decoder:
    def __init__(self, file=None, **k):
        self.file = file
        self.sample_rate = 44100
        self.channel_count = 2
        self.duration = 10
        self.samples_decoded = 44100
        self.bit_rate = 192000
        self.nominal_bitrate = 160000
        self.opened = []
        if file:
            self.open(file)

    def open(self, file):
        if file.read(3) == b"BAD":
            raise ValueError("bad file")
        self.file = file
        self.opened.append(file)


class Seekable(Decoder):
    def seek(self, seconds):
        self.sought = seconds
        return seconds


flac_module = types.ModuleType("adafruit_flac")
flac_module.FLACPlayer = Out
flac_module.FLACDecoder = Seekable
sys.modules["adafruit_flac"] = flac_module
ogg_module = types.ModuleType("adafruit_ogg")
ogg_module.OggDecoder = Decoder
sys.modules["adafruit_ogg"] = ogg_module

from adafruit_musicplayer import _dac, menus, player  # noqa: E402, PLC2701

_dac.set_clocks = lambda dac, rate: None
_dac.output_rate = lambda rate: rate


class Vfs:
    def __init__(self, bad=()):
        self.bad = bad

    def open(self, path, mode):
        return io.BytesIO(b"BAD" if path in self.bad else b"x" * 1250000)


TRACKS = [
    ("/A/1.flac", "A", "Al", "one", 1),
    ("/A/2.mp3", "A", "Al", "two", 2),
    ("/A/3.ogg", "A", "Al", "three", 3),
]


def make(bad=(), mp3=True):
    lib = types.SimpleNamespace(tracks=TRACKS, albums=[("A", "Al", range(3))])
    return player.Player(
        lib, Vfs(bad), None, None, types.SimpleNamespace(), mp3=Seekable() if mp3 else None
    )


def test_each_format_uses_its_decoder_and_shows_its_rate():
    p = make()
    queue = range(3)
    assert p.play(queue, 0)
    assert p.format == "FLAC 1000k"
    assert p.out.played is p.flac_decoder
    assert p.play(queue, 1)
    assert p.format == "MP3 192k"
    assert p.out.played is p.mp3_decoder
    assert p.play(queue, 2)
    assert p.format == "OGG 160k"
    assert p.out.played is p.ogg_decoder


def test_ogg_decoder_is_kept_across_files():
    p = make()
    p.play(range(3), 2)
    first = p.ogg_decoder
    p.play(range(3), 2)
    assert p.ogg_decoder is first
    assert len(first.opened) == 2


def test_scan_on_a_decoder_without_seek_is_harmless():
    p = make()
    p.play(range(3), 2)
    p.scan(1)
    assert p.current == 2


def test_scan_seeks_where_it_can():
    p = make()
    p.play(range(3), 0)
    p.scan(1)
    assert p.decoder.sought == 6


def test_track_end_moves_to_the_next():
    p = make()
    p.play(range(3), 0)
    p.out.playing = False
    assert p.update()
    assert p.current == 1


def test_no_mp3_decoder_skips_the_file():
    p = make(mp3=False)
    p.play(range(3), 0)
    p.forward()
    assert p.current == 2
    assert p.skipped


def test_refused_file_keeps_what_was_playing():
    p = make(bad=("/A/3.ogg",))
    p.play(range(3), 0)
    assert p.play(range(3), 2) is False
    assert p.current == 0


def test_all_three_extensions_are_playable():
    assert menus.playable("/a/b.FLAC")
    assert menus.playable("/a/b.mp3")
    assert menus.playable("/a/b.Ogg")
    assert not menus.playable("/a/b.wav")


def test_now_playing_shows_the_format():
    p = make()
    ui = menus.Menus(p.lib, p)
    p.play(range(3), 2)
    ui.now_playing()
    assert ui.view()["right"] == "OGG 160k"
