"""Minimal Dalvik disassembler for protocol archaeology.

Prints constants, strings, new-array, field access, invokes, and branches
(if-*, goto, packed/sparse-switch) for every method whose full name contains
one of the needles. Read-only. Companion to dexrefs.py / dexfieldorder.py.

The dex tools take a raw classes.dex, NOT the .apk. Extract it first:

    python -c "import zipfile; zipfile.ZipFile('software/sego-factory-apks/ctl.apk').extract('classes.dex', 'ctl_dex')"
    python tools/dexdis.py ctl_dex/classes.dex 'Terminal;->transferToSerialStr'

This is what recovered the servo movement path on 2026-09-16.
"""
import struct, sys
from dexrefs import ReferenceDex
from dexfieldorder import SIZES

dex = ReferenceDex(sys.argv[1])
needles = sys.argv[2:]

def dis(code_off):
    insns_size, = struct.unpack_from("<I", dex.d, code_off + 12)
    base = code_off + 16
    words = struct.unpack_from("<%dH" % insns_size, dex.d, base)
    pc = 0
    out = []
    while pc < insns_size:
        w = words[pc]; op = w & 0xFF
        a = (w >> 8)
        if op == 0x00 and a in (1, 2, 3):   # payload tables
            if a == 3:
                width, = struct.unpack_from("<H", dex.d, base + (pc+1)*2)
                n, = struct.unpack_from("<I", dex.d, base + (pc+2)*2)
                data = dex.d[base+(pc+4)*2: base+(pc+4)*2 + width*n]
                out.append(f"  {pc:04x} array-data w={width} n={n} {data.hex(' ')}")
                pc += 4 + (width*n + 1)//2
                continue
            n = words[pc+1]
            pc += (2 + n*2) if a == 1 else (2 + n*4)
            continue
        s = SIZES[op] or 1
        if op == 0x12:
            lit = (a >> 4); lit = lit - 16 if lit > 7 else lit
            out.append(f"  {pc:04x} const/4 v{a & 0xF} = {lit}")
        elif op == 0x13:
            lit, = struct.unpack("<h", struct.pack("<H", words[pc+1]))
            out.append(f"  {pc:04x} const/16 v{a} = {lit}")
        elif op == 0x14:
            lit, = struct.unpack("<i", struct.pack("<HH", words[pc+1], words[pc+2]))
            out.append(f"  {pc:04x} const v{a} = {lit}")
        elif 0x32 <= op <= 0x37:
            names={0x32:'if-eq',0x33:'if-ne',0x34:'if-lt',0x35:'if-ge',0x36:'if-gt',0x37:'if-le'}
            off,=struct.unpack("<h",struct.pack("<H",words[pc+1]))
            out.append(f"  {pc:04x} {names[op]} v{a & 0xF}, v{a >> 4} -> {pc+off:04x}")
        elif 0x38 <= op <= 0x3d:
            names={0x38:'if-eqz',0x39:'if-nez',0x3a:'if-ltz',0x3b:'if-gez',0x3c:'if-gtz',0x3d:'if-lez'}
            off,=struct.unpack("<h",struct.pack("<H",words[pc+1]))
            out.append(f"  {pc:04x} {names[op]} v{a} -> {pc+off:04x}")
        elif op in (0x28,0x29,0x2a):
            if op==0x28: off=a-256 if a>127 else a
            elif op==0x29: off,=struct.unpack("<h",struct.pack("<H",words[pc+1]))
            else: off,=struct.unpack("<i",struct.pack("<HH",words[pc+1],words[pc+2]))
            out.append(f"  {pc:04x} goto -> {pc+off:04x}")
        elif op in (0x2b,0x2c):
            toff,=struct.unpack("<i",struct.pack("<HH",words[pc+1],words[pc+2]))
            t=pc+toff; ident=words[t]; size=words[t+1]
            if op==0x2b:
                first,=struct.unpack("<i",struct.pack("<HH",words[t+2],words[t+3]))
                tg=[struct.unpack("<i",struct.pack("<HH",words[t+4+2*i],words[t+5+2*i]))[0] for i in range(size)]
                out.append(f"  {pc:04x} packed-switch v{a} " + ", ".join(f"{first+i}->{pc+x:04x}" for i,x in enumerate(tg)))
            else:
                keys=[struct.unpack("<i",struct.pack("<HH",words[t+2+2*i],words[t+3+2*i]))[0] for i in range(size)]
                tg=[struct.unpack("<i",struct.pack("<HH",words[t+2+2*size+2*i],words[t+3+2*size+2*i]))[0] for i in range(size)]
                out.append(f"  {pc:04x} sparse-switch v{a} " + ", ".join(f"{k:#x}->{pc+x:04x}" for k,x in zip(keys,tg)))
        elif op == 0x21:
            out.append(f"  {pc:04x} array-length v{a & 0xF} = len(v{a >> 4})")
        elif op in (0x46,0x47,0x48,0x49,0x4a,0x4b,0x4c,0x4d):
            out.append(f"  {pc:04x} aget/aput op={op:02x}")
        elif op == 0x1a:
            out.append(f"  {pc:04x} const-string v{a} = {dex.string(words[pc+1])!r}")
        elif op == 0x23:
            out.append(f"  {pc:04x} new-array v{a & 0xF} size=v{a >> 4} type={dex.type_name(words[pc+1])}")
        elif op == 0x26:
            out.append(f"  {pc:04x} fill-array-data")
        elif 0x52 <= op <= 0x6D:
            out.append(f"  {pc:04x} field op={op:02x} {dex.field_name(words[pc+1])}")
        elif 0x6E <= op <= 0x72 or 0x74 <= op <= 0x78:
            out.append(f"  {pc:04x} invoke {dex.method_full_name(words[pc+1])}")
        elif op in (0x22, 0x1c, 0x1f, 0x20):
            out.append(f"  {pc:04x} type-op {op:02x} {dex.type_name(words[pc+1])}")
        elif 0xd8 <= op <= 0xe2 or 0xb0 <= op <= 0xcf or 0x90 <= op <= 0xaf:
            out.append(f"  {pc:04x} arith op={op:02x}")
        elif op in (0x11, 0x0e, 0x0f, 0x10):
            out.append(f"  {pc:04x} return")
        pc += s
    return out

for cls, midx, code_off in dex.encoded_methods():
    full = dex.method_full_name(midx)
    if code_off and any(n in full for n in needles):
        print(f"=== {full} ===")
        print("\n".join(dis(code_off)))
