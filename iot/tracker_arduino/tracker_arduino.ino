#include <Arduino.h>
#include <Wire.h>
#include <time.h>
#include <Adafruit_BME280.h>
#include <Adafruit_ADXL345_U.h>
#include <ArduinoJson.h>
#include <FS.h>
#include <SPIFFS.h>
#include <deque>
#define TINY_GSM_MODEM_SIM7600
#include <TinyGsmClient.h>
#include <ArduinoHttpClient.h>

#include <mbedtls/base64.h>
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/entropy.h>
#include <mbedtls/md.h>
#include <mbedtls/pk.h>

#include "tracker_config.h"
#include "tracker_secrets.h"

enum class SendResult {
  Acked,
  RetryLater,
  DropPermanent,
};

struct SensorSnapshot {
  float temperature_c;
  float humidity_pct;
  float shock_g;
  float light_lux;
  float tilt_deg;
  float battery_pct;
  bool has_bme;
  bool has_adxl;
};

Adafruit_BME280 bme280;
Adafruit_ADXL345_Unified adxl345(12345);
HardwareSerial SerialAT(1);
TinyGsm modem(SerialAT);
TinyGsmClient modem_client(modem);

bool bme_ok = false;
bool adxl_ok = false;
bool spiffs_ok = false;
bool signer_ok = false;
bool modem_ready = false;

uint32_t seq_no = 0;
unsigned long last_sample_ms = 0;
unsigned long last_send_ms = 0;
unsigned long last_modem_attempt_ms = 0;
unsigned long next_retry_after_ms = 0;
unsigned long retry_backoff_ms = TELEMETRY_RETRY_BASE_MS;

mbedtls_pk_context signer_key;
mbedtls_entropy_context signer_entropy;
mbedtls_ctr_drbg_context signer_ctr_drbg;

float ldr_adc_to_lux(const int adc_value) {
  const float normalized = static_cast<float>(adc_value) / LDR_ADC_MAX;
  return normalized * LDR_LUX_SCALE;
}

String bytes_to_hex(const uint8_t *bytes, const size_t len) {
  static const char *hex = "0123456789abcdef";
  String out;
  out.reserve(len * 2);
  for (size_t i = 0; i < len; i++) {
    out += hex[(bytes[i] >> 4) & 0x0F];
    out += hex[bytes[i] & 0x0F];
  }
  return out;
}

String next_event_id(const uint32_t event_seq) {
  const uint64_t chip = ESP.getEfuseMac();
  char buffer[64];
  snprintf(
    buffer,
    sizeof(buffer),
    "%08lx-%04x-%04x-%04x-%012llx",
    static_cast<unsigned long>(chip >> 32),
    static_cast<unsigned int>((event_seq >> 16) & 0xFFFF),
    static_cast<unsigned int>(event_seq & 0xFFFF),
    static_cast<unsigned int>(millis() & 0xFFFF),
    static_cast<unsigned long long>(chip & 0xFFFFFFFFFFFFULL)
  );
  return String(buffer);
}

String current_ts_iso_utc() {
  const time_t now = time(nullptr);
  if (now < 1700000000) {
    return "1970-01-01T00:00:00Z";
  }
  struct tm utc_tm;
  gmtime_r(&now, &utc_tm);
  char ts[32];
  strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &utc_tm);
  return String(ts);
}

