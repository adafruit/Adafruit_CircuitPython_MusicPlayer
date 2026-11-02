// SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
//
// SPDX-License-Identifier: MIT
#pragma once
#include <stddef.h>
void *mp3_alloc(size_t sz);
#define MPDEC_ALLOCATOR(x) mp3_alloc(x)
#define MPDEC_FREE(x)
