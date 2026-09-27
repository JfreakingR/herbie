/*
 * Pal BLE Wi-Fi provisioner.
 * ESP32 USB only. Do not attach VAVA RX or 3.3V.
 * Pairing uses Just Works (no PIN). Pal has no keypad.
 */

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <BLEClient.h>
#include <BLESecurity.h>
#include <BLERemoteCharacteristic.h>

static const char *TARGET_NAME = "sgg6E5VF9GRNL2E99B7";
static BLEUUID CHAR_HTTP_CP("00002aba-0000-1000-8000-00805f9b34fb");
static BLEUUID DESC_CCCD("00002902-0000-1000-8000-00805f9b34fb");

static BLEAdvertisedDevice *gTarget = nullptr;
static BLEClient *gClient = nullptr;
static BLERemoteCharacteristic *gWriteChar = nullptr;
static bool gDoConnect = false;
static bool gConnected = false;

static String gSsid;
static String gPass;

static bool containsPass(const uint8_t *data, size_t len) {
  size_t plen = gPass.length();
  if (plen == 0 || len < plen) {
    return false;
  }
  const char *p = gPass.c_str();
  for (size_t i = 0; i + plen <= len; i++) {
    if (memcmp(data + i, p, plen) == 0) {
      return true;
    }
  }
  return false;
}

static void printBuf(const char *tag, const uint8_t *data, size_t len) {
  if (containsPass(data, len)) {
    Serial.printf("%s len=%u REDACTED\n", tag, (unsigned)len);
    return;
  }
  Serial.printf("%s len=%u ascii=", tag, (unsigned)len);
  for (size_t i = 0; i < len && i < 80; i++) {
    char c = (char)data[i];
    Serial.print((c >= 32 && c < 127) ? c : '.');
  }
  Serial.print(" hex=");
  for (size_t i = 0; i < len && i < 40; i++) {
    Serial.printf("%02x", data[i]);
  }
  Serial.println();
}

static void onNotify(BLERemoteCharacteristic *c, uint8_t *pData, size_t length, bool isNotify) {
  Serial.printf("NOTIFY %s isNotify=%u ", c->getUUID().toString().c_str(), isNotify);
  printBuf("payload", pData, length);
}

class SecurityCb : public BLESecurityCallbacks {
  uint32_t onPassKeyRequest() override { return 0; }
  void onPassKeyNotify(uint32_t) override {}
  bool onConfirmPIN(uint32_t) override { return true; }
  bool onSecurityRequest() override { return true; }
};

class ClientCb : public BLEClientCallbacks {
  void onConnect(BLEClient *) override { Serial.println("GAP connected."); }
  void onDisconnect(BLEClient *) override {
    gConnected = false;
    Serial.println("Disconnected from Pal.");
  }
};

static ClientCb gClientCb;
static SecurityCb gSecCb;

class AdvertisedCb : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice advertisedDevice) override {
    String name = advertisedDevice.getName().c_str();
    if (name.length() == 0) {
      return;
    }
    if (name.equalsIgnoreCase(TARGET_NAME)) {
      Serial.printf("FOUND %s rssi=%d addr=%s\n", name.c_str(), advertisedDevice.getRSSI(),
                    advertisedDevice.getAddress().toString().c_str());
      BLEDevice::getScan()->stop();
      delete gTarget;
      gTarget = new BLEAdvertisedDevice(advertisedDevice);
      gDoConnect = true;
    }
  }
};

static AdvertisedCb gAdvCb;

static void dumpGatt(BLEClient *client) {
  auto *services = client->getServices();
  if (services == nullptr) {
    Serial.println("No services.");
    return;
  }
  gWriteChar = nullptr;
  for (auto &svc : *services) {
    Serial.printf("SERVICE %s\n", svc.first.c_str());
    auto *chars = svc.second->getCharacteristics();
    if (chars == nullptr) {
      continue;
    }
    for (auto &ch : *chars) {
      BLERemoteCharacteristic *rc = ch.second;
      Serial.printf("  CHAR %s canRead=%u canWrite=%u canNotify=%u\n", ch.first.c_str(), rc->canRead(),
                    rc->canWrite() || rc->canWriteNoResponse(), rc->canNotify());
      if ((rc->canWrite() || rc->canWriteNoResponse()) && gWriteChar == nullptr) {
        gWriteChar = rc;
      }
      if (rc->getUUID().equals(CHAR_HTTP_CP)) {
        gWriteChar = rc;
      }
    }
  }
  if (gWriteChar) {
    Serial.printf("Using write char %s\n", gWriteChar->getUUID().toString().c_str());
  } else {
    Serial.println("No writable characteristic found.");
  }
}

