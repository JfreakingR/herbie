"""Dump static final field VALUES from a DEX class.

The command codes for the SEGO/VAVA serial protocol are `static final short`
constants in `TermSegoValue`. Their values are not in the field table — they
live in the class_def's `static_values_off` encoded_array, positionally matched
to the static fields listed in class_data.

Usage:
    python dexstatics.py classes.dex TermSegoValue
"""

import struct
import sys


def uleb128(data, offset):
    result, shift = 0, 0
    while True:
        b = data[offset]
        offset += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    return result, offset


class Dex:
    def __init__(self, path):
        self.d = open(path, "rb").read()
        (self.str_size, self.str_off, self.type_size, self.type_off,
         self.proto_size, self.proto_off, self.field_size, self.field_off,
         self.method_size, self.method_off, self.cls_size,
         self.cls_off) = struct.unpack_from("<12I", self.d, 0x38)

    def string(self, idx):
        (off,) = struct.unpack_from("<I", self.d, self.str_off + idx * 4)
        _, p = uleb128(self.d, off)
        return self.d[p:self.d.index(b"\x00", p)].decode("utf-8", "replace")

    def type_name(self, idx):
        (s,) = struct.unpack_from("<I", self.d, self.type_off + idx * 4)
        return self.string(s)

    def field_name(self, idx):
        _, _, name_idx = struct.unpack_from("<HHI", self.d, self.field_off + idx * 8)
        return self.string(name_idx)

    def read_value(self, p):
        """encoded_value -> (python value, new offset)."""
        arg_type = self.d[p]
        p += 1
        vtype = arg_type & 0x1F
        size = (arg_type >> 5) + 1

        def raw(n):
            return int.from_bytes(self.d[p:p + n], "little")

        if vtype in (0x00, 0x02, 0x03, 0x04, 0x06):     # byte/short/char/int/long
            v = raw(size)
            signed = vtype in (0x00, 0x02, 0x04, 0x06)
            if signed and size and self.d[p + size - 1] & 0x80:
                v -= 1 << (size * 8)
            return v, p + size
        if vtype == 0x17:                                # string
            return self.string(raw(size)), p + size
        if vtype == 0x1F:                                # boolean
            return bool(arg_type >> 5), p
        if vtype == 0x1E:                                # null
            return None, p
        return f"<type 0x{vtype:02x}>", p + (size if vtype not in (0x1E, 0x1F) else 0)

    def statics(self, needle):
        out = {}
        for i in range(self.cls_size):
            off = self.cls_off + i * 32
            class_idx, = struct.unpack_from("<I", self.d, off)
            name = self.type_name(class_idx)
            if needle not in name:
                continue
            class_data_off, = struct.unpack_from("<I", self.d, off + 24)
            static_values_off, = struct.unpack_from("<I", self.d, off + 28)
            if not class_data_off:
                continue

            p = class_data_off
            sf, p = uleb128(self.d, p)
            _inf, p = uleb128(self.d, p)
            _dm, p = uleb128(self.d, p)
            _vm, p = uleb128(self.d, p)
            names, idx = [], 0
            for _ in range(sf):
                diff, p = uleb128(self.d, p)
                _, p = uleb128(self.d, p)
                idx += diff
                names.append(self.field_name(idx))

            values = []
            if static_values_off:
                q = static_values_off
                count, q = uleb128(self.d, q)
                for _ in range(count):
                    v, q = self.read_value(q)
                    values.append(v)

            out[name] = list(zip(names, values + [None] * (len(names) - len(values))))
        return out


def main():
    dex = Dex(sys.argv[1])
    needle = sys.argv[2] if len(sys.argv) > 2 else "TermSegoValue"
    for cls, pairs in dex.statics(needle).items():
        pretty = cls[1:-1].replace("/", ".")
        print(f"\n=== {pretty} ===")
        for name, value in pairs:
            if value is None:
                continue
            if isinstance(value, int):
                print(f"  {name:<42} = {value:6d}   0x{value & 0xFFFF:04X}")
            else:
                print(f"  {name:<42} = {value!r}")


if __name__ == "__main__":
    main()
