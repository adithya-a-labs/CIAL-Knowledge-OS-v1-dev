# Proposed CIAL component architecture

## Reuse existing CIAL components

- Persistent global navigation and adaptive appearance control.
- Corpus tree/folder/document picker.
- `SourceViewerPanel`, `DocumentViewerPanel`, and format renderers.
- Assistant composer, streamed lifecycle, citations, Retry/Stop.
- System-status and indexing-state surfaces.
- Shared dialogs, menus, buttons, focus management, and ACL guards.

## New notebook-specific components

```text
NotebookWorkspacePage
|- NotebookHeader
|- NotebookResponsiveLayout
|  |- NotebookContextPanel
|  |  |- NotebookSourceList
|  |  `- NotebookSourceStateRow
|  |- NotebookConversationPanel
|  |  |- NotebookThread
|  |  `- NotebookComposer
|  `- NotebookOutputsPanel
|     |- NotebookNoteCard/Editor
|     |- ArtifactLauncherGrid
|     `- ArtifactJobCard/ArtifactViewer
`- NotebookOverlayHost
   |- CitationDetail
   |- ContextPicker
   `- SharePolicyDialog (deferred)
```

Page state owns notebook identity and responsive active panel. Context state owns
selected Corpus IDs and readiness. Conversation state owns persisted session,
messages, citations, and stream lifecycle. Output state owns notes and artifact
jobs. The shared document viewer owns page/chunk/highlight state.
