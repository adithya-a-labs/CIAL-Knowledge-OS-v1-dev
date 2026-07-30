# Executive summary

## Observed interaction principles

1. **Context is explicit.** Source checkboxes make the grounding set visible and
   reversible. Repeating one identical question produced four citation anchors
   from source 1 with one source selected, then six anchors using source
   ordinals 1 and 2 with both selected.
2. **Desktop and narrow layouts preserve the same mental model.** At 1440 and
   1024, Sources, Chat, and Studio coexist as columns. At 768 and 390, the same
   three areas become equal-priority tabs without document-level horizontal
   overflow.
3. **Evidence stays near claims.** Inline citation buttons open a compact detail
   surface and provide a source action. Source preview remains a first-class
   notebook surface.
4. **Long jobs are durable objects.** Studio uses disabled generating cards,
   completion announcements, persistent cards, viewers, menus, source counts,
   ratings, and sharing/download actions. All nine visible output types
   ultimately completed.
5. **Lightweight knowledge capture is embedded.** Notes combine generation,
   rich editing, autosave-on-close, overflow actions, conversion, export, and
   confirmed deletion.
6. **Restoration is observable.** Reload and exact reopening restored both
   controlled chat turns and all ten citation anchors.

## Recommended CIAL direction

Build a CIAL-native three-surface notebook: **Context / Conversation / Outputs**.
Reuse the Corpus API and shared document viewer; persist notebook, notes, chat,
citations, selections, and artifact jobs in PostgreSQL; keep files authoritative
on the filesystem and retrieval in Qdrant; stream query and artifact lifecycle
events from the offline backend.

Adopt explicit source selection, evidence-proximate citations, durable async job
cards, and responsive panel-to-tab reflow. Adapt them to CIAL's persistent global
navigation, calm premium enterprise design, indexing visibility, folder/document
context, ACL badges, evidence-strength indicators, and source page/chunk
navigation. Do not copy Google branding, cloud-only source adapters, account-level
sharing assumptions, or opaque AI orchestration.
