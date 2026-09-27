"""Dump class fields and methods from a DEX file.

Written to recover the VAVA/SEGO serial packet layout without a full
disassembler. The control app uses JNA, so `TermSegoPacket$*` are Structure
subclasses mapping C structs one-to-one — which means the wire format is
readable straight out of the DEX field table, in declaration order.

Usage:
    python dexfields.py classes.dex TermSegoPacket
    python dexfields.py classes.dex                 # list every class with fields
"""

import struct
import sys

TYPE_NAMES = {
    "B": "byte", "C": "char", "D": "double", "F": "float",
    "I": "int", "J": "long", "S": "short", "Z": "boolean", "V": "void",
}


def uleb128(data, offset):
    result, shift = 0, 0
    while True:
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
    return result, offset


class Dex:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        d = self.data
        (self.string_ids_size, self.string_ids_off,
         self.type_ids_size, self.type_ids_off,
         self.proto_ids_size, self.proto_ids_off,
         self.field_ids_size, self.field_ids_off,
         self.method_ids_size, self.method_ids_off,
         self.class_defs_size, self.class_defs_off) = struct.unpack_from("<12I", d, 0x38)
        self._strings = {}

    def string(self, idx):
        if idx in self._strings:
            return self._strings[idx]
        (off,) = struct.unpack_from("<I", self.data, self.string_ids_off + idx * 4)
        _, p = uleb128(self.data, off)
        end = self.data.index(b"\x00", p)
        value = self.data[p:end].decode("utf-8", "replace")
        self._strings[idx] = value
        return value

    def type_name(self, idx):
        (sidx,) = struct.unpack_from("<I", self.data, self.type_ids_off + idx * 4)
        return self.string(sidx)

    def pretty_type(self, descriptor):
        arrays = 0
        while descriptor.startswith("["):
            arrays += 1
            descriptor = descriptor[1:]
        if descriptor in TYPE_NAMES:
            base = TYPE_NAMES[descriptor]
        elif descriptor.startswith("L"):
            base = descriptor[1:-1].replace("/", ".").split(".")[-1]
        else:
            base = descriptor
        return base + "[]" * arrays

    def fields_by_class(self):
        """field_id_item: class_idx u2, type_idx u2, name_idx u4 — in class order."""
        out = {}
        for i in range(self.field_ids_size):
            class_idx, type_idx, name_idx = struct.unpack_from(
                "<HHI", self.data, self.field_ids_off + i * 8
            )
            cls = self.type_name(class_idx)
            out.setdefault(cls, []).append(
                (self.string(name_idx), self.pretty_type(self.type_name(type_idx)))
            )
        return out

    def methods_by_class(self):
        out = {}
        for i in range(self.method_ids_size):
            class_idx, _proto_idx, name_idx = struct.unpack_from(
                "<HHI", self.data, self.method_ids_off + i * 8
            )
            cls = self.type_name(class_idx)
            out.setdefault(cls, []).append(self.string(name_idx))
        return out


def main():
    dex = Dex(sys.argv[1])
    needle = sys.argv[2] if len(sys.argv) > 2 else None

    fields = dex.fields_by_class()
    methods = dex.methods_by_class()

    for cls in sorted(fields):
        if needle and needle not in cls:
            continue
        pretty = cls[1:-1].replace("/", ".") if cls.startswith("L") else cls
        print(f"\n=== {pretty} ===")
        for name, type_name in fields[cls]:
            print(f"    {type_name:<24} {name}")
        interesting = [
            m for m in dict.fromkeys(methods.get(cls, []))
            if m not in ("<init>", "<clinit>")
        ]
        if interesting:
            print("    methods:", ", ".join(interesting[:14]))


if __name__ == "__main__":
    main()
