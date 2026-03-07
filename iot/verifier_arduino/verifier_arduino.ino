#include <Arduino.h>
#include <time.h>
#include <ArduinoJson.h>
#include <Adafruit_Fingerprint.h>
#include <HardwareSerial.h>
#include <FS.h>
#include <SPIFFS.h>
#include <deque>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

#include <mbedtls/base64.h>
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/entropy.h>
#include <mbedtls/md.h>
#include <mbedtls/pk.h>

#include "verifier_config.h"
#include "verifier_secrets.h"

enum class SendResult {
  Acked,
  RetryLater,
  DropPermanent,
};

HardwareSerial SerialFP(1);
Adafruit_Fingerprint finger(&SerialFP);
WiFiClient wifi_client;
WiFiClientSecure wifi_secure_client;

bool fingerprint_ok = false;
bool signer_ok = false;
bool spiffs_ok = false;
bool wifi_ready = false;
uint32_t custody_seq = 0;
unsigned long last_scan_ms = 0;
unsigned long last_send_ms = 0;
unsigned long last_wifi_attempt_ms = 0;
unsigned long next_retry_after_ms = 0;
unsigned long retry_backoff_ms = CUSTODY_RETRY_BASE_MS;
String serial_command_buffer;

mbedtls_pk_context signer_key;
mbedtls_entropy_context signer_entropy;
mbedtls_ctr_drbg_context signer_ctr_drbg;

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

String now_iso_utc() {
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

String next_custody_event_id(const uint32_t seq) {
  const uint64_t chip = ESP.getEfuseMac();
  char buffer[64];
  snprintf(
    buffer,
    sizeof(buffer),
    "%08lx-%04x-%04x-%04x-%012llx",
    static_cast<unsigned long>(chip >> 32),
    static_cast<unsigned int>((seq >> 16) & 0xFFFF),
    static_cast<unsigned int>(seq & 0xFFFF),
    static_cast<unsigned int>(millis() & 0xFFFF),
    static_cast<unsigned long long>(chip & 0xFFFFFFFFFFFFULL)
  );
  return String(buffer);
}

void init_signer() {
  mbedtls_pk_init(&signer_key);
  mbedtls_entropy_init(&signer_entropy);
  mbedtls_ctr_drbg_init(&signer_ctr_drbg);

  const char *personalization = "trustseal-verifier";
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
    reinterpret_cast<const unsigned char *>(VERIFIER_PRIVATE_KEY_PEM),
    strlen(VERIFIER_PRIVATE_KEY_PEM) + 1,
    nullptr,
    0,
    mbedtls_ctr_drbg_random,
    &signer_ctr_drbg
  );
  signer_ok = (rc == 0);
}

String sha256_hex(const String &payload) {
  uint8_t hash_bytes[32];
  const auto *md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (md == nullptr) {
    return "";
  }
  const int hash_rc = mbedtls_md(
    md,
    reinterpret_cast<const unsigned char *>(payload.c_str()),
    payload.length(),
    hash_bytes
  );
  if (hash_rc != 0) {
    return "";
  }
  return bytes_to_hex(hash_bytes, sizeof(hash_bytes));
}

String json_escape_string(const String &input) {
  String out;
  out.reserve(input.length() + 8);
  for (size_t i = 0; i < input.length(); i++) {
    const char c = input[i];
    switch (c) {
      case '\\': out += "\\\\"; break;
      case '"': out += "\\\""; break;
      case '\b': out += "\\b"; break;
      case '\f': out += "\\f"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default: out += c; break;
    }
  }
  return out;
}

