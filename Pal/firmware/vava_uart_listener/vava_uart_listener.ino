// Pal project: passive VAVA VP-SPR001 UART listener
//
// Wiring (both devices OFF while connecting):
//   VAVA J21 TX  -> ESP32 GPIO23
//   VAVA J21 GND -> ESP32 GND
//
// Do NOT connect VAVA J21 RX or 3.3V during passive capture.

#include <Arduino.h>

HardwareSerial VavaSerial(2);

constexpr int VAVA_RX_PIN = 23;
constexpr int VAVA_TX_UNUSED = -1;

const uint32_t BAUD_RATES[] = {
  115200,
  57600,
  38400,
  19200,
  9600,
  4800,
  2400,
};

constexpr size_t BAUD_COUNT = sizeof(BAUD_RATES) / sizeof(BAUD_RATES[0]);
size_t baudIndex = 0;

void selectBaud(size_t index) {
  if (index >= BAUD_COUNT) {
    return;
  }

  baudIndex = index;
  VavaSerial.end();
  pinMode(VAVA_RX_PIN, INPUT);
  VavaSerial.begin(BAUD_RATES[baudIndex], SERIAL_8N1, VAVA_RX_PIN, VAVA_TX_UNUSED);

  Serial.printf("\nListening on GPIO%d at %lu baud (8N1).\n",
                VAVA_RX_PIN,
                static_cast<unsigned long>(BAUD_RATES[baudIndex]));
  Serial.println("Power-cycle the VAVA now, then watch for byte lines.");
}

void printMenu() {
  Serial.println();
  Serial.println("Passive VAVA UART listener");
  Serial.println("No data is transmitted to the VAVA.");
  Serial.println("Choose a baud rate, then power-cycle the VAVA:");
  for (size_t i = 0; i < BAUD_COUNT; ++i) {
    Serial.printf("  %u = %lu baud\n",
                  static_cast<unsigned>(i + 1),
                  static_cast<unsigned long>(BAUD_RATES[i]));
  }
  Serial.println("  m = show this menu");
}

void setup() {
  pinMode(VAVA_RX_PIN, INPUT);
  Serial.begin(115200);
  delay(1000);
  printMenu();
  selectBaud(0);
}

void loop() {
  while (Serial.available()) {
    const char command = static_cast<char>(Serial.read());
    if (command >= '1' && command <= '7') {
      selectBaud(static_cast<size_t>(command - '1'));
    } else if (command == 'm' || command == 'M' || command == '?') {
      printMenu();
    }
  }

  if (VavaSerial.available()) {
    Serial.printf("%10lu ms |", static_cast<unsigned long>(millis()));

    char ascii[17];
    size_t count = 0;
    const uint32_t start = millis();

    while (count < 16 && (millis() - start) < 30) {
      if (!VavaSerial.available()) {
        continue;
      }

      const uint8_t value = static_cast<uint8_t>(VavaSerial.read());
      Serial.printf(" %02X", value);
      ascii[count] = (value >= 32 && value <= 126) ? static_cast<char>(value) : '.';
      ++count;
    }

    ascii[count] = '\0';
    for (size_t i = count; i < 16; ++i) {
      Serial.print("   ");
    }
    Serial.printf(" | %s\n", ascii);
  }
}
