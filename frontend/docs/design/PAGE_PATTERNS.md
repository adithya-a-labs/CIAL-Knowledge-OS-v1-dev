# Page Patterns

This document defines common page templates for the product so new screens feel predictable and consistent.

## Search + Filter Page
Use for knowledge discovery, document search, SOP lookup, and content browse experiences.

Layout:
- header with page title and utility actions
- search input near the top
- quick filters or facets
- result list or discovery grid
- optional secondary insights or recommendations

Interaction expectations:
- search should feel fast and focused
- filters should refine results without requiring a full page reload
- results should support both scanning and drilling in

## Knowledge Discovery Page
Use for curated content surfaces, category browsing, and initial knowledge entry points.

Layout:
- strong page title or section intro
- discovery cards grouped by category
- supporting content or featured items
- optional department or ownership grouping

Interaction expectations:
- help users orient quickly
- make the next action obvious
- keep category exploration calm and structured

## File Manager Page
Use for documents, policies, SOPs, and workspace files.

Layout:
- breadcrumb path
- folder and file listing
- action bar for selection and bulk operations
- optional metadata columns

Interaction expectations:
- browsing should feel organized and reliable
- folders should appear before files
- file actions should be accessible without clutter

## AI Assistant Page
Use for conversational knowledge assistance, search support, and AI-guided actions.

Layout:
- compact header or context area
- chat or prompt surface
- supporting context, result references, and action area
- optional suggestions or recent work

Interaction expectations:
- responses should be readable and trustworthy
- AI actions should remain explainable
- the interface should not feel playful or overly chat-like

### Assistant navigation contract
- `/assistant/new` represents a client-only empty draft. Generic Assistant and New Conversation actions always use this route and clear conversation-scoped messages, uploads, selected context, citations, and pending handoffs.
- `/assistant/new?handoff=<one-time-token>` represents a new client-only draft with only the context explicitly supplied by the originating document, folder, search, upload, note, or Saved Knowledge action.
- `/assistant/conversations/:conversationId` represents an existing persisted conversation and is entered only through an explicit history or recent-conversation selection.
- History hydration may populate the history list but must never choose a conversation for a fresh route.
- The first submitted draft message lets the chat API create the backend session. The client then replaces the draft URL with the persisted conversation route.

## Analytics Dashboard
Use for operational reporting, document usage, learning progress, and knowledge insights.

Layout:
- summary metrics at the top
- grouped charts or insight blocks
- supporting tables or detailed sections
- clear filters and time controls

Interaction expectations:
- prioritize clarity over visual drama
- keep metrics restrained and meaningful
- avoid turning the page into a dashboard of decorative visuals

## Detail Page
Use for documents, policies, SOPs, department profiles, experts, and learning resources.

Layout:
- strong title and metadata
- summary or overview section
- main content body
- related items or actions
- secondary context as needed

Interaction expectations:
- show the user where they are immediately
- make key actions obvious and predictable
- support both quick scan and deeper reading

### Knowledge Center document workspace
- Keep the shared global application navigation mounted; default it to the 64px icon rail when entering a document.
- Persist the user's global navigation width preference locally across routes and refreshes.
- Treat the Corpus Tree and document assistant as workspace panels, not global navigation.
- Responsive disclosure order is global navigation first, then Corpus Tree, then document assistant. Use overlay drawers only below each panel's desktop breakpoint.
- Icon-only global navigation must retain accessible names, keyboard focus treatment, active-route state, and hover/focus tooltips.

## Settings and Admin Page
Use for configuration, governance, and management screens.

Layout:
- clear section hierarchy
- grouped controls with explained purpose
- supporting guidance or status if needed

Interaction expectations:
- remain calm and precise
- avoid overloading the page with controls
- keep complex settings readable and structured