String build_custody_approval_canonical_json(
  const String &event_id,
  const String &ts,
  const char *fingerprint_result,
  const int confidence,
  const int template_id
) {
  String json = "{";
  json += "\"custody_event_id\":\"" + json_escape_string(event_id) + "\",";
  json += "\"digital_signer_address\":\"" + String(VERIFIER_SIGNER_ADDRESS) + "\",";
  json += "\"fingerprint_result\":\"" + String(fingerprint_result) + "\",";
  if (confidence >= 0) {
    char score_buf[16];
    snprintf(score_buf, sizeof(score_buf), "%.1f", static_cast<float>(confidence));
    json += "\"fingerprint_score\":" + String(score_buf) + ",";
  } else {
    json += "\"fingerprint_score\":null,";
  }
  if (template_id >= 0) {
    json += "\"fingerprint_template_id\":\"" + String(template_id) + "\",";
  } else {
    json += "\"fingerprint_template_id\":null,";
  }
  json += "\"idempotency_key\":\"" + json_escape_string(event_id) + "\",";
  json += "\"leg_id\":\"" + String(VERIFIER_LEG_ID) + "\",";
  json += "\"shipment_id\":\"" + String(VERIFIER_SHIPMENT_ID) + "\",";
  json += "\"sig_alg\":\"ecdsa-secp256r1\",";
  json += "\"ts\":\"" + json_escape_string(ts) + "\",";
  json += "\"verifier_device_id\":\"" + String(VERIFIER_DEVICE_ID) + "\",";
  json += "\"verifier_user_id\":\"" + String(VERIFIER_USER_ID) + "\"";
  json += "}";
  return json;
}

bool sign_hash_hex(const String &hash_hex, String &signature_b64) {
  if (!signer_ok || hash_hex.length() != 64) {
    return false;
  }

  auto hex_nibble = [](const char c) -> int {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
    if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
    return -1;
  };

  uint8_t hash_bytes[32];
  for (size_t i = 0; i < 32; i++) {
    const int h = hex_nibble(hash_hex[i * 2]);
    const int l = hex_nibble(hash_hex[i * 2 + 1]);
    if (h < 0 || l < 0) {
      return false;
    }
    hash_bytes[i] = static_cast<uint8_t>((h << 4) | l);
  }

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

  unsigned char signature_b64_buf[257];
  size_t b64_len = 0;
  const int b64_rc = mbedtls_base64_encode(
    signature_b64_buf,
    sizeof(signature_b64_buf) - 1,
    &b64_len,
    signature,
    signature_len
  );
  if (b64_rc != 0) {
    return false;
  }
  signature_b64_buf[b64_len] = '\0';
  signature_b64 = String(reinterpret_cast<char *>(signature_b64_buf));
  return true;
}

void init_storage() {
  spiffs_ok = SPIFFS.begin(true);
}

void init_fingerprint() {
  SerialFP.begin(FP_BAUD, SERIAL_8N1, FP_RX_PIN, FP_TX_PIN);
  delay(200);
  finger.begin(FP_BAUD);
  fingerprint_ok = finger.verifyPassword();
}

bool sync_time_from_wifi() {
  configTime(0, 0, VERIFIER_NTP_SERVER_1, VERIFIER_NTP_SERVER_2);
  const unsigned long start = millis();
  while (millis() - start < 15000) {
    const time_t now = time(nullptr);
    if (now >= 1700000000) {
      return true;
    }
    delay(250);
  }
  return false;
}

