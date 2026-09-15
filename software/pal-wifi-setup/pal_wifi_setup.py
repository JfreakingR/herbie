#!/usr/bin/env python3
"""Pal Wi-Fi setup helper.

Live Bluetooth LE + classic discovery, GATT dump, optional 2.4 GHz credential send.
Does not command motors, treats, or the laser.
Does not save the Wi-Fi password to disk.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
import queue
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.characteristic import BleakGATTCharacteristic
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "bleak is not installed. Run Start Pal Wifi Setup.cmd once so the venv is created."
    ) from exc

try:
    from winrt.windows.devices.enumeration import (
        DeviceInformation,
        DevicePairingKinds,
        DevicePairingProtectionLevel,
        DevicePairingResultStatus,
    )
    from winrt.windows.devices.bluetooth import BluetoothLEDevice
except Exception:  # pragma: no cover
    DeviceInformation = None
    DevicePairingKinds = None
    DevicePairingProtectionLevel = None
    DevicePairingResultStatus = None
    BluetoothLEDevice = None

APP_DIR = Path(__file__).resolve().parent
DUMP_PATH = APP_DIR / "last-gatt-dump.txt"
LOG_PATH = APP_DIR / "last-session.log"

# Phone Bluetooth screen 2026-09-07: Pal advertised as this TUTK UID.
# Android system pairing failed ("Couldn't pair") — that is expected.
PAL_TUTK_UID = "sgg6E5VF9GRNL2E99B7"

LIKELY_NAME_BITS = (
    "vava",
    "pal",
    "pet",
    "tutk",
    "kalay",
    "sg_802",
    "sg802",
    "cam",
    "setup",
    "config",
    "spr",
    "ipc",
    "sgg6",
    PAL_TUTK_UID.lower(),
)

LIKELY_UUID_BITS = (
    "wifi",
    "ssid",
    "pass",
    "prov",
    "config",
    "setup",
    "net",
)

WRITE_PROPS = frozenset({"write", "write-without-response"})

TUTK_LAN_PORTS = (32761, 49182, 32108, 12315)
TUTK_PROBES = (
    bytes([0x01, 0x01, 0x04, 0x03, 0x02, 0x01, 0x00]),
    bytes([0x01, 0x01, 0x04, 0x03, 0x03, 0x00, 0x00, 0x01]),
    b"\x00\x00\x00\x01",
    b"\x04\x02\x1a\x02",
)


def redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "********")
    return text


def is_likely_name(name: str) -> bool:
    lowered = (name or "").lower()
    return any(bit in lowered for bit in LIKELY_NAME_BITS)


def is_likely_uuid(uuid: str) -> bool:
    lowered = (uuid or "").lower()
    return any(bit in lowered for bit in LIKELY_UUID_BITS)


def char_can_write(char: BleakGATTCharacteristic) -> bool:
    props = {p.lower() for p in (char.properties or [])}
    return bool(props & WRITE_PROPS)


def build_payloads(ssid: str, password: str) -> list[tuple[str, bytes]]:
    s = ssid.encode("utf-8")
    p = password.encode("utf-8")
    return [
        ("json ssid/password", json.dumps({"ssid": ssid, "password": password}).encode("utf-8")),
        ("json wifi_ssid/wifi_password", json.dumps({"wifi_ssid": ssid, "wifi_password": password}).encode("utf-8")),
        ("newline ssid\\npassword", s + b"\n" + p),
        ("nul ssid\\0password", s + b"\x00" + p),
        ("len-prefixed", bytes([len(s)]) + s + bytes([len(p)]) + p),
        ("ssid only", s),
        ("password only", p),
    ]


class AsyncWorker:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


class PalWifiSetupApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Pal Wi-Fi Setup")
        self.root.geometry("1000x760")
        self.worker = AsyncWorker()
        self.ui_queue: queue.Queue = queue.Queue()
        self.devices: dict[str, dict] = {}
        self.writable: list[tuple[str, str]] = []
        self.client: BleakClient | None = None
        self.connected_address: str | None = None
        self.scanning = False
        self.scan_stop = asyncio.Event()
        self.ble_scanner: BleakScanner | None = None

        self.filter_likely = tk.BooleanVar(value=False)
        self.ssid_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.format_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Motors locked off. This app only does Wi-Fi setup.")

        self._build()
        self.root.after(100, self._drain_ui)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log("Pal Wi-Fi Setup. No motor, treat, or laser commands.")
        self.log("Use live scan with Pal next to this PC, within 5 minutes of 'waiting for network config'.")
        self.log("Look for BLE sgg6E5VF9GRNL2E99B7. Do not connect Echo-CNX.")
        self.log("If writes stay Access Denied, pair Pal in Windows Bluetooth settings first.")

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Start live scan", command=self.start_scan).pack(side="left")
        ttk.Button(top, text="Stop scan", command=self.stop_scan).pack(side="left", padx=4)
        ttk.Checkbutton(top, text="Only Pal/VAVA-like names", variable=self.filter_likely).pack(side="left", padx=8)
        ttk.Button(top, text="Connect + dump GATT", command=self.connect_dump).pack(side="left")
        ttk.Button(top, text="Disconnect", command=self.disconnect).pack(side="left", padx=8)
        ttk.Button(top, text="Search LAN for TUTK", command=self.lan_search).pack(side="left")
        ttk.Button(top, text="Open Windows Bluetooth", command=self.open_windows_bluetooth).pack(side="left", padx=8)

        mid = ttk.Frame(self.root, padding=(8, 0))
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Devices (stay in the list once seen)").pack(anchor="w")
        self.device_list = tk.Listbox(left, height=12)
        self.device_list.pack(fill="both", expand=True)

        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(right, text="Writable BLE characteristics").pack(anchor="w")
        self.char_list = tk.Listbox(right, height=12, selectmode="extended")
        self.char_list.pack(fill="both", expand=True)

        cred = ttk.LabelFrame(self.root, text="2.4 GHz Wi-Fi credentials (kept in memory only)", padding=8)
        cred.pack(fill="x", padx=8, pady=8)
        ttk.Label(cred, text="SSID").grid(row=0, column=0, sticky="w")
        ttk.Entry(cred, textvariable=self.ssid_var, width=40).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Label(cred, text="Password").grid(row=1, column=0, sticky="w")
        ttk.Entry(cred, textvariable=self.password_var, width=40, show="*").grid(row=1, column=1, sticky="we", padx=6)
        ttk.Label(cred, text="Payload").grid(row=0, column=2, sticky="w")
        formats = [name for name, _ in build_payloads("x", "y")]
        self.format_var.set(formats[0])
        ttk.Combobox(cred, textvariable=self.format_var, values=formats, width=32, state="readonly").grid(
            row=0, column=3, padx=6
        )
        ttk.Button(cred, text="Send Wi-Fi to Pal", command=self.send_wifi).grid(row=1, column=3, sticky="e", padx=6)
        cred.columnconfigure(1, weight=1)

        ttk.Label(self.root, textvariable=self.status_var).pack(anchor="w", padx=8)
        self.log_box = tk.Text(self.root, height=16, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        note = (
            "Phone Bluetooth settings seeing Pal is not the same as sending Wi-Fi. "
            "Live-scan with Pal touching this PC. Watch the Wi-Fi LED. "
            "If pairing fails, press Pal's power button once — not an 8-second reset."
        )
        ttk.Label(self.root, text=note, wraplength=960).pack(anchor="w", padx=8, pady=(0, 8))

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"{stamp}  {message}"
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        secret = self.password_var.get()
        safe = redact(line, secret)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(safe + "\n")

    def _drain_ui(self) -> None:
        while True:
            try:
                kind, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log(payload)
            elif kind == "status":
                self.status_var.set(payload)
            elif kind == "device":
                self._upsert_device(payload)
            elif kind == "writable":
                self._set_writable(payload)
            elif kind == "error":
                messagebox.showerror("Pal Wi-Fi Setup", payload)
        self.root.after(100, self._drain_ui)

    def ui(self, kind: str, payload) -> None:
        self.ui_queue.put((kind, payload))

    def _upsert_device(self, rec: dict) -> None:
        key = rec["key"]
        likely = bool(self.filter_likely.get())
        if likely and not is_likely_name(rec.get("name") or ""):
            return
        self.devices[key] = rec
        rows = sorted(
            self.devices.values(),
            key=lambda r: (
                0 if PAL_TUTK_UID.lower() in (r.get("name") or "").lower() else 1,
                0 if is_likely_name(r.get("name") or "") else 1,
                r.get("label") or "",
            ),
        )
        selected = None
        sel = self.device_list.curselection()
        if sel:
            selected = self.device_list.get(sel[0])
        self.device_list.delete(0, "end")
        for row in rows:
            self.device_list.insert("end", row["label"])
        if selected:
            for idx, row in enumerate(rows):
                if row["label"] == selected:
                    self.device_list.selection_set(idx)
                    break

    def _set_writable(self, rows: list[tuple[str, str]]) -> None:
        self.char_list.delete(0, "end")
        self.writable = rows
        for _uuid, label in rows:
            self.char_list.insert("end", label)

    def selected_device(self) -> dict | None:
        sel = self.device_list.curselection()
        if not sel:
            return None
        label = self.device_list.get(sel[0])
        for rec in self.devices.values():
            if rec.get("label") == label:
                return rec
        return None

    def start_scan(self) -> None:
        if self.scanning:
            self.log("Live scan already running.")
            return
        self.scanning = True
        self.scan_stop = asyncio.Event()
        self.status_var.set("Live scan running. Power Pal now and keep it next to this PC.")
        self.log("Starting live BLE + classic Bluetooth scan. Devices stay in the list.")
        self.worker.submit(self._live_scan())

    def stop_scan(self) -> None:
        self.scanning = False
        self.worker.loop.call_soon_threadsafe(self.scan_stop.set)
        self.status_var.set("Scan stopping...")
        self.log("Stop requested.")

    async def _live_scan(self) -> None:
        seen_log: set[str] = set()

        def on_ble(device, adv) -> None:
            name = device.name or adv.local_name or "(no name)"
            rssi = adv.rssi if adv.rssi is not None else "?"
            uuids = ",".join(adv.service_uuids or [])
            key = f"ble:{device.address}"
            label = f"BLE  {name}  [{device.address}]  RSSI {rssi}"
            rec = {
                "key": key,
                "kind": "ble",
                "name": name,
                "address": device.address,
                "rssi": adv.rssi,
                "label": label,
                "ble_device": device,
            }
            self.ui("device", rec)
            if key not in seen_log:
                seen_log.add(key)
                extra = f" services={uuids}" if uuids else ""
                self.ui("log", f"Saw {label}{extra}")

        scanner = BleakScanner(detection_callback=on_ble)
        self.ble_scanner = scanner
        classic_watcher = None
        try:
            await scanner.start()
            if DeviceInformation is not None:
                classic_watcher = DeviceInformation.create_watcher()

                def added(_w, info) -> None:
                    blob = f"{info.name} {info.id}"
                    low = blob.lower()
                    if "bluetooth" not in low and "bth" not in low and "{e0cbf06c" not in low:
                        return
                    name = info.name or "(no name)"
                    key = f"classic:{info.id}"
                    label = f"CLASSIC  {name}  [{info.id[-24:]}]"
                    rec = {
                        "key": key,
                        "kind": "classic",
                        "name": name,
                        "address": info.id,
                        "label": label,
                        "ble_device": None,
                    }
                    self.ui("device", rec)
                    if key not in seen_log:
                        seen_log.add(key)
                        self.ui("log", f"Saw {label}")

                classic_watcher.add_added(added)
                classic_watcher.start()
            self.ui("status", "Listening. Put Pal against this PC.")
            while self.scanning and not self.scan_stop.is_set():
                try:
                    await asyncio.wait_for(self.scan_stop.wait(), timeout=1.0)
                except TimeoutError:
                    pass
        except Exception as exc:
            self.ui("error", f"Scan failed: {exc}")
            self.ui("status", "Scan failed.")
        finally:
            try:
                await scanner.stop()
            except Exception:
                pass
            self.ble_scanner = None
            if classic_watcher is not None:
                try:
                    classic_watcher.stop()
                except Exception:
                    pass
            self.scanning = False
            n = len(self.devices)
            self.ui("log", f"Live scan stopped. {n} device(s) remembered.")
            self.ui("status", f"Scan stopped. {n} device(s) in the list.")

    def connect_dump(self) -> None:
        rec = self.selected_device()
        if rec is None:
            messagebox.showinfo("Pal Wi-Fi Setup", "Select a device first.")
            return
        if rec.get("kind") != "ble" or rec.get("ble_device") is None:
            messagebox.showinfo(
                "Pal Wi-Fi Setup",
                "That entry is classic Bluetooth. GATT/Wi-Fi send only works on a BLE row.\n"
                "Look for BLE  sgg6E5VF9GRNL2E99B7 — not Echo-CNX.",
            )
            self.log(f"Skipped classic device {rec.get('name')}. Need a BLE row named {PAL_TUTK_UID}.")
            return
        name = rec.get("name") or ""
        rssi = rec.get("rssi")
        if PAL_TUTK_UID.lower() not in name.lower():
            if not messagebox.askyesno(
                "Pal Wi-Fi Setup",
                f"This BLE name is {name!r}, not Pal's ID {PAL_TUTK_UID}.\n"
                "Weak unnamed devices are usually not Pal.\nConnect anyway?",
            ):
                self.log(f"User skipped BLE {name} [{rec.get('address')}]")
                return
        if isinstance(rssi, int) and rssi <= -90:
            self.log(f"Warning: RSSI {rssi} is very weak. Move Pal next to the PC.")
        self.status_var.set(f"Stopping scan, then connecting to {rec['address']}...")
        self.log(f"Connect requested: {name} [{rec['address']}] RSSI {rssi}")
        self.worker.submit(self._connect_dump(rec))

    async def _stop_scan_for_connect(self) -> None:
        self.scanning = False
        try:
            self.scan_stop.set()
        except Exception:
            pass
        scanner = self.ble_scanner
        self.ble_scanner = None
        if scanner is not None:
            try:
                await scanner.stop()
                self.ui("log", "Stopped live scan so Windows can connect.")
            except Exception as exc:
                self.ui("log", f"Scan stop: {exc}")
        await asyncio.sleep(0.8)

    def _on_pairing_requested(self, _sender, args) -> None:
        pin = ""
        try:
            pin = args.pin or ""
        except Exception:
            pin = ""
        self.ui("log", f"Windows pairing request kind={args.pairing_kind} pin={pin!r}")
        try:
            args.accept()
            self.ui("log", "Accepted pairing request.")
            return
        except Exception as exc:
            self.ui("log", f"accept() failed: {exc}")
        for guess in ("0000", "1234", "8888"):
            try:
                args.accept_with_pin(guess)
                self.ui("log", f"Accepted pairing with PIN {guess}.")
                return
            except Exception:
                continue

    async def _try_windows_pair(self, address: str) -> None:
        if BluetoothLEDevice is None or DevicePairingKinds is None:
            return
        try:
            addr_int = int(str(address).replace(":", ""), 16)
            le = await BluetoothLEDevice.from_bluetooth_address_async(addr_int)
        except Exception as exc:
            self.ui("log", f"Pair lookup failed: {exc}")
            return
        if le is None:
            self.ui("log", "Windows has no BLE handle yet; will try a plain connect.")
            return
        pairing = le.device_information.pairing
        self.ui("log", f"Windows pairing: can_pair={pairing.can_pair} is_paired={pairing.is_paired}")
        if pairing.is_paired:
            self.ui("log", "Keeping existing Windows bond. Not unpairing.")
            return
        # Pal has no screen/keypad. DISPLAY_PIN / PROVIDE_PIN makes Windows
        # ask for a 6-digit code on Pal, which cannot work.
        kinds = DevicePairingKinds.CONFIRM_ONLY
        custom = pairing.custom
        token = custom.add_pairing_requested(self._on_pairing_requested)
        try:
            self.ui("log", "Custom pairing. If Windows asks, click Connect.")
            result = None
            for args in (
                (kinds, DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION),
                (kinds, DevicePairingProtectionLevel.ENCRYPTION),
                (kinds,),
            ):
                try:
                    result = await custom.pair_async(*args)
                    break
                except TypeError:
                    continue
            if result is None:
                self.ui("log", "custom.pair_async signature mismatch.")
                return
            self.ui("log", f"Custom pair result: {result.status}")
        except Exception as exc:
            self.ui("log", f"Custom pair failed: {exc}")
        finally:
            try:
                custom.remove_pairing_requested(token)
            except Exception:
                pass

    def open_windows_bluetooth(self) -> None:
        try:
            os.startfile("ms-settings:bluetooth")
            self.log("Opened Windows Bluetooth settings. Add device → Bluetooth → sgg6E5VF9GRNL2E99B7. Then Connect in this app.")
        except Exception as exc:
            self.log(f"Could not open Windows Bluetooth settings: {exc}")

    async def _open_client(self, address: str) -> BleakClient:
        client = BleakClient(address)
        await client.connect(timeout=20.0)
        return client

    async def _pair_on_connection(self, client: BleakClient, address: str) -> None:
        if hasattr(client, "pair"):
            try:
                ok = await client.pair()
                self.ui("log", f"bleak.pair() -> {ok}")
            except Exception as exc:
                self.ui("log", f"bleak.pair() failed: {exc}")
        await self._try_windows_pair(address)

    async def _dump_gatt(self, client: BleakClient, rec: dict, address: str) -> None:
        self.ui("log", f"Connected to {address}. Discovering GATT...")
        lines = [
            f"Pal Wi-Fi Setup GATT dump {datetime.now().isoformat(timespec='seconds')}",
            f"Address: {address}",
            f"Name: {rec.get('name')}",
            "",
        ]
        writable: list[tuple[str, str]] = []
        services = client.services
        for service in services:
            lines.append(f"SERVICE {service.uuid}  {service.description}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                lines.append(f"  CHAR {char.uuid}  {char.description}  [{props}]")
                if char_can_write(char):
                    mark = " likely" if is_likely_uuid(char.uuid + char.description) else ""
                    label = f"{char.uuid}  {char.description}  [{props}]{mark}"
                    writable.append((char.uuid, label))
                for desc in char.descriptors:
                    lines.append(f"    DESC {desc.uuid} handle={getattr(desc, 'handle', '?')}")
        DUMP_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.writable = writable
        self.ui("writable", writable)
        self.ui("log", f"GATT dump saved to {DUMP_PATH.name}. {len(writable)} writable characteristic(s).")
        try:
            raw_name = await client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
            self.ui("log", f"Device Name characteristic: {raw_name!r}")
        except Exception as exc:
            self.ui("log", f"Could not read Device Name: {exc}")
        try:
            raw_ctrl = await client.read_gatt_char("00002aba-0000-1000-8000-00805f9b34fb")
            self.ui("log", f"HTTP Control Point read: {bytes(raw_ctrl).hex(' ')}")
        except Exception as exc:
            self.ui("log", f"HTTP Control Point read failed: {exc}")

    async def _connect_dump(self, rec: dict) -> None:
        await self._stop_scan_for_connect()
        await self._disconnect_silent()
        address = rec.get("address")
        client = None
        try:
            self.ui("log", f"First connect to {address}...")
            client = await self._open_client(address)
        except Exception as exc:
            self.ui("error", f"Connect failed: {exc}\nPut Pal against this PC.")
            self.ui("status", "Connect failed.")
            return
        await self._pair_on_connection(client, address)
        try:
            await client.disconnect()
        except Exception:
            pass
        self.ui("log", "Reconnecting after pairing so Windows can encrypt writes...")
        await asyncio.sleep(1.2)
        try:
            client = await self._open_client(address)
        except Exception as exc:
            self.ui("error", f"Reconnect failed: {exc}")
            self.ui("status", "Reconnect failed.")
            return
        self.client = client
        self.connected_address = address
        try:
            await self._dump_gatt(client, rec, address)
        except Exception as exc:
            self.ui("error", f"GATT discovery failed: {exc}")
            return
        self.ui("status", "Connected after pairing. Select HTTP Control Point, then Send.")

    def send_wifi(self) -> None:
        ssid = self.ssid_var.get().strip()
        password = self.password_var.get()
        if not ssid:
            messagebox.showinfo("Pal Wi-Fi Setup", "Enter the 2.4 GHz SSID.")
            return
        if self.client is None or not self.connected_address:
            messagebox.showinfo("Pal Wi-Fi Setup", "Connect to a BLE Pal row first.")
            return
        selected = self.char_list.curselection()
        if not selected:
            if len(self.writable) == 1:
                selected = (0,)
            else:
                messagebox.showinfo("Pal Wi-Fi Setup", "Select one writable characteristic (or two: SSID then password).")
                return
        uuids = [self.writable[i][0] for i in selected]
        fmt = self.format_var.get()
        self.status_var.set("Sending Wi-Fi credentials over BLE...")
        self.worker.submit(self._send_wifi(ssid, password, uuids, fmt))

    async def _send_wifi(self, ssid: str, password: str, uuids: list[str], fmt: str) -> None:
        client = self.client
        if client is None:
            self.ui("error", "Not connected.")
            return

        def notify(_sender, data: bytearray) -> None:
            self.ui("log", f"Notify {len(data)} bytes: {bytes(data).hex(' ')}")

        uuid = uuids[0]
        try:
            for service in client.services:
                for char in service.characteristics:
                    if char.uuid.lower() != uuid.lower():
                        continue
                    for desc in char.descriptors:
                        if "2902" in desc.uuid.lower():
                            handle = getattr(desc, "handle", None)
                            if handle is not None:
                                await client.write_gatt_descriptor(handle, b"\x01\x00")
                                self.ui("log", f"Enabled notify CCCD handle {handle}")
        except Exception as exc:
            self.ui("log", f"CCCD write failed: {redact(str(exc), password)}")
        try:
            await client.start_notify(uuid, notify)
            self.ui("log", f"Subscribed to notifies on {uuid}")
        except Exception as exc:
            self.ui("log", f"Notify subscribe failed: {redact(str(exc), password)}")

        payloads = dict(build_payloads(ssid, password))
        # HTTP Control Point is a 1-byte opcode in the Bluetooth spec; Pal may still
        # treat 2ABA as a vendor Wi-Fi pipe. Try both.
        ordered = [
            ("len-prefixed", payloads["len-prefixed"]),
            ("nul ssid\\0password", payloads["nul ssid\\0password"]),
            ("newline ssid\\npassword", payloads["newline ssid\\npassword"]),
            (fmt, payloads.get(fmt) or payloads["json ssid/password"]),
            ("http GET opcode", bytes([0x01])),
            ("http POST opcode", bytes([0x03])),
        ]
        wrote = 0
        last_error = None
        for name, data in ordered:
            for response in (True, False):
                try:
                    await client.write_gatt_char(uuid, data, response=response)
                    wrote += 1
                    self.ui("log", f"Wrote {name} ({len(data)} bytes, response={response}). Password not logged.")
                except Exception as exc:
                    err = str(exc)
                    if "Access Denied" in err:
                        last_error = "Access Denied"
                    else:
                        last_error = redact(err, password)
                    self.ui("log", f"{name} response={response} failed: {last_error}")
        if wrote == 0:
            self.ui("error", f"Write failed: {last_error}\nMove Pal against the PC (RSSI was very weak).")
            self.ui("status", "Write failed.")
            return
        self.ui("status", f"Sent {wrote} payload(s). Watch Pal's Wi-Fi LED, then Search LAN for TUTK.")
        self.ui("log", "Send finished. Password was not written to the log.")

    def lan_search(self) -> None:
        self.status_var.set("Broadcasting TUTK-style LAN search...")
        self.worker.submit(self._lan_search())

    async def _lan_search(self) -> None:
        replies: list[str] = []

        def probe() -> None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.4)
            try:
                for port in TUTK_LAN_PORTS:
                    for packet in TUTK_PROBES:
                        try:
                            sock.sendto(packet, ("255.255.255.255", port))
                        except OSError:
                            continue
                deadline = datetime.now().timestamp() + 3.0
                while datetime.now().timestamp() < deadline:
                    try:
                        data, addr = sock.recvfrom(2048)
                    except TimeoutError:
                        continue
                    except OSError:
                        break
                    preview = data[:80].hex(" ")
                    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in data[:80])
                    replies.append(f"{addr[0]}:{addr[1]}  hex={preview}  ascii={ascii_part}")
            finally:
                sock.close()

        await asyncio.to_thread(probe)
        if not replies:
            self.ui("log", "No LAN replies on TUTK ports. Pal may still be joining Wi-Fi, or the cloud/P2P service is silent.")
            self.ui("status", "No TUTK LAN reply yet. Check the Wi-Fi LED and router DHCP list.")
            return
        self.ui("log", f"LAN replies ({len(replies)}):")
        for row in replies:
            self.ui("log", "  " + row)
        self.ui("status", f"LAN search got {len(replies)} reply/replies. Pal may be on the network.")

    def disconnect(self) -> None:
        self.worker.submit(self._disconnect_silent())
        self.status_var.set("Disconnected.")
        self.log("Disconnected.")

    async def _disconnect_silent(self) -> None:
        client = self.client
        self.client = None
        self.connected_address = None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    def on_close(self) -> None:
        self.scanning = False
        try:
            self.worker.loop.call_soon_threadsafe(self.scan_stop.set)
        except Exception:
            pass
        self.worker.submit(self._disconnect_silent())
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    PalWifiSetupApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