static void enableNotify() {
  if (gWriteChar == nullptr) {
    return;
  }
  if (gWriteChar->canNotify() || gWriteChar->canIndicate()) {
    gWriteChar->registerForNotify(onNotify, gWriteChar->canNotify(), true);
    Serial.println("NOTIFY registerForNotify called.");
    BLERemoteDescriptor *cccd = gWriteChar->getDescriptor(DESC_CCCD);
    if (cccd != nullptr) {
      uint8_t v[2] = {gWriteChar->canNotify() ? (uint8_t)0x01 : (uint8_t)0x02, 0x00};
      bool wok = cccd->writeValue(v, 2, true);
      Serial.printf("CCCD write ok=%u\n", wok);
    }
  }
  if (gWriteChar->canRead()) {
    String v = gWriteChar->readValue();
    printBuf("READ 2ABA", (const uint8_t *)v.c_str(), v.length());
  }
}

static void disconnectPal() {
  gDoConnect = false;
  gConnected = false;
  gWriteChar = nullptr;
  if (gClient != nullptr) {
    gClient->disconnect();
    delay(200);
    delete gClient;
    gClient = nullptr;
  }
  Serial.println("Local disconnect done.");
}

static bool connectToPal() {
  if (gTarget == nullptr) {
    return false;
  }
  gWriteChar = nullptr;
  if (gClient != nullptr) {
    gClient->disconnect();
    delete gClient;
    gClient = nullptr;
  }
  gClient = BLEDevice::createClient();
  gClient->setClientCallbacks(&gClientCb);
  Serial.printf("Connecting to %s ...\n", gTarget->getAddress().toString().c_str());
  if (!gClient->connect(gTarget)) {
    Serial.println("Connect failed.");
    gConnected = false;
    return false;
  }
  Serial.println("Connected. Starting Just Works pairing (no PIN)...");
  BLESecurity::setCapability(ESP_IO_CAP_NONE);
  BLESecurity::setAuthenticationMode(true, false, false);
  BLESecurity::setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  bool sec = gClient->secureConnection();
  Serial.printf("secureConnection ok=%u\n", sec);
  gClient->setMTU(185);
  delay(400);
  dumpGatt(gClient);
  // 2ABA read/CCCD/notify can block forever (same Access Denied Windows hit).
  // Writes still work without them. Use NOTIFY only as a later optional command.
  Serial.println("Skipping 2ABA read/notify (can hang). SEND will write anyway.");
  gConnected = gClient->isConnected();
  return gConnected;
}

static bool writeTry(const char *name, const uint8_t *data, size_t len) {
  if (gWriteChar == nullptr) {
    Serial.println("No writable characteristic.");
    return false;
  }
  Serial.printf("WRITE %s len=%u ...\n", name, (unsigned)len);
  bool ok = gWriteChar->writeValue((uint8_t *)data, len, true);
  Serial.printf("WRITE %s len=%u ok=%u (password not printed)\n", name, (unsigned)len, ok);
  delay(250);
  return ok;
}

static String jsonEscape(const String &value) {
  String escaped;
  escaped.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); ++i) {
    const char ch = value.charAt(i);
    if (ch == '\\' || ch == '"') {
      escaped += '\\';
      escaped += ch;
    } else if (ch == '\n') {
      escaped += "\\n";
    } else if (ch == '\r') {
      escaped += "\\r";
    } else if (ch == '\t') {
      escaped += "\\t";
    } else {
      escaped += ch;
    }
  }
  return escaped;
}

