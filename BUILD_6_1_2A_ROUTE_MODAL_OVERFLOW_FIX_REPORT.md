# BUILD 6.1.2A — ROUTE MODAL OVERFLOW & NESTED SCROLL FIX REPORT

**Status**: VERIFIED & COMPLETE  
**Target File**: `apps/admin-web/src/pages/RoutesPage.tsx`  
**Completion Code**: `BUILD_6_1_2A_ROUTE_MODAL_OVERFLOW_FIX_COMPLETE`  

---

## 1. Root Cause Identified

1. **Absence of Tailwind Runtime Utilities in Vanilla CSS Project**:  
   `admin-web` is built with Vanilla CSS (`index.css`) without Tailwind CSS compilation. In Build 6.1.1, flex and layout properties were applied using Tailwind utility class names (`flex-1`, `min-h-0`, `overflow-y-auto`, `shrink-0`, `p-6`, `space-y-6`), which had no matching definitions in `index.css`. Consequently, flex parents defaulted to `min-height: auto; flex-shrink: 1;` and lacked `overflow-y: auto`, preventing the modal body from scrolling.
2. **Dual Nested Vertical Scrolling Traps**:  
   The Ordered Intermediate Stops sub-section previously had an internal scroll container with `maxHeight: "260px"` and `overflow-y: auto`. Combined with the outer modal viewport clipping (`maxHeight: calc(100vh - 32px)`), this created two conflicting scroll contexts. Mouse wheel pointer events became trapped inside the 260px intermediate stop container, while dropdown menus and action controls clipped or overlapped outer elements.
3. **Improper Flex Containment on Form Container**:  
   The form element lacked explicit flex column styling and `min-height: 0`, preventing the inner body from scrolling properly between the header and footer.

---

## 2. Files Changed

