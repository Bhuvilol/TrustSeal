#ifndef VERIFIER_ARDUINO_SECRETS_H
#define VERIFIER_ARDUINO_SECRETS_H

#if __has_include("verifier_secrets.local.h")
#include "verifier_secrets.local.h"
#else
static const char *VERIFIER_PRIVATE_KEY_PEM =
  "REPLACE_WITH_PROVISIONED_EC_PRIVATE_KEY_PEM";
#endif

#endif
