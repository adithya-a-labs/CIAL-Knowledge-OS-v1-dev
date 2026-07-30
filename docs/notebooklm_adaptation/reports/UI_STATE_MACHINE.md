# UI state machine

Major state families:

- Library: loading -> ready -> filtered/sorted/view-mode -> creating.
- Sources: empty -> import dialog -> form -> processing -> ready -> selected /
  deselected -> preview.
- Chat: empty -> draft -> submitting -> generating/Stop -> completed/citations.
- Citation: closed -> detail overlay -> source action -> closed.
- Notes: none -> generating -> editor -> autosaved card -> menu -> confirmed delete.
- Studio: ready -> customisation (where applicable) -> generating disabled card
  -> completed card -> viewer/menu.
- Persistence: route loading -> restored notebook state.

No product failure/retry state was safely induced. Retry remains UNKNOWN.
