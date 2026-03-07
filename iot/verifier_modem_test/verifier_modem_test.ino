#include <Arduino.h>
#define TINY_GSM_MODEM_SIM7600
#include <TinyGsmClient.h>

HardwareSerial SerialAT(2);
TinyGsm modem(SerialAT);

static const int MODEM_RX_PIN = 26;  // ESP32 RX, connect to modem TX
static const int MODEM_TX_PIN = 27;  // ESP32 TX, connect to modem RX
static const int MODEM_BAUD = 115200;

static const char APN[] = "airtelgprs.com";
static const char APN_USER[] = "";
static const char APN_PASS[] = "";

void send_raw_at(const char *cmd, unsigned long wait_ms = 3000) {
  Serial.print("\n> ");
  Serial.println(cmd);
  SerialAT.print(cmd);
  SerialAT.print("\r");

  const unsigned long start = millis();
  while (millis() - start < wait_ms) {
    while (SerialAT.available()) {
      Serial.write(SerialAT.read());
    }
  }
  Serial.println("\n----");
}

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("TrustSeal Verifier Modem Test");
  Serial.printf("UART pins: RX=%d TX=%d\n", MODEM_RX_PIN, MODEM_TX_PIN);
  Serial.printf("APN: %s\n", APN);

  SerialAT.begin(MODEM_BAUD, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
  delay(500);

  send_raw_at("AT");
  send_raw_at("ATI");
  send_raw_at("AT+CPIN?");
  send_raw_at("AT+CSQ");
  send_raw_at("AT+CREG?");
  send_raw_at("AT+CGREG?");
  send_raw_at("AT+COPS?", 5000);

  Serial.println("TinyGSM restart...");
  const bool restart_ok = modem.restart();
  Serial.printf("modem.restart(): %s\n", restart_ok ? "ok" : "failed");
  if (!restart_ok) {
    return;
  }

  Serial.println("TinyGSM waitForNetwork...");
  const bool network_ok = modem.waitForNetwork(30000);
  Serial.printf("waitForNetwork(): %s\n", network_ok ? "ok" : "failed");
  if (!network_ok) {
    return;
  }

  Serial.println("TinyGSM gprsConnect...");
  const bool gprs_ok = modem.gprsConnect(APN, APN_USER, APN_PASS);
  Serial.printf("gprsConnect(): %s\n", gprs_ok ? "ok" : "failed");
  if (gprs_ok) {
    Serial.printf("operator: %s\n", modem.getOperator().c_str());
    Serial.printf("local ip: %s\n", modem.localIP().c_str());
  }
}

void loop() {
  while (Serial.available()) {
    SerialAT.write(Serial.read());
  }
  while (SerialAT.available()) {
    Serial.write(SerialAT.read());
  }
}
