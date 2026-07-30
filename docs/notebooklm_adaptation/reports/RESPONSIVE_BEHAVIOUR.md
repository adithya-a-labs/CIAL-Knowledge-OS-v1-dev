# Responsive behaviour

| Viewport | Library | Notebook | Overflow |
|---|---|---|---|
| 1440x900 | Full toolbar/filter/view controls | Three columns; side panels ~315px | None |
| 1024x768 | Full desktop controls | Three columns; side panels ~209px | None |
| 768x1024 | Full library controls | Sources/Chat/Studio tabs (267/245/256px) | None |
| 390x844 | Grid/list controls hidden; compact Create/search/sort | Tabs (141/119/130px), one active panel | None |

Primary source, chat/citation, and Studio flows were exercised at each breakpoint.
The narrow interaction model changes from simultaneous comparison to explicit
panel switching while preserving labels and route state.
