# CIAL Knowledge OS Design Language

This document is the primary source of truth for the visual and interaction direction of CIAL Knowledge OS. Future UI work should follow this document before introducing new patterns, visuals, or component behavior.

Use this file as the reference for prompts, implementation tasks, and design reviews. If a decision feels unclear, default to calm, professional, enterprise-grade clarity over novelty.

# User Emotional Experience

Every screen in CIAL Knowledge OS should make the user feel a certain way. The interface is not simply a collection of components—it is an environment that people spend hours working inside. Every interaction should reduce stress, increase confidence, and make knowledge feel immediately accessible.

## The Desired Feeling

When using CIAL Knowledge OS, users should feel:

### Calm
The interface should never overwhelm users with visual noise. Whitespace, hierarchy, and restrained colors should create a peaceful working environment. Users should feel that everything has its place.

---

### In Control
Users should always know:
- where they are
- what they can do next
- what information they're looking at
- how to return to previous views

Navigation should feel effortless.

---

### Confident
Information should feel trustworthy. Actions should feel safe. Important operations should feel deliberate. The UI should inspire confidence rather than uncertainty.

---

### Productive
The product should feel fast even when handling large knowledge bases. Users should spend their time thinking—not searching through clutter. The interface should remove friction from everyday work.

---

### Intelligent
The system should feel like a knowledgeable assistant. Search, recommendations, AI responses, and organization should make users feel that the software understands their intent. The product should quietly help without constantly demanding attention.

---

### Professional
This is enterprise software used in operational environments. The design should communicate reliability, maturity, and precision. It should never feel experimental or playful.

---

### Premium
The experience should feel thoughtfully crafted. Small details matter:
- smooth transitions
- consistent spacing
- polished typography
- subtle animations
- refined interactions

Quality should be felt rather than announced.

---

### Familiar
Users should immediately understand how to interact with the interface. Borrow proven interaction patterns from:
- Windows Explorer
- Dropbox
- Google Drive
- Arc
- Linear
- GitHub
- Notion

Avoid reinventing common workflows unless there is a clear usability benefit.

---

### Focused
At any moment, the interface should direct attention toward one primary task. Avoid competing focal points. There should rarely be more than one obvious primary action on screen.

---

### Empowered
Users should feel that the system gives them more capability rather than more complexity. AI should augment human decision-making, not replace it. Every feature should increase clarity and confidence.

## Emotional Design Principles

Every new page should answer these questions before implementation:
- Does this reduce cognitive load?
- Does this make users feel confident?
- Does this help users find information faster?
- Does the interface feel calm?
- Is there unnecessary visual noise?
- Can the next action be understood in under two seconds?
- Would someone feel comfortable spending eight hours a day using this interface?
- Does this interaction feel polished enough for a premium enterprise product?

## If a design choice creates a conflict

Always prioritize:
1. Clarity
2. Simplicity
3. Confidence
4. Consistency
5. Speed
6. Visual polish

Never sacrifice usability purely for aesthetics.

## The North Star

The ideal user reaction is:

> "Everything is exactly where I expect it to be. The interface stays out of my way. Finding knowledge feels effortless, and I trust the system."

This sentence should guide every future UI decision.

## 1. Product Philosophy

CIAL Knowledge OS is not a generic admin dashboard. It is an enterprise operating system for organizational knowledge used by airport operations teams, knowledge workers, departments, analysts, and support staff.

The interface should:
- reduce cognitive load
- help users find trusted information quickly
- feel dependable for long work sessions
- support fast scanning, deep reading, and confident action
- make important knowledge feel visible, discoverable, and safe to act on

The UI should feel like a calm command center for knowledge work, not a busy reporting portal.

## 2. Product Personality

Preferred traits:
- calm
- premium
- professional
- approachable
- modern
- fast
- confident
- minimal
- intelligent
- human

Traits to avoid:
- flashy
- noisy
- generic
- over-designed
- childish
- gaming-like
- Bootstrap-like
- Material-like

The tone should feel composed and helpful, with a sense of authority without becoming cold or corporate-heavy.

## 3. Core Visual Principles

The visual system should be guided by the following:
- generous whitespace
- thin borders
- subtle shadows
- rounded corners
- soft green accents
- muted pastel category colors
- strong hierarchy
- calm contrast
- no unnecessary visual noise

The goal is clarity first. Every element should earn its place.

## 4. Color Usage Rules

Do not hardcode final colors unless existing design tokens are already present. Instead, follow these usage rules:
- green = primary action, selection, success, and CIAL identity
- blue = information, airfield, technical, or system-oriented meaning
- orange = warnings, baggage, or energy-related emphasis
- red = safety, critical, or fire-related urgency
- purple = IT, systems, or advanced tooling
- gray = neutral UI foundation
- pastel backgrounds should be reserved for category and discovery cards
- avoid large saturated color blocks

Use color as a signal, not as decoration. Prefer a restrained palette with one meaningful accent at a time.

## 5. Typography Rules

Typography should feel clear, composed, and quietly confident.

General hierarchy:
- page titles: bold, clear, not oversized
- subtitles: muted, concise
- section titles: compact and strong
- labels: uppercase only when needed
- body text: readable and calm
- captions and metadata: muted and small

Consistency matters more than exact font size. The system should feel stable across pages, components, and content types.

## 6. Spacing System

Use a consistent spacing scale:
- 4
- 8
- 12
- 16
- 20
- 24
- 32
- 40
- 48
- 64

Rules:
- avoid random spacing values
- give sections room to breathe
- keep cards from feeling cramped
- preserve row rhythm even in dense areas
- use spacing to build calm structure rather than visual tension

## 7. Border Radius Rules

