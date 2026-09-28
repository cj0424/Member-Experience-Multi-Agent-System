"""uuid7() in plain Python (RFC 9562): 48-bit Unix time in milliseconds,
version 7, then random bits. Returns a standard uuid.UUID."""

import os
import time
import uuid


def uuid7(timestamp: int | None = None, nanos: int | None = None) -> uuid.UUID:
    if timestamp is None:
        total_ns = time.time_ns()
    else:
        total_ns = int(timestamp) * 1_000_000_000 + int(nanos or 0)
    unix_ms = (total_ns // 1_000_000) & ((1 << 48) - 1)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (unix_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=value)


__all__ = ["uuid7"]