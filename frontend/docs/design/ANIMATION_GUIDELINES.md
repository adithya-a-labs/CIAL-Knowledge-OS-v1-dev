# Animation Guidelines

Motion in CIAL Knowledge OS should feel quiet, useful, and deliberate. It should support comprehension and feedback without distracting from work.

## Allowed animations
Use motion for:
- hover feedback
- opening and closing panels
- tab transitions
- popover and menu reveal
- loading states
- skeleton transitions
- state changes that benefit from feedback

## Timing
- short transitions: 150–200ms
- slightly longer transitions: 200–250ms
- avoid long or delayed motion

## Easing
Prefer simple, soft easing such as:
- ease-out for enter animations
- ease-in-out for panel transitions
- minimal motion curves for hover feedback

## Hover states
Hover interactions should be subtle and informative. A small change in color, underline, or elevation is usually enough.

## Tab transitions
Tabs should shift clearly but not dramatically. Keep transitions brief and predictable.

## Popover transitions
Popovers and menus should appear quickly and gently, with enough motion to signal intent but not enough to feel flashy.

## Loading states
Loading should be calm and structured. Use skeletons or lightweight placeholders where appropriate.

## What to avoid
Avoid:
- bouncing
- exaggerated transitions
- constant motion
- animation that competes with content
- flashy entrance effects
- decorative movement that does not serve a task

The principle is simple: motion should support understanding, not perform for attention.