Use conservative rounding:
- small controls: 8–10px
- inputs, buttons, and cards: 12px
- large panels: 14–18px
- avoid pill shapes unless used intentionally for badges or tags

Rounded corners should make surfaces feel softer and more approachable, not playful or toy-like.

## 8. Shadow and Border Rules

Prefer:
- 1px borders
- subtle soft shadows
- layered cards only when they improve separation

Avoid:
- heavy shadows
- glassmorphism
- neumorphism
- floating everything

The interface should feel tactile and refined, not theatrical.

## 9. Layout Rules

Use a predictable page hierarchy across the product:
1. Header
2. Search or filters
3. Discovery cards or highlight area
4. Primary content
5. Secondary content when needed
6. Footer or supporting actions

This pattern should feel consistent across:
- Knowledge Center
- AI Assistant
- Documents
- Policies and SOPs
- FAQs
- Expert Directory
- Learning Hub
- Knowledge Graph
- Analytics
- My Workspace

Pages should feel familiar even when the content type changes.

## 10. Component Rules

Use components in a deliberate, reusable way.

Buttons:
- primary actions should be clear and restrained
- secondary actions should be visually quieter
- avoid competing CTAs in the same area

Search bars:
- should feel lightweight and efficient
- should be easy to scan and easy to dismiss

Filters:
- should support quick narrowing without overwhelming the page
- should remain simple and predictable

Cards:
- should present one clear idea or object
- should not feel decorative for decoration’s sake

Tabs:
- should be compact and clear
- should support scanning without adding visual noise

Tables and lists:
- should not feel like spreadsheets unless the data truly requires that treatment
- longer content should often be expressed as structured lists or document-style rows

File manager:
- should feel organized and navigable, like a trusted workspace

Sidebars:
- should remain calm, scannable, and low-friction

Breadcrumbs:
- should show context clearly and support backtracking

Badges:
- should be subtle and readable
- should not become visual clutter

Empty states:
- should guide the user with clarity and calm confidence

Modals and popovers:
- should feel temporary and focused, not heavy or blocking

## 11. File Manager Pattern

Document browsing should feel inspired by Dropbox, Google Drive, and Windows Explorer, but refined for enterprise knowledge work.

The file manager pattern should include:
- breadcrumb path for context
- list/grid toggle when appropriate
- folders shown before files
- recognizable file icons
- owner or department metadata
- file type
- size
- last updated time
- row hover states
- selection state
- kebab or action menu
- empty state guidance
- backend-ready actions and loading states

This pattern should support both document browsing and operational file handling without feeling like a generic table dump.

## 12. Cards Pattern

Cards should have clear purpose and restrained style.

Category cards:
- pastel, discovery-focused
- include icon, title, and lightweight metadata
- support quick orientation and browsing

Department cards:
- smaller and lighter
- centered on organization and ownership

Metric cards:
- restrained and factual
- avoid fake visual drama or overpromising emphasis

Content cards:
- clean, readable, and action-oriented
- should make scanning easy and support next steps

## 13. Motion Rules

Use subtle micro-interactions only.

Allowed motion:
- hover lift or emphasis
- fade in and out
- underline slide
- panel open and close transitions
- short loading and state changes

Timing:
- 150–250ms for most UI transitions

Avoid:
- bouncing
- exaggerated transitions
- constant motion
- distracting animations

Motion should support clarity and feedback, not entertainment.

## 14. Iconography Rules

Use:
- simple outline icons
- consistent stroke width
- meaningful icons with clear purpose
- file-type icons for documents and media

Avoid:
- emoji as primary icons
- random mixed icon packs
- heavy filled icons
- decorative icons with no purpose

Icons should reinforce meaning quickly without adding visual noise.

## 15. Accessibility Rules

Accessibility is part of the design system, not an afterthought.

Requirements:
- readable contrast
- keyboard-accessible controls
- visible focus states
- semantic buttons and links
- aria labels for icon-only buttons
- minimum practical click targets
- do not rely on color alone to communicate meaning

The experience should remain usable for keyboard, assistive technology, and low-vision users.

## 16. Backend-Ready UI Rules

Frontend mock data should be structured cleanly and thoughtfully.

Guidance:
- avoid hardcoded repeated JSX where a component can be reused
- keep handlers stubbed clearly
- separate presentational and data logic where reasonable
- make components reusable across pages and states
- assume real data will arrive from APIs and search systems

The UI should be implementation-friendly for future engineering work.

## 17. Things We Never Do

Never:
- use ugly native selects when custom controls already exist
- use generic admin dashboard layouts
- make document tables feel like spreadsheets
- overload dashboards with fake metrics
- use more than one primary CTA in the same area
- mix design languages
- introduce new dependencies without a clear need
- sacrifice clarity for decoration

## 18. Design Review Checklist

Before shipping or approving a UI change, confirm that it:
- fits the CIAL design language
- feels calm and premium
- uses consistent spacing
- uses existing components and tokens where available
- is responsive
- is accessible
- is backend-ready
- avoids unnecessary dependencies
- has no visual clutter
- follows established page patterns

## Design Influences and Borrowed Patterns

The system is not a copy of any single product. It blends a few strong references into an enterprise-first experience.

- Arc: spacious calm interface and polished sidebar behavior
- Linear: typography, spacing, command-like efficiency, and refined micro-interactions
- Notion: clean organization of information and calm content surfaces
- GitHub: practical density, developer-grade clarity, and straightforward interaction patterns
- Dropbox, Google Drive, and Windows Explorer: file browsing and document management patterns
- Apple Human Interface Guidelines and Figma: restraint, clarity, and precise interaction design

The result should feel like a modern enterprise workspace rather than a themed template.