// PAL's factory OperateHandlerProfile2 accepts at most 19 message bytes per
// GATT write. Every non-final chunk carries a trailing 0xAA continuation byte.
static bool writeFactoryMessage(const String &message) {
  const uint8_t *data = reinterpret_cast<const uint8_t *>(message.c_str());
  size_t offset = 0;
  unsigned chunk = 0;
  while (offset < message.length()) {
    const size_t remaining = message.length() - offset;
    const size_t bodyLen = remaining > 19 ? 19 : remaining;
    uint8_t packet[20];
    memcpy(packet, data + offset, bodyLen);
    size_t packetLen = bodyLen;
    if (remaining > 19) {
      packet[packetLen++] = 0xAA;
    }
    char label[32];
    snprintf(label, sizeof(label), "factory-chunk-%u", ++chunk);
    if (!writeTry(label, packet, packetLen)) {
      return false;
    }
    offset += bodyLen;
  }
  return true;
}

static void sendWifi() {
  if (!gConnected || gClient == nullptr || !gClient->isConnected()) {
    Serial.println("Not connected.");
    return;
  }
  if (gSsid.length() == 0) {
    Serial.println("Set SSID=... first.");
    return;
  }
  if (gWriteChar == nullptr) {
    Serial.println("No writable characteristic.");
    return;
  }

  Serial.println("SEND start.");
  String request = "{\"action\":\"setwifi\",\"wifi\":\"" + jsonEscape(gSsid) +
                   "\",\"pass\":\"" + jsonEscape(gPass) + "\",\"sec\":\"1\"}";
  Serial.printf("Factory setwifi request length=%u (credentials not printed).\n", request.length());
  bool ok = writeFactoryMessage(request);
  Serial.printf("SEND factory framing complete ok=%u. Waiting 3s for PAL response/state change...\n", ok);
  delay(3000);
  Serial.println("SEND wait finished.");
}

static void printStatus() {
  bool live = gConnected && gClient != nullptr && gClient->isConnected();
  Serial.printf("STATUS connected=%u ssid_len=%u pass_len=%u write_char=%s\n", live, gSsid.length(), gPass.length(),
                gWriteChar ? gWriteChar->getUUID().toString().c_str() : "none");
}

static void printHelp() {
  Serial.println("Commands:");
  Serial.println("  SCAN");
  Serial.println("  SSID=your2.4ghz-name");
  Serial.println("  PASS=your-password");
  Serial.println("  SEND");
  Serial.println("  STATUS");
  Serial.println("  DISCONNECT");
  Serial.println("Target name: sgg6E5VF9GRNL2E99B7");
  Serial.println("No motor commands. USB power only.");
}

static void startScan() {
  if (gConnected && gClient != nullptr && gClient->isConnected()) {
    Serial.println("Already connected. DISCONNECT first, or SEND.");
    printStatus();
    return;
  }
  BLEScan *scan = BLEDevice::getScan();
  scan->setAdvertisedDeviceCallbacks(&gAdvCb, true);
  scan->setActiveScan(true);
  scan->setInterval(1349);
  scan->setWindow(449);
  Serial.println("Scanning 20s for Pal...");
  scan->start(20, false);
  Serial.println("Scan finished.");
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("Pal BLE Wi-Fi provisioner v2");
  BLEDevice::init("PalSetup");
  BLEDevice::setSecurityCallbacks(&gSecCb);
  BLESecurity::setCapability(ESP_IO_CAP_NONE);
  BLESecurity::setAuthenticationMode(true, false, false);
  printHelp();
}

void loop() {
  if (gDoConnect) {
    gDoConnect = false;
    connectToPal();
  }

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.equalsIgnoreCase("SCAN")) {
      startScan();
    } else if (line.equalsIgnoreCase("DISCONNECT")) {
      disconnectPal();
    } else if (line.equalsIgnoreCase("STATUS")) {
      printStatus();
    } else if (line.startsWith("SSID=") || line.startsWith("ssid=")) {
      gSsid = line.substring(5);
      Serial.printf("SSID set, %u chars.\n", gSsid.length());
    } else if (line.startsWith("PASS=") || line.startsWith("pass=")) {
      gPass = line.substring(5);
      Serial.printf("PASS set, %u chars (not printed).\n", gPass.length());
    } else if (line.equalsIgnoreCase("SEND")) {
      sendWifi();
    } else if (line.equalsIgnoreCase("NOTIFY")) {
      Serial.println("NOTIFY can hang on 2ABA. Not recommended.");
      enableNotify();
    } else if (line.equalsIgnoreCase("HELP")) {
      printHelp();
    }
  }
}
