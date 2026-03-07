#ifndef TRACKER_ARDUINO_SECRETS_H
#define TRACKER_ARDUINO_SECRETS_H

#if __has_include("tracker_secrets.local.h")
#include "tracker_secrets.local.h"
#else
static const char *TRACKER_PRIVATE_KEY_PEM =
  "REPLACE_WITH_PROVISIONED_EC_PRIVATE_KEY_PEM";

static const char *TRACKER_PUBKEY_ID = "replace-with-provisioned-pubkey-id";
#endif

#endif
