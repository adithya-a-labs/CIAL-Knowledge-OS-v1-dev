# Information architecture

NotebookLM uses a shallow two-route architecture:

1. **Library**: discover, filter, sort, change view, or create.
2. **Notebook**: one persistent shell containing:
   - **Sources**: ingest, select, sort, preview, manage;
   - **Chat**: ask, stream, cite, save, rate;
   - **Studio**: generate notes and durable output artifacts.

The key design move is not the visual three-column layout itself; it is the
stable semantic triad. Desktop renders the triad simultaneously, while tablet
and mobile render it as tabs. Overlays remain subordinate to the active surface.
