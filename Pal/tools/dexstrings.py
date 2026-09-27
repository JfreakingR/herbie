"""Pull the string table out of a DEX file.

Android DEX stores strings in a proper table with a header offset, so a generic
`strings` scan misses most of them (they are MUTF-8 with a ULEB128 length
prefix, not NUL-terminated ASCII runs).
"""

import struct
import sys


def uleb128(data, offset):
    result = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            break
        shift += 7
    return result, offset


def dex_strings(path):
    data = open(path, "rb").read()
    if data[:4] not in (b"dex\n", b"dey\n"):
        return []
    # header: string_ids_size at 0x38, string_ids_off at 0x3C
    count, off = struct.unpack_from("<II", data, 0x38)
    out = []
    for i in range(count):
        (string_off,) = struct.unpack_from("<I", data, off + i * 4)
        try:
            length, p = uleb128(data, string_off)
            raw = bytearray()
            while data[p] != 0:
                raw.append(data[p])
                p += 1
            out.append(raw.decode("utf-8", "replace"))
        except (IndexError, struct.error):
            continue
    return out


if __name__ == "__main__":
    path = sys.argv[1]
    needles = [n.lower() for n in sys.argv[2:]] if len(sys.argv) > 2 else None
    strings = dex_strings(path)
    print(f"# {len(strings)} strings in {path}")
    for s in strings:
        if needles is None or any(n in s.lower() for n in needles):
            if 2 <= len(s) <= 200:
                print(s)
