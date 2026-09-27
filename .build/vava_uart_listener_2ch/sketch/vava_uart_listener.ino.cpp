#line 1 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_listener\\vava_uart_listener.ino"
// Herbie project: passive two-channel VAVA VP-SPR001 UART listener
//
// Wiring (both devices OFF while connecting):
//   VAVA J21 TX  -> ESP32 GPIO34 (replies from the STM32)
//   VAVA J21 RX  -> ESP32 GPIO35 (commands to the STM32)
//   VAVA J21 GND -> ESP32 GND
//
// GPIO34 and GPIO35 are input-only on the classic ESP32, so this sketch cannot
// drive either VAVA signal. Do NOT connect VAVA J21 3.3V or any ESP32 TX pin.

#include <Arduino.h>

HardwareSerial J21TxSerial(1);
HardwareSerial J21RxSerial(2);

constexpr int J21_TX_LISTEN_PIN = 34;
constexpr int J21_RX_LISTEN_PIN = 35;
constexpr int NO_TX_PIN = -1;

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

#line 33 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_listener\\vava_uart_listener.ino"
void selectBaud(size_t index);
#line 55 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_listener\\vava_uart_listener.ino"
void printMenu();
#line 68 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_listener\\vava_uart_listener.ino"
void setup();
#line 77 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_listener\\vava_uart_listener.ino"
void loop();
#line 91 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_listener\\vava_uart_listener.ino"
void captureAvailable(HardwareSerial &source, const char *direction);
#line 33 "C:\\Users\\Phyllis\\Desktop\\Herbie\\firmware\\vava_uart_listener\\vava_uart_listener.ino"
void selectBaud(size_t index) {
  if (index >= BAUD_COUNT) {
    return;
  }

  baudIndex = index;
  J21TxSerial.end();
  J21RxSerial.end();
  pinMode(J21_TX_LISTEN_PIN, INPUT);
  pinMode(J21_RX_LISTEN_PIN, INPUT);
  J21TxSerial.begin(BAUD_RATES[baudIndex], SERIAL_8N1,
                    J21_TX_LISTEN_PIN, NO_TX_PIN);
  J21RxSerial.begin(BAUD_RATES[baudIndex], SERIAL_8N1,
                    J21_RX_LISTEN_PIN, NO_TX_PIN);

  Serial.printf("\nListening on GPIO%d (J21 TX) and GPIO%d (J21 RX) at %lu baud (8N1).\n",
                J21_TX_LISTEN_PIN,
                J21_RX_LISTEN_PIN,
                static_cast<unsigned long>(BAUD_RATES[baudIndex]));
  Serial.println("Power-cycle the VAVA now, then watch for byte lines.");
}

void printMenu() {
  Serial.println();
  Serial.println("Passive two-channel VAVA UART listener");
  Serial.println("GPIO34 and GPIO35 are input-only; no data can be transmitted to the VAVA.");
  Serial.println("Choose a baud rate, then power-cycle the VAVA:");
  for (size_t i = 0; i < BAUD_COUNT; ++i) {
    Serial.printf("  %u = %lu baud\n",
                  static_cast<unsigned>(i + 1),
                  static_cast<unsigned long>(BAUD_RATES[i]));
  }
  Serial.println("  m = show this menu");
}

void setup() {
  pinMode(J21_TX_LISTEN_PIN, INPUT);
  pinMode(J21_RX_LISTEN_PIN, INPUT);
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

  captureAvailable(J21TxSerial, "J21_TX_REPLY");
  captureAvailable(J21RxSerial, "J21_RX_COMMAND");
}

void captureAvailable(HardwareSerial &source, const char *direction) {
  if (source.available()) {
    Serial.printf("%10lu ms |", static_cast<unsigned long>(millis()));

    char ascii[17];
    size_t count = 0;
    const uint32_t start = millis();

    while (count < 16 && (millis() - start) < 30) {
      if (!source.available()) {
        continue;
      }

      const uint8_t value = static_cast<uint8_t>(source.read());
      Serial.printf(" %02X", value);
      ascii[count] = (value >= 32 && value <= 126) ? static_cast<char>(value) : '.';
      ++count;
    }

    ascii[count] = '\0';
    for (size_t i = count; i < 16; ++i) {
      Serial.print("   ");
    }
    Serial.printf(" | %s | %s\n", ascii, direction);
  }
}