void init_wifi() {
  if (strlen(VERIFIER_WIFI_SSID) == 0) {
    wifi_ready = false;
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.begin(VERIFIER_WIFI_SSID, VERIFIER_WIFI_PASSWORD);
  const unsigned long start = millis();
  while (millis() - start < 15000) {
    if (WiFi.status() == WL_CONNECTED) {
      wifi_ready = true;
      return;
    }
    delay(250);
  }
  wifi_ready = false;
}

void ensure_wifi_connected() {
  if (WiFi.status() == WL_CONNECTED) {
    wifi_ready = true;
    return;
  }
  wifi_ready = false;
  const unsigned long now = millis();
  if (now - last_wifi_attempt_ms < 10000) {
    return;
  }
  last_wifi_attempt_ms = now;
  WiFi.disconnect(true, true);
  delay(100);
  init_wifi();
}

void print_boot_status() {
  Serial.println("TrustSeal Verifier Fingerprint+Send Boot");
  Serial.printf("R307S: %s\n", fingerprint_ok ? "ok" : "not_found_or_locked");
  Serial.printf("ECDSA signer: %s\n", signer_ok ? "ok" : "failed");
  Serial.printf("SPIFFS: %s\n", spiffs_ok ? "ok" : "failed");
  Serial.printf("WiFi: %s\n", wifi_ready ? "connected" : "not_connected");
  Serial.printf("SSID: %s\n", strlen(VERIFIER_WIFI_SSID) > 0 ? VERIFIER_WIFI_SSID : "<unset>");
  if (wifi_ready) {
    Serial.printf("WiFi local IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("WiFi gateway: %s\n", WiFi.gatewayIP().toString().c_str());
  }
  Serial.printf(
    "API: %s://%s:%d%s\n",
    VERIFIER_API_USE_TLS ? "https" : "http",
    VERIFIER_API_HOST,
    VERIFIER_API_PORT,
    VERIFIER_API_PATH
  );
  Serial.println("Serial commands: enroll <id>, delete <id>, empty, count");
}

std::deque<String> read_queue_lines() {
  std::deque<String> lines;
  if (!spiffs_ok || !SPIFFS.exists(CUSTODY_QUEUE_FILE)) {
    return lines;
  }
  File file = SPIFFS.open(CUSTODY_QUEUE_FILE, FILE_READ);
  if (!file) return lines;
  while (file.available()) {
    String line = file.readStringUntil('\n');
    line.trim();
    if (line.length() > 2) lines.push_back(line);
  }
  file.close();
  return lines;
}

bool rewrite_queue_lines(const std::deque<String> &lines) {
  if (!spiffs_ok) return false;
  File file = SPIFFS.open(CUSTODY_QUEUE_FILE, FILE_WRITE);
  if (!file) return false;
  for (const auto &line : lines) file.println(line);
  file.close();
  return true;
}

size_t queue_depth() {
  return read_queue_lines().size();
}

void trim_queue_to_limit() {
  std::deque<String> lines = read_queue_lines();
  while (lines.size() > CUSTODY_QUEUE_MAX_ENTRIES) lines.pop_front();
  rewrite_queue_lines(lines);
}

bool queue_packet(const String &packet_json) {
  if (!spiffs_ok) return false;
  File file = SPIFFS.open(CUSTODY_QUEUE_FILE, FILE_APPEND);
  if (!file) file = SPIFFS.open(CUSTODY_QUEUE_FILE, FILE_WRITE);
  if (!file) return false;
  file.println(packet_json);
  file.close();
  trim_queue_to_limit();
  return true;
}

bool peek_queue_head(String &line_out) {
  std::deque<String> lines = read_queue_lines();
  if (lines.empty()) return false;
  line_out = lines.front();
  return true;
}

bool pop_queue_head() {
  std::deque<String> lines = read_queue_lines();
  if (lines.empty()) return false;
  lines.pop_front();
  return rewrite_queue_lines(lines);
}

String build_and_sign_custody_packet(const char *fingerprint_result, const int confidence, const int template_id) {
  const uint32_t seq = ++custody_seq;
  const String event_id = next_custody_event_id(seq);
  const String ts = now_iso_utc();
  const int normalized_confidence = confidence < 0 ? confidence : min(confidence, 100);

  const String canonical_json = build_custody_approval_canonical_json(
    event_id,
    ts,
    fingerprint_result,
    normalized_confidence,
    template_id
  );
  const String approval_hash = sha256_hex(canonical_json);

  String signature_b64;
  const bool signature_ok = sign_hash_hex(approval_hash, signature_b64);

  StaticJsonDocument<1024> packet;
  packet["custody_event_id"] = event_id;
  packet["shipment_id"] = VERIFIER_SHIPMENT_ID;
  packet["leg_id"] = VERIFIER_LEG_ID;
  packet["verifier_device_id"] = VERIFIER_DEVICE_ID;
  packet["verifier_user_id"] = VERIFIER_USER_ID;
  packet["ts"] = ts;
  packet["fingerprint_result"] = fingerprint_result;
  packet["digital_signer_address"] = VERIFIER_SIGNER_ADDRESS;
  packet["approval_message_hash"] = approval_hash;
  packet["signature"] = signature_ok ? signature_b64 : "";
  packet["sig_alg"] = "ecdsa-secp256r1";
  packet["idempotency_key"] = event_id;
  if (normalized_confidence >= 0) {
    packet["fingerprint_score"] = normalized_confidence;
  } else {
    packet["fingerprint_score"] = nullptr;
  }
  if (template_id >= 0) {
    packet["fingerprint_template_id"] = String(template_id);
  } else {
    packet["fingerprint_template_id"] = nullptr;
  }

  String packet_json;
  serializeJson(packet, packet_json);
  return packet_json;
}

void queue_custody_event(const char *fingerprint_result, const int confidence, const int template_id) {
  const String packet_json = build_and_sign_custody_packet(fingerprint_result, confidence, template_id);
  const bool buffered = queue_packet(packet_json);
  StaticJsonDocument<256> log_doc;
  log_doc["type"] = "custody_queued";
  log_doc["fingerprint_result"] = fingerprint_result;
  log_doc["buffered"] = buffered;
  log_doc["queue_depth"] = static_cast<uint32_t>(queue_depth());
  log_doc["ts"] = now_iso_utc();
  serializeJson(log_doc, Serial);
  Serial.println();
}

void scan_fingerprint_once() {
  if (!fingerprint_ok) return;
  const uint8_t img = finger.getImage();
  if (img == FINGERPRINT_NOFINGER) return;
  if (img != FINGERPRINT_OK) {
    queue_custody_event("error", -1, -1);
    return;
  }

  const uint8_t tz = finger.image2Tz();
  if (tz != FINGERPRINT_OK) {
    queue_custody_event("error", -1, -1);
    return;
  }

  const uint8_t search = finger.fingerFastSearch();
  if (search == FINGERPRINT_OK) {
    queue_custody_event("match", finger.confidence, finger.fingerID);
    return;
  }
  if (search == FINGERPRINT_NOTFOUND) {
    queue_custody_event("no_match", finger.confidence, -1);
    return;
  }
  queue_custody_event("error", -1, -1);
}

bool wait_for_image(const unsigned long timeout_ms) {
  const unsigned long start = millis();
  while (millis() - start < timeout_ms) {
    const uint8_t img = finger.getImage();
    if (img == FINGERPRINT_OK) {
      return true;
    }
    if (img != FINGERPRINT_NOFINGER) {
      return false;
    }
    delay(50);
  }
  return false;
}

bool wait_for_finger_release(const unsigned long timeout_ms) {
  const unsigned long start = millis();
  while (millis() - start < timeout_ms) {
    const uint8_t img = finger.getImage();
    if (img == FINGERPRINT_NOFINGER) {
      return true;
    }
    delay(50);
  }
  return false;
}

bool enroll_fingerprint(const int id) {
  if (!fingerprint_ok || id <= 0 || id > 127) {
    return false;
  }

  Serial.printf("Enroll: place finger for ID %d\n", id);
  if (!wait_for_image(15000)) {
    Serial.println("Enroll: first capture timeout");
    return false;
  }
  if (finger.image2Tz(1) != FINGERPRINT_OK) {
    Serial.println("Enroll: first template conversion failed");
    return false;
  }

  Serial.println("Enroll: remove finger");
  if (!wait_for_finger_release(10000)) {
    Serial.println("Enroll: finger release timeout");
    return false;
  }

  Serial.printf("Enroll: place same finger again for ID %d\n", id);
  if (!wait_for_image(15000)) {
    Serial.println("Enroll: second capture timeout");
    return false;
  }
  if (finger.image2Tz(2) != FINGERPRINT_OK) {
    Serial.println("Enroll: second template conversion failed");
    return false;
  }
  if (finger.createModel() != FINGERPRINT_OK) {
    Serial.println("Enroll: model creation failed");
    return false;
  }
  if (finger.storeModel(id) != FINGERPRINT_OK) {
    Serial.println("Enroll: store model failed");
    return false;
  }

  Serial.printf("Enroll: success for ID %d\n", id);
  return true;
}

void handle_serial_command(const String &command_raw) {
  String command = command_raw;
  command.trim();
  if (command.length() == 0) {
    return;
  }

  if (command.equalsIgnoreCase("empty")) {
    const uint8_t rc = finger.emptyDatabase();
    Serial.printf("Empty DB: %s\n", rc == FINGERPRINT_OK ? "ok" : "failed");
    return;
  }

  if (command.equalsIgnoreCase("count")) {
    const uint8_t rc = finger.getTemplateCount();
    if (rc == FINGERPRINT_OK) {
      Serial.printf("Template count: %d\n", finger.templateCount);
    } else {
      Serial.println("Template count: failed");
    }
    return;
  }

  if (command.startsWith("delete ")) {
    const int id = command.substring(7).toInt();
    const uint8_t rc = finger.deleteModel(id);
    Serial.printf("Delete ID %d: %s\n", id, rc == FINGERPRINT_OK ? "ok" : "failed");
    return;
  }

  if (command.startsWith("enroll ")) {
    const int id = command.substring(7).toInt();
    enroll_fingerprint(id);
    return;
  }

  Serial.println("Unknown command. Use: enroll <id>, delete <id>, empty, count");
}

void process_serial_commands() {
  while (Serial.available()) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      handle_serial_command(serial_command_buffer);
      serial_command_buffer = "";
      continue;
    }
    serial_command_buffer += c;
  }
}

