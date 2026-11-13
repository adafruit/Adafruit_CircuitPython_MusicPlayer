# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""Plays a queue of library tracks. No screen or keys here: Menus drives it."""

import time

import adafruit_flac

from adafruit_musicplayer import _dac, menus

LEVEL = 0.5  # output level, 0.0 to 1.0
HP_DB = -8.1  # TLV320 analog headphone volume, 0 (loud) to -78.3
DB_MIN = -63  # wheel range
DB_MAX = 0  # above this the DAC clips; loud masters distorted at 0 dB on headphones
RESTART_S = 3  # reverse after this far into a track restarts it
SCAN_S = 5  # seconds per rewind / fast-forward step (one step every 0.3 s held)
# What a damaged or unreadable file raises: FLACError is a ValueError, short
# reads give IndexError or struct's RuntimeError, a wild STREAMINFO a MemoryError.
BAD_FILE = (ValueError, OSError, IndexError, RuntimeError, MemoryError)


class Player:
    """Plays through one output and one set of decoders, kept across files."""

    def __init__(self, lib, vfs, audio, out_buf, dac, *, flac=None, mp3=None, volume_db=-20):  # noqa: PLR0913
        self.lib = lib
        self.vfs = vfs
        self.dac = dac
        self.out = adafruit_flac.FLACPlayer(audio, buffer=out_buf, level=LEVEL)
        self.decoder = flac  # the current file's decoder
        self.flac_decoder = flac
        self.mp3_decoder = mp3
        self.ogg_decoder = None  # made on the first .ogg
        self.file = flac.file if flac else None  # closed on the first play
        self.rate = 0
        self.db = volume_db
        self.queue = []
        self.pos = 0
        self.current = None  # library track index
        self.format = ""  # the current file's format and bit rate, for the screen
        self.started = 0
        self.skipped = False  # a damaged file was passed over; Menus.tick reports it

    @property
    def playing(self):
        """True while a track is playing and not paused."""
        return self.current is not None and not self.out.paused

    @property
    def paused(self):
        """True while a track is loaded and paused."""
        return self.current is not None and self.out.paused

    def position(self):
        """The current track's place in the queue, as (number, total), counting from 1."""
        return self.pos + 1, len(self.queue)

    def play(self, queue, pos, skip=False):
        """Play queue[pos], or with skip the first track from there that can
        play. False if it can't, and what was playing carries on, restarted
        where it was if the new file failed to open."""
        step = 1 if skip else 0
        pos = self._find(queue, pos, step)
        if pos < 0:
            return False
        had = self.current is not None
        old_queue, old_pos, paused = self.queue, self.pos, self.paused
        at = self.decoder.samples_decoded / self.rate if had else 0
        self.queue = queue
        if self._start(pos, step):
            return True
        self.skipped = False  # the caller reports this one
        self.queue, self.pos = old_queue, old_pos
        if had and self._start(old_pos, 0):
            self._seek(at)
            if paused:
                self.out.pause()
        return False

    def _find(self, queue, pos, step):
        """The first playable index from pos going by step, else -1. With
        step 0, only pos itself."""
        while 0 <= pos < len(queue):
            if menus.playable(self.lib.tracks[queue[pos]][0]):
                return pos
            if not step:
                break
            pos += step
        return -1

    def _start(self, pos, step=1):
        """Stop, then play from pos, passing over what can't play. False, with
        nothing playing, if nothing can."""
        self.out.stop()
        if self.file:
            self.file.close()
            self.file = None
        pos = self._find(self.queue, pos, step)
        while pos >= 0:
            if self._load(pos):
                return True
            self.skipped = True
            pos = self._find(self.queue, pos + step, step) if step else -1
        self.current = None
        return False

    def _open_flac(self):
        f = self.file
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if self.flac_decoder is None:
            self.flac_decoder = adafruit_flac.FLACDecoder(f)
        else:
            self.flac_decoder.open(f)
        kbits = size // 125
        return self.flac_decoder, "FLAC %dk" % (kbits // max(int(self.flac_decoder.duration), 1))

    def _open_mp3(self):
        if self.mp3_decoder is None:
            raise ValueError("no MP3 decoder for this chip")
        self.mp3_decoder.open(self.file)
        return self.mp3_decoder, "MP3 %dk" % (self.mp3_decoder.bit_rate // 1000)

    def _open_ogg(self):
        if self.ogg_decoder is None:
            try:
                import adafruit_ogg  # noqa: PLC0415
            except ImportError as e:
                raise ValueError("adafruit_ogg is not installed") from e
            self.ogg_decoder = adafruit_ogg.OggDecoder(self.file)
        else:
            self.ogg_decoder.open(self.file)
        return self.ogg_decoder, "OGG %dk" % (self.ogg_decoder.nominal_bitrate // 1000)

    def _load(self, pos):
        i = self.queue[pos]
        path = self.lib.tracks[i][0]
        low = path.lower()
        try:  # noqa: PLW0717
            self.file = self.vfs.open(path, "rb")
            if low.endswith(".mp3"):
                self.decoder, self.format = self._open_mp3()
            elif low.endswith(".ogg"):
                self.decoder, self.format = self._open_ogg()
            else:
                self.decoder, self.format = self._open_flac()
            d = self.decoder
            if d.sample_rate != self.rate:
                self.rate = d.sample_rate
                _dac.set_clocks(self.dac, self.rate)
                self.dac.headphone_output = True
                self.dac.speaker_output = False  # class-D amp off, nothing on it
                self.dac.headphone_volume = HP_DB  # headphone_output sets -20.1
                self.dac.dac_volume = self.db
            print("%s  %d Hz %s" % (path, self.rate, self.format))
            self._play()
        except BAD_FILE as e:
            print("can't play", path, e)
            if self.file:
                self.file.close()
                self.file = None
            self.rate = 0  # set the clocks again next time
            return False
        self.pos = pos
        self.current = i
        self.started = time.monotonic()
        return True

    def _play(self):
        out = self.out
        out.play(self.decoder)
        # time the halves from the real output rate (see _dac.output_rate)
        out._half_ns = int(
            out._half // self.decoder.channel_count * 1e9 / _dac.output_rate(self.rate)
        )

    def pause(self):
        """Pause the track if one is playing."""
        if self.playing:
            self.out.pause()

    def resume(self):
        """Carry on from where pause() stopped."""
        if self.paused:
            self.out.resume()

    def reverse(self):
        """Restart the track, or in its first RESTART_S seconds go to the
        previous track that can play."""
        if self.current is None:
            return
        previous = self._find(self.queue, self.pos - 1, -1)
        if time.monotonic() - self.started > RESTART_S or previous < 0:
            self._start(self.pos)
        else:
            self._start(previous, -1)

    def forward(self):
        """Skip to the next track in the queue."""
        if self.current is not None:
            self._start(self.pos + 1)

    def scan(self, direction):
        """Rewind (-1) or fast-forward (1) one SCAN_S step."""
        if self.current is None:
            return
        self._seek(self.decoder.samples_decoded / self.rate + direction * SCAN_S)

    def _seek(self, seconds):
        if not hasattr(self.decoder, "seek"):  # adafruit_ogg has no seek yet
            return
        try:
            at = self.decoder.seek(max(0, seconds))
            self._play()  # past the end, this plays silence and update() moves on
            self.started = time.monotonic() - at  # so reverse() still restarts the track
        except BAD_FILE as e:
            self._bad_file(e)

    def _bad_file(self, e):
        print("can't play on:", e)
        self.skipped = True
        self._start(self.pos + 1)

    def volume(self, steps):
        """Turn the DAC volume up or down by steps dB, kept between DB_MIN and DB_MAX."""
        self.db = max(DB_MIN, min(DB_MAX, self.db + steps))
        self.dac.dac_volume = self.db

    def update(self):
        """Keep the audio fed. Returns True when a track just ended."""
        if self.current is None:
            return False
        try:
            self.out.update()
        except BAD_FILE as e:
            self._bad_file(e)
            return True
        if not self.out.playing and not self.out.paused:
            print("  done, underruns", self.out.underruns)
            self._start(self.pos + 1)
            return True
        return False
