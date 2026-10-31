"""Safe byte-buffer range copying for the COMP-014 example.

The fast path copies forward only when the source and destination ranges do
not overlap.  Overlapping ranges use a source snapshot so every input byte is
read before a write can overwrite it.
"""

from __future__ import annotations


def _validate(buffer: bytes | bytearray, src: int, dst: int, length: int) -> None:
    if not isinstance(buffer, (bytes, bytearray)):
        raise TypeError("buffer must be bytes or bytearray")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in (src, dst, length)):
        raise TypeError("src, dst, and length must be integers")
    if src < 0 or dst < 0 or length < 0:
        raise ValueError("src, dst, and length must be non-negative")
    if src + length > len(buffer) or dst + length > len(buffer):
        raise ValueError("copy range is outside the buffer")


def _overlaps(src: int, dst: int, length: int) -> bool:
    return length > 0 and src < dst + length and dst < src + length


def copy_range(buffer: bytes | bytearray, src: int, dst: int, length: int) -> bytes:
    """Return ``buffer`` after copying ``length`` bytes from ``src`` to ``dst``.

    Non-overlapping ranges use a forward copy.  For overlapping ranges the
    source bytes are snapshotted before writing, preserving memmove semantics.
    The input is never mutated; the returned value is always ``bytes``.
    """

    _validate(buffer, src, dst, length)
    result = bytearray(buffer)

    if _overlaps(src, dst, length):
        result[dst : dst + length] = result[src : src + length]
    else:
        for offset in range(length):
            result[dst + offset] = result[src + offset]

    return bytes(result)


if __name__ == "__main__":
    print(copy_range(b"abcdefghij", src=1, dst=6, length=3))
