# Design System Strategy: The Sovereign Auditor

## 1. Overview & Creative North Star
**Creative North Star: "The Sovereign Auditor"**
This design system moves beyond the generic "SaaS Dashboard" to create an environment of absolute precision and quiet authority. For a CPA AI Agent, the interface must feel like a high-end, digital private office—private, focused, and immutably accurate. 

We achieve this through **"Atmospheric Depth."** Rather than using white lines to box in data, we use tonal shifts and light-bleed to create a sense of infinite space. The design breaks the rigid, "templated" look by using intentional white space, asymmetric data clusters, and high-contrast typography scales that prioritize legibility over decoration.

---

## 2. Colors: Tonal Architecture
The palette is built on a "Dark Matter" foundation, using deep indigo-blacks to provide a canvas where critical financial alerts can "pop" without overwhelming the user.

### The Color Palette
- **Core Surfaces:** `background` (#0e0e13), `surface` (#0e0e13).
- **The Primary Action:** `primary` (#a8a4ff) — An electric, glowing indigo that signifies the AI’s active intelligence.
- **The Tonal Scale:** Use `surface_container_low` (#131319) through `surface_container_highest` (#25252d) to define hierarchy.

### The "No-Line" Rule
**Explicit Instruction:** Prohibit 1px solid borders for sectioning. Structural boundaries must be defined solely through background color shifts. A `surface_container_low` card sitting on a `background` provides all the separation needed. If a visual break is required, use a 48px vertical gap rather than a horizontal line.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. 
- **Tier 1 (Base):** `background`
- **Tier 2 (Navigation/Search):** `surface_container_low`
- **Tier 3 (Primary Data Cards):** `surface_container`
- **Tier 4 (Modals/Pop-overs):** `surface_container_high`

### The "Glass & Gradient" Rule
To elevate the experience, use **Glassmorphism** for floating elements (like the AI Command Bar). Apply `surface_variant` at 60% opacity with a `backdrop-blur(20px)`. Main CTAs should utilize a subtle linear gradient: `primary_dim` to `primary`.

---

## 3. Typography: Editorial Precision
The typography system uses a dual-font approach to separate narrative insights from technical financial data.

- **Headings (Inter):** Set to **Bold** with a **-0.02em tracking**. This "tight" setting creates an editorial, premium feel used in high-end financial journals.
- **Technical Data (JetBrains Mono):** All currency values, tax codes, and ledger entries must use JetBrains Mono. This provides a "tabular-numeric" feel that reassures the user of the AI's mathematical rigor.

### Typography Scale
- **Display (L/M/S):** Used for total portfolio value or high-level summaries. (3.5rem - 2.25rem).
- **Headline (L/M/S):** Section starters. Always Inter Bold.
- **Title (L/M/S):** Sub-section headers.
- **Body (L/M/S):** Default reading size. Use `body-md` (0.875rem) for most text to maintain a dense, professional feel.
- **Label (M/S):** For metadata and technical labels in JetBrains Mono.

---

## 4. Elevation & Depth: Tonal Layering
Traditional structural lines are replaced by **Tonal Layering**.

### The Layering Principle
Depth is achieved by stacking tiers. Place a `surface_container_lowest` (#000000) card inside a `surface_container_low` (#131319) section to create a "recessed" effect for secondary data.

### Ambient Shadows
For floating elements, use "Ambient Shadows":
- **Blur:** 40px - 60px
- **Opacity:** 4%-8%
- **Color:** Use a tinted version of `surface_tint` (#a8a4ff) rather than black. This makes the element feel like it is glowing with the AI’s energy.

### The "Ghost Border" Fallback
If a border is required for accessibility (e.g., input focus), use the **Ghost Border**: `outline_variant` at 15% opacity. Never use 100% opaque borders.

---

## 5. Components: Functional Elegance

### Buttons & CTAs
- **Primary:** Gradient from `primary_dim` to `primary`. Text: `on_primary`. Rounded-xl (1.5rem).
- **Secondary:** Surface-only. Background: `surface_container_high`. No border.
- **Tertiary:** Ghost style. `primary` text color, no background until hover.

### Severity Badges (CPA Specific)
Badges use a "Low-Impact" fill to keep the UI clean, but high-contrast text for urgency.
- **Critical:** `error_container` (Low Opacity) background + `error` text/border.
- **High:** `Warning` palette (Orange-tinted).
- **Medium:** `Warning` palette (Yellow-tinted).
- **Low:** `Success` palette (Green-tinted).

### Input Fields
- **Default State:** Background `surface_container_low`, no border.
- **Active State:** Ghost border (20% `primary`) and a subtle inner-glow.
- **Data Entry:** Use JetBrains Mono for all numeric input fields.

### Cards & Lists
**Forbid Divider Lines.** Use vertical white space (from the Spacing Scale) or subtle background shifts. For a list of transactions, alternate between `surface` and `surface_container_low` backgrounds (zebra striping) but with zero-width gutters to make it feel like a single, cohesive block.

---

## 6. Do’s and Don'ts

### Do
- Use **Asymmetry** in dashboard layouts. Let the AI summary take up 65% of the width, with technical logs taking up the remaining 35%.
- Use **JetBrains Mono** for every single dollar sign ($) and decimal point.
- Prioritize **Breathing Room**. If in doubt, double the padding.

### Don't
- **Never use 1px solid white/grey borders.** They break the immersion of the dark theme.
- **Avoid "Pure Black" (#000000) for large surfaces.** Only use it for deep recessed areas (`surface_container_lowest`).
- **Don't use standard icons.** Use thin-stroke (1.5px) custom iconography to match the Inter tracking.

---

## 7. Signature AI Component: The "Audit Pulse"
Create a custom component for the AI's processing state. Instead of a spinning loader, use a subtle, breathing gradient pulse on the `surface_container_highest` background using the `primary` color at 5% opacity. It should feel like the interface is "thinking" rather than "loading."