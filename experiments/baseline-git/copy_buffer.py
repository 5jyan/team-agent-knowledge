"""Small byte-buffer range copy used by the baseline integration check."""


def copy_range(
    buffer: bytes,
    source_index: int,
    length: int,
    destination_index: int,
) -> bytes:
    """Return ``buffer`` after copying one range to another index."""
    if length < 0 or source_index < 0 or destination_index < 0:
        raise ValueError("copy indexes and length must be non-negative")

    source_end = source_index + length
    destination_end = destination_index + length
    if source_end > len(buffer) or destination_end > len(buffer):
        raise ValueError("copy range must fit within the buffer")

    result = bytearray(buffer)
    ranges_are_disjoint = (
        destination_index >= source_end or source_index >= destination_end
    )
    if ranges_are_disjoint:
        for offset in range(length):
            result[destination_index + offset] = result[source_index + offset]
    else:
        snapshot = result[source_index:source_end]
        result[destination_index:destination_end] = snapshot
    return bytes(result)


if __name__ == "__main__":
    print(copy_range(b"abcdefghij", source_index=1, length=3, destination_index=6))
