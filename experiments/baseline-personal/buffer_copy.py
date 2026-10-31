"""Byte-buffer segment copy used by the baseline personal evaluation."""

from __future__ import annotations


def copy_bytes_segment(
    buffer: bytes | bytearray,
    source_index: int,
    length: int,
    destination_index: int,
) -> bytes:
    """Copy a segment within a byte buffer and return the resulting bytes."""
    if not isinstance(buffer, (bytes, bytearray)):
        raise TypeError("buffer must be bytes or bytearray")
    if source_index < 0 or length < 0 or destination_index < 0:
        raise ValueError("indices and length must be non-negative")

    source_end = source_index + length
    destination_end = destination_index + length
    if source_end > len(buffer) or destination_end > len(buffer):
        raise ValueError("copy range must fit within the buffer")

    result = bytearray(buffer)
    result[destination_index:destination_end] = result[source_index:source_end]
    return bytes(result)