bool sync_time_from_modem() {
  Serial.println("Time sync: configuring CNTP");
  modem.sendAT("+CNTP=\"pool.ntp.org\",0");
  const int resp1 = modem.waitResponse(3000L);
  Serial.printf("CNTP config resp: %d\n", resp1);

  Serial.println("Time sync: triggering CNTP");
  modem.sendAT("+CNTP");
  const int resp2 = modem.waitResponse(15000L);
  Serial.printf("CNTP trigger resp: %d\n", resp2);

  Serial.println("Time sync: reading CCLK");
  while (SerialAT.available()) {
    SerialAT.read();
  }
  SerialAT.print("AT+CCLK?\r");
  String raw;
  const unsigned long start = millis();
  while (millis() - start < 2500) {
    while (SerialAT.available()) {
      raw += static_cast<char>(SerialAT.read());
    }
  }
  Serial.print("CCLK raw: ");
  Serial.println(raw);
  if (raw.indexOf("OK") < 0) {
    return false;
  }

  const int q1 = raw.indexOf('"');
  const int q2 = raw.indexOf('"', q1 + 1);
  if (q1 < 0 || q2 < 0) {
    return false;
  }

  const String modem_ts = raw.substring(q1 + 1, q2);
  if (modem_ts.length() < 17) {
    return false;
  }

  const int yy = modem_ts.substring(0, 2).toInt();
  const int mo = modem_ts.substring(3, 5).toInt();
  const int dd = modem_ts.substring(6, 8).toInt();
  const int hh = modem_ts.substring(9, 11).toInt();
  const int mm = modem_ts.substring(12, 14).toInt();
  const int ss = modem_ts.substring(15, 17).toInt();

  struct tm t = {};
  t.tm_year = (2000 + yy) - 1900;
  t.tm_mon = mo - 1;
  t.tm_mday = dd;
  t.tm_hour = hh;
  t.tm_min = mm;
  t.tm_sec = ss;

  const time_t epoch = mktime(&t);
  if (epoch < 1700000000) {
    return false;
  }

  const struct timeval tv = {
    .tv_sec = epoch,
    .tv_usec = 0,
  };
  settimeofday(&tv, nullptr);
  return true;
}

void init_i2c() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
}

void init_storage() {
  spiffs_ok = SPIFFS.begin(true);
}

void init_signer() {
  mbedtls_pk_init(&signer_key);
  mbedtls_entropy_init(&signer_entropy);
  mbedtls_ctr_drbg_init(&signer_ctr_drbg);

  const char *personalization = "trustseal-tracker";
  int rc = mbedtls_ctr_drbg_seed(
    &signer_ctr_drbg,
    mbedtls_entropy_func,
    &signer_entropy,
    reinterpret_cast<const unsigned char *>(personalization),
    strlen(personalization)
  );
  if (rc != 0) {
    signer_ok = false;
    return;
  }

  rc = mbedtls_pk_parse_key(
    &signer_key,
    reinterpret_cast<const unsigned char *>(TRACKER_PRIVATE_KEY_PEM),
    strlen(TRACKER_PRIVATE_KEY_PEM) + 1,
    nullptr,
    0,
    mbedtls_ctr_drbg_random,
    &signer_ctr_drbg
  );
  signer_ok = (rc == 0);
}

void init_sensors() {
  bme_ok = bme280.begin(0x76) || bme280.begin(0x77);
  adxl_ok = adxl345.begin();
  if (adxl_ok) {
    adxl345.setRange(ADXL345_RANGE_16_G);
  }
}

