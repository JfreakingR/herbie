"""Recover JNA Structure field ORDER from a DEX.

The DEX field table is sorted alphabetically, which is useless for a wire
format. JNA keeps the real declaration order in each Structure's
`getFieldOrder()`, which returns a list of field-name strings. Those appear as
`const-string` instructions in the method body, in order — so walking the
bytecode and collecting them yields the exact struct layout.

Usage:
    python dexfieldorder.py classes.dex TermSegoPacket
"""

import struct
import sys

# Instruction size in 16-bit code units, built from the DEX opcode ranges.
# Generated rather than hand-typed: a single wrong entry desynchronises the
# whole walk, which is exactly what happened on the first attempt.
def _build_sizes():
    s = [1] * 256
    two = ([0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1A, 0x1C, 0x1F, 0x20,
            0x22, 0x23, 0x29]
           + list(range(0x2D, 0x3E))      # cmp*, if-*, if-*z
           + list(range(0x44, 0x6E))      # aget/aput, iget/iput, sget/sput
           + list(range(0x90, 0xB0))      # binop
           + list(range(0xD0, 0xE3)))     # binop/lit16, binop/lit8
    three = ([0x03, 0x06, 0x09, 0x14, 0x17, 0x1B, 0x24, 0x25, 0x26, 0x2A,
              0x2B, 0x2C]
             + list(range(0x6E, 0x73))    # invoke-*
             + list(range(0x74, 0x79)))   # invoke-*/range
    five = [0x18]
    for op in two:
        s[op] = 2
    for op in three:
        s[op] = 3
    for op in five:
        s[op] = 5
    return s


SIZES = _build_sizes()


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

    def method_name(self, idx):
        _, _, name_idx = struct.unpack_from("<HHI", self.d, self.method_off + idx * 8)
        return self.string(name_idx)

    def strings_in_method(self, code_off):
        """Walk the bytecode, collecting const-string operands in order."""
        if code_off == 0:
            return []
        insns_size, = struct.unpack_from("<I", self.d, code_off + 12)
        base = code_off + 16
        out, pc = [], 0
        while pc < insns_size:
            unit, = struct.unpack_from("<H", self.d, base + pc * 2)
            op = unit & 0xFF
            if op == 0x1A:      # const-string vAA, string@BBBB
                idx, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                if idx < self.str_size:
                    out.append(self.string(idx))
            elif op == 0x1B:    # const-string/jumbo
                idx, = struct.unpack_from("<I", self.d, base + (pc + 1) * 2)
                if idx < self.str_size:
                    out.append(self.string(idx))
            size = SIZES[op]
            # Payload pseudo-instructions carry their own length.
            if op == 0x00 and unit != 0:
                kind = unit >> 8
                if kind == 1:      # packed-switch
                    n, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                    size = n * 2 + 4
                elif kind == 2:    # sparse-switch
                    n, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                    size = n * 4 + 2
                elif kind == 3:    # fill-array-data
                    w, = struct.unpack_from("<H", self.d, base + (pc + 1) * 2)
                    n, = struct.unpack_from("<I", self.d, base + (pc + 2) * 2)
                    size = (n * w + 1) // 2 + 4
            pc += max(size, 1)
        return out

    def field_orders(self, needle):
        results = {}
        for i in range(self.cls_size):
            off = self.cls_off + i * 32
            class_idx, = struct.unpack_from("<I", self.d, off)
            name = self.type_name(class_idx)
            if needle not in name:
                continue
            class_data_off, = struct.unpack_from("<I", self.d, off + 24)
            if class_data_off == 0:
                continue
            p = class_data_off
            sf, p = uleb128(self.d, p)
            inf, p = uleb128(self.d, p)
            dm, p = uleb128(self.d, p)
            vm, p = uleb128(self.d, p)
            for count in (sf, inf):          # skip encoded fields
                idx = 0
                for _ in range(count):
                    diff, p = uleb128(self.d, p)
                    _, p = uleb128(self.d, p)
                    idx += diff
            for count in (dm, vm):
                idx = 0
                for _ in range(count):
                    diff, p = uleb128(self.d, p)
                    _, p = uleb128(self.d, p)      # access flags
                    code_off, p = uleb128(self.d, p)
                    idx += diff
                    if self.method_name(idx) == "getFieldOrder":
                        order = self.strings_in_method(code_off)
                        if order:
                            results[name] = order
        return results


def main():
    dex = Dex(sys.argv[1])
    needle = sys.argv[2] if len(sys.argv) > 2 else "TermSegoPacket"
    orders = dex.field_orders(needle)
    if not orders:
        print("no getFieldOrder methods found")
        return
    for cls in sorted(orders):
        pretty = cls[1:-1].replace("/", ".").split(".")[-1]
        print(f"\n=== {pretty} ===")
        for n, field in enumerate(orders[cls]):
            print(f"  {n}. {field}")


if __name__ == "__main__":
    main()
