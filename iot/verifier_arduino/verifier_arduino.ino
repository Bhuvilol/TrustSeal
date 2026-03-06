#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_Fingerprint.h>
#include <HardwareSerial.h>
#include <FS.h>
#include <SPIFFS.h>
#include <deque>
#define TINY_GSM_MODEM_A7672X
#include <TinyGsmClient.h>
#include <ArduinoHttpClient.h>

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
HardwareSerial SerialAT(2);
Adafruit_Fingerprint finger(&SerialFP);
TinyGsm modem(SerialAT);
TinyGsmClient modem_client(modem);

bool fingerprint_ok = false;
bool signer_ok = false;
bool spiffs_ok = false;
bool modem_ready = false;
uint32_t custody_seq = 0;
unsigned long last_scan_ms = 0;
unsigned long last_send_ms = 0;
unsigned long last_modem_attempt_ms = 0;
unsigned long next_retry_after_ms = 0;
unsigned long retry_backoff_ms = CUSTODY_RETRY_BASE_MS;

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
  const time_t base_epoch_2026 = 1767225600;
  const time_t now = base_epoch_2026 + static_cast<time_t>(millis() / 1000);
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

void init_modem() {
  SerialAT.begin(MODEM_BAUD, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
  delay(300);
  modem_ready = modem.restart();
  if (!modem_ready) return;
  modem_ready = modem.waitForNetwork(30000);
  if (!modem_ready) return;
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
  Serial.println("TrustSeal Verifier Fingerprint+Send Boot");
  Serial.printf("R307S: %s\n", fingerprint_ok ? "ok" : "not_found_or_locked");
  Serial.printf("ECDSA signer: %s\n", signer_ok ? "ok" : "failed");
  Serial.printf("SPIFFS: %s\n", spiffs_ok ? "ok" : "failed");
  Serial.printf("Modem network: %s\n", modem_ready ? "connected" : "not_connected");
  Serial.printf("APN: %s\n", MODEM_APN);
  Serial.printf("API: http://%s:%d%s\n", VERIFIER_API_HOST, VERIFIER_API_PORT, VERIFIER_API_PATH);
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

  StaticJsonDocument<768> canonical;
  canonical["custody_event_id"] = event_id;
  canonical["shipment_id"] = VERIFIER_SHIPMENT_ID;
  canonical["leg_id"] = VERIFIER_LEG_ID;
  canonical["verifier_device_id"] = VERIFIER_DEVICE_ID;
  canonical["verifier_user_id"] = VERIFIER_USER_ID;
  canonical["ts"] = ts;
  canonical["fingerprint_result"] = fingerprint_result;
  canonical["digital_signer_address"] = VERIFIER_SIGNER_ADDRESS;
  canonical["sig_alg"] = "ecdsa-secp256r1";
  canonical["idempotency_key"] = event_id;
  if (confidence >= 0) {
    canonical["fingerprint_score"] = confidence;
  } else {
    canonical["fingerprint_score"] = nullptr;
  }
  if (template_id >= 0) {
    canonical["fingerprint_template_id"] = String(template_id);
  } else {
    canonical["fingerprint_template_id"] = nullptr;
  }

  String canonical_json;
  serializeJson(canonical, canonical_json);
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
  if (confidence >= 0) {
    packet["fingerprint_score"] = confidence;
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

SendResult post_queued_packet(const String &packet_json) {
  if (!modem_ready || !modem.isGprsConnected()) {
    return SendResult::RetryLater;
  }

  HttpClient http(modem_client, VERIFIER_API_HOST, VERIFIER_API_PORT);
  http.setHttpResponseTimeout(8000);
  http.beginRequest();
  http.post(VERIFIER_API_PATH);
  http.sendHeader("Content-Type", "application/json");
  if (strlen(VERIFIER_API_BEARER_TOKEN) > 0) {
    http.sendHeader("Authorization", String("Bearer ") + VERIFIER_API_BEARER_TOKEN);
    http.sendHeader("X-Verifier-Device-Id", VERIFIER_DEVICE_ID);
  }
  http.sendHeader("Content-Length", packet_json.length());
  http.beginBody();
  http.print(packet_json);
  http.endRequest();

  const int status_code = http.responseStatusCode();
  const String response_body = http.responseBody();
  http.stop();

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
  } else if (result == SendResult::DropPermanent) {
    pop_queue_head();
  } else {
    next_retry_after_ms = millis() + retry_backoff_ms;
    retry_backoff_ms = min(retry_backoff_ms * 2, static_cast<unsigned long>(CUSTODY_RETRY_MAX_MS));
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  init_signer();
  init_storage();
  init_fingerprint();
  init_modem();
  print_boot_status();
}

void loop() {
  const unsigned long now = millis();
  ensure_modem_connected();

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
