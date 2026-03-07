#include <Arduino.h>
#define TINY_GSM_MODEM_A7672X
#include <TinyGsmClient.h>
#include <ArduinoHttpClient.h>

HardwareSerial SerialAT(1);
TinyGsm modem(SerialAT);
TinyGsmClientSecure client(modem);

static const int MODEM_RX_PIN = 16;
static const int MODEM_TX_PIN = 17;
static const int MODEM_BAUD = 115200;

static const char APN[] = "jionet";
static const char APN_USER[] = "";
static const char APN_PASS[] = "";

static const char HOST[] = "trustsealbridge.onrender.com";
static const int PORT = 443;
static const char PATH[] = "/health";

bool syncTimeFromModem() {
  modem.sendAT("+CNTP=\"pool.ntp.org\",0");
  modem.waitResponse(3000L);

  modem.sendAT("+CNTP");
  modem.waitResponse(15000L);

  while (SerialAT.available()) {
    SerialAT.read();
  }

  SerialAT.print("AT+CCLK?\r");

  String raw;
  unsigned long start = millis();
  while (millis() - start < 2500) {
    while (SerialAT.available()) {
      raw += char(SerialAT.read());
    }
  }

  Serial.print("CCLK raw: ");
  Serial.println(raw);

  int q1 = raw.indexOf('"');
  int q2 = raw.indexOf('"', q1 + 1);
  if (q1 < 0 || q2 < 0) return false;

  String s = raw.substring(q1 + 1, q2);  // "26/03/06,23:45:15+22"
  if (s.length() < 17) return false;

  int yy = s.substring(0, 2).toInt();
  int mo = s.substring(3, 5).toInt();
  int dd = s.substring(6, 8).toInt();
  int hh = s.substring(9, 11).toInt();
  int mm = s.substring(12, 14).toInt();
  int ss = s.substring(15, 17).toInt();

  struct tm t = {};
  t.tm_year = (2000 + yy) - 1900;
  t.tm_mon = mo - 1;
  t.tm_mday = dd;
  t.tm_hour = hh;
  t.tm_min = mm;
  t.tm_sec = ss;

  time_t epoch = mktime(&t);
  if (epoch < 1700000000) return false;

  struct timeval tv = {
    .tv_sec = epoch,
    .tv_usec = 0
  };
  settimeofday(&tv, nullptr);
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("HTTPS test starting");

  SerialAT.begin(MODEM_BAUD, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
  delay(500);

  bool modemOk = modem.restart();
  Serial.printf("modem.restart(): %s\n", modemOk ? "ok" : "failed");
  if (!modemOk) return;

  bool netOk = modem.waitForNetwork(30000);
  Serial.printf("waitForNetwork(): %s\n", netOk ? "ok" : "failed");
  if (!netOk) return;

  bool gprsOk = modem.gprsConnect(APN, APN_USER, APN_PASS);
  Serial.printf("gprsConnect(): %s\n", gprsOk ? "ok" : "failed");
  if (!gprsOk) return;

  bool timeOk = syncTimeFromModem();
  Serial.printf("time sync: %s\n", timeOk ? "ok" : "failed");

  HttpClient http(client, HOST, PORT);
  http.setHttpResponseTimeout(15000);

  Serial.println("Sending HTTPS GET /health");
  http.get(PATH);

  int status = http.responseStatusCode();
  String body = http.responseBody();

  Serial.printf("HTTPS status: %d\n", status);
  Serial.println("HTTPS body:");
  Serial.println(body);

  http.stop();
}

void loop() {
}
