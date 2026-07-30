# Network and runtime observations

## Observed

- Copied-text and website imports exposed processing then ready states.
- Chat exposed a Stop control during generation and completed with citations.
- Studio displayed disabled generating cards and later completion announcements.
- Video explicitly warned that generation may take a while and later completed.
- Reload restored two controlled chat turns and ten citation anchors.
- Console capture contained 28 warning/error events across five sanitized unique
  messages: a closed async extension message channel, default logger warning,
  two experimentation lookup warnings, and a missing config ID/name warning.

## Unavailable

The connected Chrome surface exposed console logs but not a raw network/CDP
request stream, Performance Timeline resource entries, or trace export. Therefore
request hosts, payloads, headers, auth data, streaming frame shapes, CLS, and
network timings are UNKNOWN rather than inferred.