SendResult post_queued_packet(const String &packet_json) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("send: wifi unavailable");
    return SendResult::RetryLater;
  }

  HTTPClient http;
  http.setTimeout(8000);
  http.setFollowRedirects(HTTPC_FORCE_FOLLOW_REDIRECTS);
  const String url =
    String(VERIFIER_API_USE_TLS ? "https://" : "http://") +
    VERIFIER_API_HOST + ":" + String(VERIFIER_API_PORT) + VERIFIER_API_PATH;
#if VERIFIER_API_USE_TLS
  wifi_secure_client.setInsecure();
  if (!http.begin(wifi_secure_client, url)) {
#else
  if (!http.begin(wifi_client, url)) {
#endif
    Serial.println("send: http begin failed");
    return SendResult::RetryLater;
  }
  http.addHeader("Content-Type", "application/json");
  if (strlen(VERIFIER_API_BEARER_TOKEN) > 0) {
    http.addHeader("X-Verifier-Device-Id", VERIFIER_DEVICE_ID);
    http.addHeader("X-Verifier-Token", VERIFIER_API_BEARER_TOKEN);
  }
  const int status_code = http.POST(packet_json);
  const String response_body = status_code > 0 ? http.getString() : "";
  http.end();

  Serial.printf("send: status=%d\n", status_code);
  if (status_code < 0) {
    Serial.print("send: error=");
    Serial.println(HTTPClient::errorToString(status_code));
  }
  if (response_body.length() > 0) {
    Serial.print("send: body=");
    Serial.println(response_body);
  }

  if (status_code == 409) return SendResult::Acked;

  if (status_code == 202) {
    StaticJsonDocument<512> resp;
    if (deserializeJson(resp, response_body) == DeserializationError::Ok) {
      const bool success = resp["success"] | false;
      const bool accepted = resp["data"]["accepted"] | false;
      if (success && accepted) return SendResult::Acked;
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
  if (!peek_queue_head(packet_json)) return;
  const SendResult result = post_queued_packet(packet_json);
  if (result == SendResult::Acked) {
    pop_queue_head();
    retry_backoff_ms = CUSTODY_RETRY_BASE_MS;
    next_retry_after_ms = 0;
    Serial.printf("send: acked queue_depth=%u\n", static_cast<unsigned>(queue_depth()));
  } else if (result == SendResult::DropPermanent) {
    pop_queue_head();
    Serial.printf("send: dropped queue_depth=%u\n", static_cast<unsigned>(queue_depth()));
  } else {
    next_retry_after_ms = millis() + retry_backoff_ms;
    retry_backoff_ms = min(retry_backoff_ms * 2, static_cast<unsigned long>(CUSTODY_RETRY_MAX_MS));
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
  init_signer();
  init_storage();
  if (spiffs_ok) {
    SPIFFS.remove(CUSTODY_QUEUE_FILE);
  }
  init_fingerprint();
  init_wifi();
  if (wifi_ready) {
    const bool time_ok = sync_time_from_wifi();
    Serial.printf("Time sync: %s\n", time_ok ? "ok" : "failed");
  }
  print_boot_status();
}

void loop() {
  const unsigned long now = millis();
  ensure_wifi_connected();
  process_serial_commands();

  if (now - last_scan_ms >= FP_SCAN_INTERVAL_MS) {
    last_scan_ms = now;
    scan_fingerprint_once();
  }

  if (now - last_send_ms >= CUSTODY_SEND_INTERVAL_MS) {
    last_send_ms = now;
    if (next_retry_after_ms == 0 || now >= next_retry_after_ms) {
      process_send_once();
    }
  }
}
