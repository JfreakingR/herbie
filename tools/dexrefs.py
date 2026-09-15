"""Find DEX methods that reference a class, field, method, or string.

This is a deliberately small read-only companion to ``dexfields.py`` and
``dexfieldorder.py``. It is sufficient for locating protocol construction code
without installing a full Android decompiler.

Usage:
    python dexrefs.py classes.dex TOY_LOGIN
"""

from __future__ import annotations

import struct
import sys

from dexfieldorder import Dex, SIZES, uleb128


TYPE_REF_OPS = {0x1C, 0x1F, 0x20, 0x22, 0x23}
FIELD_REF_OPS = set(range(0x52, 0x6E))
METHOD_REF_OPS = set(range(0x6E, 0x73)) | set(range(0x74, 0x79))


class ReferenceDex(Dex):
    def field_name(self, idx):
        class_idx, type_idx, name_idx = struct.unpack_from(
            "<HHI", self.d, self.field_off + idx * 8
        )
        return (
            f"{self.type_name(class_idx)}->{self.string(name_idx)}:"
            f"{self.type_name(type_idx)}"
        )

    def method_full_name(self, idx):
        class_idx, _proto_idx, name_idx = struct.unpack_from(
            "<HHI", self.d, self.method_off + idx * 8
        )
        return f"{self.type_name(class_idx)}->{self.string(name_idx)}"

    def encoded_methods(self):
        for i in range(self.cls_size):
            off = self.cls_off + i * 32
            class_idx, = struct.unpack_from("<I", self.d, off)
            class_name = self.type_name(class_idx)
            class_data_off, = struct.unpack_from("<I", self.d, off + 24)
            if not class_data_off:
                continue
            p = class_data_off
            sf, p = uleb128(self.d, p)
            inf, p = uleb128(self.d, p)
            dm, p = uleb128(self.d, p)
            vm, p = uleb128(self.d, p)
            for count in (sf, inf):
                field_idx = 0
                for _ in range(count):
                    diff, p = uleb128(self.d, p)
                    _, p = uleb128(self.d, p)
                    field_idx += diff
            for count in (dm, vm):
                method_idx = 0
                for _ in range(count):
                    diff, p = uleb128(self.d, p)
                    _, p = uleb128(self.d, p)
                    code_off, p = uleb128(self.d, p)
                    method_idx += diff
                    yield class_name, method_idx, code_off

    def references(self, code_off):
        if not code_off:
            return []
        insns_size, = struct.unpack_from("<I", self.d, code_off + 12)
        base = code_off + 16
        out = []
        pc = 0
        while pc < insns_size:
            unit, = struct.unpack_from("<H", self.d, base + pc * 2)
            op = unit & 0xFF
            size = SIZES[op]
            ref = None
            if op == 0x1A:  # const-string
                idx, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                ref = ("string", self.string(idx))
            elif op == 0x1B:  # const-string/jumbo
                idx, = struct.unpack_from("<I", self.d, base + (pc + 1) * 2)
                ref = ("string", self.string(idx))
            elif op in TYPE_REF_OPS:
                idx, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                ref = ("type", self.type_name(idx))
            elif op in FIELD_REF_OPS:
                idx, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                ref = ("field", self.field_name(idx))
            elif op in METHOD_REF_OPS:
                idx, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                ref = ("method", self.method_full_name(idx))

            if ref:
                out.append((pc, op, ref[0], ref[1]))

            if op == 0x00 and unit != 0:
                kind = unit >> 8
                if kind == 1:
                    n, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                    size = n * 2 + 4
                elif kind == 2:
                    n, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                    size = n * 4 + 2
                elif kind == 3:
                    width, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                    count, = struct.unpack_from("<I", self.d, base + (pc + 2) * 2)
                    size = (count * width + 1) // 2 + 4
            pc += max(size, 1)
        return out


def main():
    if len(sys.argv) < 3:
        raise SystemExit("usage: dexrefs.py classes.dex NEEDLE")
    dex = ReferenceDex(sys.argv[1])
    needle = sys.argv[2].lower()
    found = 0
    for class_name, method_idx, code_off in dex.encoded_methods():
        refs = dex.references(code_off)
        if not any(needle in value.lower() for _, _, _, value in refs):
            continue
        found += 1
        print(f"\n=== {class_name}->{dex.method_name(method_idx)} ===")
        for pc, op, kind, value in refs:
            marker = "*" if needle in value.lower() else " "
            print(f"{marker} {pc:04x} op={op:02x} {kind:<6} {value}")
    if not found:
        print("no matching method references found")


if __name__ == "__main__":
    main()
