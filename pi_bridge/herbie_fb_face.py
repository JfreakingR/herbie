#!/usr/bin/env python3
"""BMO-style face on Melba's HDMI framebuffer. Stdlib only. No motors."""

from __future__ import annotations

import math
import mmap
import os
import time
from pathlib import Path

FB_PATH = "/dev/fb0"
SYS = Path("/sys/class/graphics/fb0")
LCD = (0x88, 0xC4, 0xAE)
INK = (0x14, 0x14, 0x14)
HL = (0xFF, 0xFF, 0xFF)


def rgb565(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def read_fb_info() -> tuple[int, int, int]:
    virt = (SYS / "virtual_size").read_text(encoding="ascii").strip()
    w, h = (int(x) for x in virt.split(","))
    bpp = int((SYS / "bits_per_pixel").read_text(encoding="ascii").strip())
    return w, h, bpp


class Face:
    def __init__(self, w: int, h: int, bpp: int, buf: mmap.mmap):
        self.w = w
        self.h = h
        self.bpp = bpp
        self.buf = buf
        self.pitch = w * (2 if bpp <= 16 else 4)
        self.cx = w // 2
        self.cy = int(h * 0.46)
        self.look_x = 0.0
        self.look_y = 0.0
        self.blink = 1.0
        self.smile = 0.72
        self.open = 0.0
        self.tilt = 0.0

    def put(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        if self.bpp <= 16:
            off = y * self.pitch + x * 2
            self.buf[off : off + 2] = rgb565(color).to_bytes(2, "little")
        else:
            off = y * self.pitch + x * 4
            r, g, b = color
            self.buf[off : off + 4] = bytes((b, g, r, 0))

    def fill(self, color: tuple[int, int, int]) -> None:
        if self.bpp <= 16:
            px = rgb565(color).to_bytes(2, "little")
            row = px * self.w
        else:
            r, g, b = color
            row = bytes((b, g, r, 0)) * self.w
        self.buf[:] = row * self.h

    def disk(self, cx: float, cy: float, rx: float, ry: float, color: tuple[int, int, int]) -> None:
        rx_i = max(1, int(rx))
        ry_i = max(1, int(ry))
        x0 = max(0, int(cx) - rx_i)
        x1 = min(self.w - 1, int(cx) + rx_i)
        y0 = max(0, int(cy) - ry_i)
        y1 = min(self.h - 1, int(cy) + ry_i)
        rx2 = float(rx_i * rx_i) or 1.0
        ry2 = float(ry_i * ry_i) or 1.0
        for y in range(y0, y1 + 1):
            dy = (y - cy) * (y - cy) / ry2
            for x in range(x0, x1 + 1):
                dx = (x - cx) * (x - cx) / rx2
                if dx + dy <= 1.0:
                    self.put(x, y, color)

    def mouth(self, cx: float, cy: float, width: float, smile: float, open_: float) -> None:
        half = width / 2
        steps = max(24, int(width))
        thickness = 6 if open_ < 0.12 else 0
        if open_ < 0.12:
            pts = []
            for i in range(steps + 1):
                t = i / steps
                x = cx - half + width * t
                y = cy + smile * 18 * math.sin(math.pi * t)
                pts.append((int(x), int(y)))
            for x, y in pts:
                self.disk(x, y, thickness, thickness, INK)
            return
        rx = width * 0.28 + open_ * 10
        ry = 6 + open_ * 16
        self.disk(cx, cy + 4, rx, ry, INK)

    def draw(self, t: float) -> None:
        self.fill(LCD)
        breath = 1.0 + 0.012 * math.sin(t * 2.2)
        ox = self.cx + int(self.look_x)
        oy = self.cy + int(self.look_y)
        gap = int(self.w * 0.16)
        er = int(36 * breath)
        ey = max(3, int(er * self.blink))
        self.disk(ox - gap, oy, er, ey, INK)
        self.disk(ox + gap, oy, er, ey, INK)
        if self.blink > 0.35:
            self.disk(ox - gap - 8, oy - 8, 9, 9, HL)
            self.disk(ox + gap - 8, oy - 8, 9, 9, HL)
        self.mouth(self.cx, self.cy + int(self.h * 0.18), 120, self.smile, self.open)


def unbind_console() -> None:
    vt = Path("/sys/class/vtconsole")
    if not vt.exists():
        return
    for node in vt.iterdir():
        bind = node / "bind"
        if bind.exists():
            try:
                bind.write_text("0\n", encoding="ascii")
            except OSError:
                pass


def main() -> None:
    if not Path(FB_PATH).exists():
        raise SystemExit("no framebuffer; HDMI is not up")
    w, h, bpp = read_fb_info()
    fd = os.open(FB_PATH, os.O_RDWR)
    size = w * h * (2 if bpp <= 16 else 4)
    buf = mmap.mmap(fd, size, mmap.MAP_SHARED, mmap.PROT_WRITE)
    face = Face(w, h, bpp, buf)
    unbind_console()
    next_blink = time.monotonic() + 1.2
    blinking = 0.0
    look_until = 0.0
    target_x = 0.0
    target_y = 0.0
    try:
        while True:
            now = time.monotonic()
            if blinking > 0:
                face.blink = 0.12
                blinking -= 0.03
            else:
                face.blink = min(1.0, face.blink + 0.2)
                if now >= next_blink:
                    blinking = 0.18
                    next_blink = now + 1.6 + (math.sin(now) * 0.5 + 0.5) * 2.8
            if now >= look_until:
                target_x = math.sin(now * 0.37) * 18
                target_y = math.cos(now * 0.21) * 8
                look_until = now + 1.4 + (now % 1.7)
            face.look_x += (target_x - face.look_x) * 0.08
            face.look_y += (target_y - face.look_y) * 0.08
            face.smile = 0.62 + 0.12 * math.sin(now * 0.4)
            face.draw(now)
            time.sleep(1 / 28)
    finally:
        buf.close()
        os.close(fd)


if __name__ == "__main__":
    main()