1. [`apps/admin-web/src/pages/RoutesPage.tsx`](file:///d:/GoBus/Transit%20Pulse/transit-platform/apps/admin-web/src/pages/RoutesPage.tsx):
   - Refactored the Create Route dialog to enforce strict Flexbox hierarchy:
     - Outer Dialog: `maxHeight: calc(100vh - 32px); display: flex; flexDirection: column; overflow: hidden;`
     - Fixed Header: `flexShrink: 0;` (fixed at the top, does not scroll)
     - Form: `flex: 1; minHeight: 0; display: flex; flexDirection: column; overflow: hidden;`
     - Modal Body: `flex: 1; minHeight: 0; overflowY: auto; overflowX: hidden;` (**ONE PRIMARY VERTICAL SCROLL CONTAINER ONLY**)
     - Fixed Footer: `flexShrink: 0;` (fixed at the bottom, does not scroll or overlap)
   - Completely eliminated internal `maxHeight: 260px` and `overflow-y-auto` from the Ordered Intermediate Stops list.
   - Preserved Ordered Stop Sequence as a distinct, unified card that expands naturally in document flow.

---

## 3. Outer Modal Scrolling Behavior

```
CREATE ROUTE MODAL
┌────────────────────────────────────────────────────────┐
│ FIXED HEADER (flexShrink: 0) — Title & Close [X]       │
├────────────────────────────────────────────────────────┤
│                                                        │
│ GENERAL DEFINITION CARD                                │
│                                                        │
│ ORDERED STOP SEQUENCE CARD                             │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Start Stop (Sequence 1)                            │ │
│ │ 2. Stop  [Select Stop] [↑] [↓] [Delete]            │ │
│ │ 3. Stop  [Select Stop] [↑] [↓] [Delete]            │ │
│ │ ...                                                │ │
│ │ 40. Stop [Select Stop] [↑] [↓] [Delete]            │ │
│ │ End Stop (Sequence Final)                          │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ ROUTE CALCULATION CARD (Road Distance, Duration)       │
│                                                        │
│ MAP PREVIEW CARD (Leaflet Polyline & Markers)          │
│                                                        │
│           ONE PRIMARY MODAL SCROLL (↕)                 │
├────────────────────────────────────────────────────────┤
│ FIXED FOOTER (flexShrink: 0) — [Cancel] [Create Route] │
└────────────────────────────────────────────────────────┘
```

- **Single Scroll Mechanism**: The entire body between the fixed header and fixed footer scrolls as a single unified container (`overflow-y: auto`, `overflow-x: hidden`).
- **Scroll Isolation**: Mouse wheel and touch events operate predictably regardless of cursor position; there are zero child scroll containers to hijack mouse wheel events.

---

## 4. Ordered Stop Section Behavior

- **Card Visual Integrity**: The Ordered Stop Sequence remains housed in its own card (`background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px;`).
- **Flow Positioning**:
  - `START STOP (Sequence 1)` is anchored at the top of the card with an emerald visual indicator.
  - `INTERMEDIATE STOPS` flow sequentially with clear numbering (`2.`, `3.`, etc.), full stop dropdowns, and aligned action buttons (`↑`, `↓`, `🗑`).
  - `END STOP (Sequence Final)` is anchored at the bottom of the card with a rose visual indicator.
- **Natural Expansion**: The card dynamically grows to accommodate any number of stops (from 2 up to 40+ stops).

---

## 5. Confirmation: Internal Vertical Scrolling Removed

- The intermediate stop container has **NO** `max-height` restriction.
- The intermediate stop container has **NO** `overflow-y: auto` or `overflow: scroll`.
- There is **exactly ONE vertical scrollbar** visible across the entire modal (on the modal body).

---

## 6. Header and Footer Behavior

- **Fixed Modal Header**: Styled with `flexShrink: 0`, `padding: 18px 24px`, and `border-bottom: 1px solid var(--border)`. Remains pinned at the top regardless of scroll position.
- **Fixed Modal Actions Footer**: Styled with `flexShrink: 0`, `padding: 16px 24px`, and `border-top: 1px solid var(--border)`. Remains pinned at the bottom with route calculation summary text and actionable `[Cancel]` and `[Create Route]` buttons. Content never overflows behind or beneath the footer.

---

## 7. Overflow & Z-Index Safety

- Replaced arbitrary `z-index` values (`z-10`, etc.) with proper Flexbox layout boundaries. Header, body, and footer are flex siblings in normal stacking context.
- Added `minWidth: 0` to flex child `<select>` elements on intermediate stop rows to ensure long stop names never cause horizontal overflow or push action buttons off-screen.
- Pinned sequence numbers and action button clusters with `flexShrink: 0` to prevent button squishing.
- Added `overflowX: hidden` on the modal body to guarantee zero horizontal layout shifts.

---

## 8. Responsive Verification

Layout verified across standard breakpoints:
- **1366 × 768** (Laptop): Modal height constrained to `calc(100vh - 32px)` (736px max); header and footer remain fully visible and sticky, body smoothly scrolls through 30+ stops without clipping.
- **1440 × 900** (Desktop Standard): Body accommodates General Definition, Ordered Stops, Route Calculation, and Map Preview with ample viewport breathing room.
- **1920 × 1080** (Full HD Desktop): Optimal full-width card layout with multi-column grids for route properties and road distance calculation metrics.

---

## 9. UI Tests Performed

1. **Modal Open / Dismiss**: Verified click on `+ Create Route` opens the modal; verified clicking `Cancel` or `[X]` dismisses cleanly without altering state.
2. **Intermediate Stop Add / Remove**: Tested adding 5, 10, and 20 intermediate stops; verified each stop increments sequence count and expands the Ordered Stop card naturally.
3. **Reordering**: Tested `Move Up` and `Move Down` on intermediate stops; verified button disabling on boundaries (top row disabled for `Move Up`, bottom row disabled for `Move Down`).
4. **Validation Unchanged**: Verified `Start != End` validation, duplicate stop prevention, required road calculation before creation, and duplicate route detection remain intact.

---

## 10. Build & Distribution Result

- TypeScript typecheck & Vite production build executed cleanly:
  ```
  $ tsc -b && vite build
  ✓ 1892 modules transformed.
  dist/index.html                   0.45 kB
  dist/assets/index-BRqOrFYf.css   23.59 kB
  dist/assets/index-Zmpls_hz.js   555.19 kB
  ✓ built in 1.72s
  ```
- Assets updated in Caddy web server container:
  ```
  docker cp apps/admin-web/dist/. demo-transit-admin-web:/usr/share/caddy/
  ```
- Public Cloudflare Quick Tunnel and local Caddy verified serving HTTP 200 OK:
  - Localhost: `HTTP/1.1 200 OK` (Last-Modified: Thu, 03 Sep 2026 23:48:06 GMT)
  - Remote Tunnel: `https://warming-milan-gtk-dynamic.trycloudflare.com` (`HTTP/1.1 200 OK`)
- Backend Test Suite:
  - 52 tests executed and passed (`52 passed in 35.71s`).

---

## 11. Confirmation: Live Database Clean & Unmodified

Live product database (`transit_platform`) audit:
```sql
SELECT 'stops' as table_name, count(*) FROM stops 
UNION ALL SELECT 'routes', count(*) FROM routes 
UNION ALL SELECT 'route_stops', count(*) FROM route_stops 
UNION ALL SELECT 'services', count(*) FROM services 
UNION ALL SELECT 'vehicles', count(*) FROM vehicles 
UNION ALL SELECT 'trips', count(*) FROM trips 
UNION ALL SELECT 'stop_aliases', count(*) FROM stop_aliases 
UNION ALL SELECT 'organizations', count(*) FROM organizations;
```
**Results**:
- `stops`: 49 (Real Kolkata Transit Authority Stop catalog preserved untouched)
- `routes`: **0**
- `route_stops`: **0**
- `services`: **0**
- `vehicles`: **0**
- `trips`: **0**
- `stop_aliases`: 9
- `organizations`: 1 (Kolkata Transit Authority)

Zero real or test routes exist in the live database.
All existing real stops remain 100% untouched.

---

BUILD_6_1_2A_ROUTE_MODAL_OVERFLOW_FIX_COMPLETE
