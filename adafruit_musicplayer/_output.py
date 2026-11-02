# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""The I2S output and its buffer, allocated while SRAM is free.

The I2S DMA copies come from internal SRAM, twice the whole buffer. Playing the
buffer once reserves them before anything else loads.
"""

from array import array

import audiobusio
import audiocore

RATE = 96000  # sizes the buffer; lower rates get longer halves
BUFFER_MS = 64  # per half: 49 KB, plus 98 KB of DMA copies


def reserve(config):
    """Returns (the I2SOut, the output buffer)."""
    out_buf = array("h", [0]) * (2 * (RATE * BUFFER_MS // 1000) * 2)
    audio = audiobusio.I2SOut(config["bit_clock"], config["word_select"], config["data"])
    audio.play(
        audiocore.RawSample(
            memoryview(out_buf), channel_count=2, sample_rate=RATE, single_buffer=False
        ),
        loop=True,
    )
    audio.stop()
    return audio, out_buf
