# SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT
# mp3_native.mpy, a native module:
#   make MPY_DIR=path/to/circuitpython MP3_SRC=path/to/circuitpython/lib/mp3/src
# Then copy it to ../../../adafruit_musicplayer/mp3_native.$(ARCH).mpy.
# Use the CircuitPython tree whose firmware will load it (the .mpy version must match).
# MP3_SRC is the Helix decoder: see the README for its license.
MPY_DIR ?= ../../../../circuitpython
MP3_SRC ?= $(MPY_DIR)/lib/mp3/src
MOD = mp3_native
ARCH ?= armv7emsp
HELIX = bitstream buffers dct32 dequant dqchan huffman hufftabs imdct mp3dec mp3tabs polyphase \
	scalfact stproc subband trigtabs
$(shell ln -sfn $(MP3_SRC) helix)
SRC = mp3_native.c $(addprefix helix/,$(addsuffix .c,$(HELIX)))
LINK_RUNTIME = 1
CFLAGS_EXTRA = -O2 -fwrapv -w -Ihelix -include mp3_alloc.h
export PYTHONHASHSEED = 0

include $(MPY_DIR)/py/dynruntime.mk