void init_modem() {
  SerialAT.begin(MODEM_BAUD, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
  delay(300);
  modem_ready = modem.restart();
  if (!modem_ready) {
    return;
  }
  modem_ready = modem.waitForNetwork(30000);
  if (!modem_ready) {
    return;
  }
  modem_ready = modem.gprsConnect(MODEM_APN, MODEM_APN_USER, MODEM_APN_PASS);
}

void ensure_modem_connected() {
  if (!modem_ready) {
    const unsigned long now = millis();
    if (now - last_modem_attempt_ms < 10000) {
      return;
    }
    last_modem_attempt_ms = now;
    init_modem();
    return;
  }
  if (!modem.isNetworkConnected()) {
    modem_ready = false;
    return;
  }
  if (!modem.isGprsConnected()) {
    modem_ready = modem.gprsConnect(MODEM_APN, MODEM_APN_USER, MODEM_APN_PASS);
  }
}

void print_boot_status() {
  Serial.println("TrustSeal Tracker Sensor+Sign+Send Boot");
  Serial.printf("BME280: %s\n", bme_ok ? "ok" : "not_found");
  Serial.printf("ADXL345: %s\n", adxl_ok ? "ok" : "not_found");
  Serial.printf("SPIFFS: %s\n", spiffs_ok ? "ok" : "failed");
  Serial.printf("ECDSA signer: %s\n", signer_ok ? "ok" : "failed");
  Serial.printf("Modem network: %s\n", modem_ready ? "connected" : "not_connected");
  Serial.printf("APN: %s\n", MODEM_APN);
  Serial.printf(
    "API: %s://%s:%d%s\n",
    TRACKER_API_USE_TLS ? "https" : "http",
    TRACKER_API_HOST,
    TRACKER_API_PORT,
    TRACKER_API_PATH
  );
}

std::deque<String> read_queue_lines() {
  std::deque<String> lines;
  if (!spiffs_ok || !SPIFFS.exists(TELEMETRY_QUEUE_FILE)) {
    return lines;
  }
  File file = SPIFFS.open(TELEMETRY_QUEUE_FILE, FILE_READ);
  if (!file) {
    return lines;
  }
  while (file.available()) {
    String line = file.readStringUntil('\n');
    line.trim();
    if (line.length() > 2) {
      lines.push_back(line);
    }
  }
  file.close();
  return lines;
}

bool rewrite_queue_lines(const std::deque<String> &lines) {
  if (!spiffs_ok) {
    return false;
  }
  File file = SPIFFS.open(TELEMETRY_QUEUE_FILE, FILE_WRITE);
  if (!file) {
    return false;
  }
  for (const auto &line : lines) {
    file.println(line);
  }
  file.close();
  return true;
}

size_t queue_depth() {
  return read_queue_lines().size();
}

void trim_queue_to_limit() {
  std::deque<String> lines = read_queue_lines();
  while (lines.size() > TELEMETRY_QUEUE_MAX_ENTRIES) {
    lines.pop_front();
  }
  rewrite_queue_lines(lines);
}

bool queue_packet(const String &packet_json) {
  if (!spiffs_ok) {
    return false;
  }
  File file = SPIFFS.open(TELEMETRY_QUEUE_FILE, FILE_APPEND);
  if (!file) {
    file = SPIFFS.open(TELEMETRY_QUEUE_FILE, FILE_WRITE);
  }
  if (!file) {
    return false;
  }
  file.println(packet_json);
  file.close();
  trim_queue_to_limit();
  return true;
}

bool pop_queue_head() {
  std::deque<String> lines = read_queue_lines();
  if (lines.empty()) {
    return false;
  }
  lines.pop_front();
  return rewrite_queue_lines(lines);
}

bool peek_queue_head(String &line_out) {
  std::deque<String> lines = read_queue_lines();
  if (lines.empty()) {
    return false;
  }
  line_out = lines.front();
  return true;
}

SensorSnapshot sample_sensors() {
  SensorSnapshot s {};
  s.has_bme = bme_ok;
  s.has_adxl = adxl_ok;
  s.battery_pct = 100.0f;
  s.tilt_deg = 0.0f;

  if (bme_ok) {
    s.temperature_c = bme280.readTemperature();
    s.humidity_pct = bme280.readHumidity();
  }

  if (adxl_ok) {
    sensors_event_t event;
    adxl345.getEvent(&event);
    s.shock_g = sqrtf(
      (event.acceleration.x * event.acceleration.x) +
      (event.acceleration.y * event.acceleration.y) +
      (event.acceleration.z * event.acceleration.z)
    ) / 9.80665f;
    s.tilt_deg = atan2f(event.acceleration.x, event.acceleration.z) * (180.0f / PI);
  }

  s.light_lux = ldr_adc_to_lux(analogRead(LDR_PIN));
  return s;
}

String build_canonical_payload_json(
  const String &event_id,
  const String &ts,
  const uint32_t seq,
  const SensorSnapshot &s
) {
  StaticJsonDocument<1024> canonical;
  canonical["battery_pct"] = s.battery_pct;
  canonical["device_id"] = TRACKER_DEVICE_ID;
  canonical["device_uid"] = TRACKER_DEVICE_UID;
  canonical["event_id"] = event_id;
  canonical["firmware_version"] = TRACKER_FIRMWARE_VERSION;
  canonical["gps"] = nullptr;
  canonical["idempotency_key"] = event_id;
  canonical["light_lux"] = s.light_lux;
  canonical["network_type"] = "cellular";
  canonical["pubkey_id"] = TRACKER_PUBKEY_ID;
  canonical["seq_no"] = seq;
  canonical["shipment_id"] = TRACKER_SHIPMENT_ID;
  canonical["sig_alg"] = "ecdsa-secp256r1";
  canonical["ts"] = ts;
  if (s.has_bme) {
    canonical["humidity_pct"] = s.humidity_pct;
    canonical["temperature_c"] = s.temperature_c;
  } else {
    canonical["humidity_pct"] = nullptr;
    canonical["temperature_c"] = nullptr;
  }
  if (s.has_adxl) {
    canonical["shock_g"] = s.shock_g;
    canonical["tilt_deg"] = s.tilt_deg;
  } else {
    canonical["shock_g"] = nullptr;
    canonical["tilt_deg"] = nullptr;
  }

  String out;
  serializeJson(canonical, out);
  return out;
}

bool sign_payload(const String &canonical_payload, String &payload_hash_hex, String &signature_base64) {
  if (!signer_ok) {
    return false;
  }

  uint8_t hash_bytes[32];
  const auto *md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (md == nullptr) {
    return false;
  }

  const int hash_rc = mbedtls_md(
    md,
    reinterpret_cast<const unsigned char *>(canonical_payload.c_str()),
    canonical_payload.length(),
    hash_bytes
  );
  if (hash_rc != 0) {
    return false;
  }
  payload_hash_hex = bytes_to_hex(hash_bytes, sizeof(hash_bytes));

  unsigned char signature[128];
  size_t signature_len = 0;
  const int sign_rc = mbedtls_pk_sign(
    &signer_key,
    MBEDTLS_MD_SHA256,
    hash_bytes,
    sizeof(hash_bytes),
    signature,
    sizeof(signature),
    &signature_len,
    mbedtls_ctr_drbg_random,
    &signer_ctr_drbg
  );
  if (sign_rc != 0) {
    return false;
  }

  unsigned char signature_b64[257];
  size_t b64_len = 0;
  const int b64_rc = mbedtls_base64_encode(
    signature_b64,
    sizeof(signature_b64) - 1,
    &b64_len,
    signature,
    signature_len
  );
  if (b64_rc != 0) {
    return false;
  }
  signature_b64[b64_len] = '\0';
  signature_base64 = String(reinterpret_cast<char *>(signature_b64));
  return true;
}

void enqueue_telemetry_packet() {
  const uint32_t current_seq = ++seq_no;
  const String event_id = next_event_id(current_seq);
  const String ts = current_ts_iso_utc();
  const SensorSnapshot snapshot = sample_sensors();

  const String canonical = build_canonical_payload_json(event_id, ts, current_seq, snapshot);
  String payload_hash_hex;
  String signature_b64;
  const bool signed_ok = sign_payload(canonical, payload_hash_hex, signature_b64);

  StaticJsonDocument<1024> packet;
  packet["event_id"] = event_id;
  packet["shipment_id"] = TRACKER_SHIPMENT_ID;
  packet["device_id"] = TRACKER_DEVICE_ID;
  packet["device_uid"] = TRACKER_DEVICE_UID;
  packet["ts"] = ts;
  packet["seq_no"] = current_seq;
  packet["light_lux"] = snapshot.light_lux;
  packet["gps"] = nullptr;
  packet["battery_pct"] = snapshot.battery_pct;
  packet["network_type"] = "cellular";
  packet["firmware_version"] = TRACKER_FIRMWARE_VERSION;
  packet["hash_alg"] = "sha256";
  packet["payload_hash"] = payload_hash_hex;
  packet["sig_alg"] = "ecdsa-secp256r1";
  packet["signature"] = signature_b64;
  packet["pubkey_id"] = TRACKER_PUBKEY_ID;
  packet["idempotency_key"] = event_id;
  if (snapshot.has_bme) {
    packet["temperature_c"] = snapshot.temperature_c;
    packet["humidity_pct"] = snapshot.humidity_pct;
  } else {
    packet["temperature_c"] = nullptr;
    packet["humidity_pct"] = nullptr;
  }
  if (snapshot.has_adxl) {
    packet["shock_g"] = snapshot.shock_g;
    packet["tilt_deg"] = snapshot.tilt_deg;
  } else {
    packet["shock_g"] = nullptr;
    packet["tilt_deg"] = nullptr;
  }

  String packet_json;
  serializeJson(packet, packet_json);
  const bool buffered = signed_ok && queue_packet(packet_json);

  StaticJsonDocument<256> log_doc;
  log_doc["event_id"] = event_id;
  log_doc["signed"] = signed_ok;
  log_doc["buffered"] = buffered;
  log_doc["queue_depth"] = static_cast<uint32_t>(queue_depth());
  log_doc["ts"] = ts;
  serializeJson(log_doc, Serial);
  Serial.println();
}

SendResult post_queued_packet(const String &packet_json) {
  if (!modem_ready || !modem.isGprsConnected()) {
    Serial.println("send: modem unavailable");
    return SendResult::RetryLater;
  }

  HttpClient http(modem_client, TRACKER_API_HOST, TRACKER_API_PORT);
  http.setHttpResponseTimeout(8000);

  http.beginRequest();
  http.post(TRACKER_API_PATH);
  http.sendHeader("Content-Type", "application/json");
  if (strlen(TRACKER_API_BEARER_TOKEN) > 0) {
    http.sendHeader("X-Device-Id", TRACKER_DEVICE_ID);
    http.sendHeader("X-Device-Token", TRACKER_API_BEARER_TOKEN);
  }
  http.sendHeader("Content-Length", packet_json.length());
  http.beginBody();
  http.print(packet_json);
  http.endRequest();

  const int status_code = http.responseStatusCode();
  const String response_body = http.responseBody();
  http.stop();

  Serial.printf("send: status=%d\n", status_code);
  if (response_body.length() > 0) {
    Serial.print("send: body=");
    Serial.println(response_body);
  }

  if (status_code == 409) {
    return SendResult::Acked;
  }

  if (status_code == 202) {
    StaticJsonDocument<512> resp;
    if (deserializeJson(resp, response_body) == DeserializationError::Ok) {
      const bool success = resp["success"] | false;
      const bool accepted = resp["data"]["accepted"] | false;
      if (success && accepted) {
        return SendResult::Acked;
      }
    }
    return SendResult::RetryLater;
  }

  if (status_code == 400 || status_code == 401 || status_code == 403 || status_code == 422) {
    return SendResult::DropPermanent;
  }

  return SendResult::RetryLater;
}

void process_send_once() {
  String packet_json;
  if (!peek_queue_head(packet_json)) {
    return;
  }

  const SendResult result = post_queued_packet(packet_json);
  if (result == SendResult::Acked) {
    pop_queue_head();
    retry_backoff_ms = TELEMETRY_RETRY_BASE_MS;
    next_retry_after_ms = 0;
    Serial.printf("send: acked queue_depth=%u\n", static_cast<unsigned>(queue_depth()));
  } else if (result == SendResult::DropPermanent) {
    pop_queue_head();
    Serial.printf("send: dropped queue_depth=%u\n", static_cast<unsigned>(queue_depth()));
  } else {
    next_retry_after_ms = millis() + retry_backoff_ms;
    retry_backoff_ms = min(retry_backoff_ms * 2, static_cast<unsigned long>(TELEMETRY_RETRY_MAX_MS));
    Serial.printf(
      "send: retry_later next_retry_ms=%lu queue_depth=%u\n",
      retry_backoff_ms,
      static_cast<unsigned>(queue_depth())
    );
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  analogReadResolution(12);
  pinMode(LDR_PIN, INPUT);

  init_i2c();
  init_storage();
  init_sensors();
  init_signer();
  init_modem();
  if (modem_ready) {
    const bool time_ok = sync_time_from_modem();
    Serial.printf("Time sync: %s\n", time_ok ? "ok" : "failed");
  }
  print_boot_status();
}

void loop() {
  const unsigned long now = millis();
  ensure_modem_connected();

  if (now - last_sample_ms >= TELEMETRY_SAMPLE_INTERVAL_MS) {
    last_sample_ms = now;
    enqueue_telemetry_packet();
  }

  if (now - last_send_ms >= TELEMETRY_SEND_INTERVAL_MS) {
    last_send_ms = now;
    if (next_retry_after_ms == 0 || now >= next_retry_after_ms) {
      process_send_once();
    }
  }
}
