#include <Arduino.h>

HardwareSerial SerialAT(1);

void sendCommand(const char *cmd, unsigned long waitMs = 2000) {
  Serial.print("\n> ");
  Serial.println(cmd);
  SerialAT.print(cmd);
  SerialAT.print("\r");

  unsigned long start = millis();
  while (millis() - start < waitMs) {
    while (SerialAT.available()) {
      Serial.write(SerialAT.read());
    }
  }
  Serial.println("\n----");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("A7670C auto-test starting");
  SerialAT.begin(115200, SERIAL_8N1, 26, 27);
  delay(2000);

  sendCommand("AT");
  sendCommand("ATI");
  sendCommand("AT+CPIN?");
  sendCommand("AT+CSQ");
  sendCommand("AT+CREG?");
  sendCommand("AT+CGREG?");
  sendCommand("AT+COPS?", 5000);
}

void loop() {
}
