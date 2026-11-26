# ⬡ PRIME FORMULA — NelloGem Design System v1.0
*The official look for ALL NelloGem projects. Every agent MUST follow this.*

## The Formula (from the prime discovery)
```
PRIMES > 5  →  last digit ∈ {1, 3, 7, 9}
PRIMORIAL   →  2·3·5·7·11·13...  ladder of sieves
```
Applied to design: **order everything by the ladder** (small→large, foundation→advanced), mark sections with the surviving digits **1·3·7·9**, and let density → focus like the sieve density → 0.

## Palette (exact)
| Token | Hex | Use |
|---|---|---|
| `--bg` | `#0d1117` | page background |
| `--panel` | `#161b22` | cards, code blocks |
| `--border` | `#30363d` | borders, dividers |
| `--text` | `#e6edf3` | body text |
| `--dim` | `#8b949e` | secondary text |
| `--gold` | `#f0b429` | PRIMARY accent — headings, markers, links-hover |
| `--blue` | `#58a6ff` | links, h2 |
| `--green` | `#3fb950` | success, h3 |
| `--red` | `#f85149` | danger/warnings |

## Typography
- Body: `system-ui, -apple-system, sans-serif` · line-height 1.65
- Code/labels/markers: `ui-monospace, 'Cascadia Mono', Consolas, monospace`
- Max content width: `860px`, centered, `padding: 0 24px`

## Required page chrome (EVERY html page)
```html
<nav class="pnav">
  <a class="plogo" href="01 - the-project-individual.html">⬡ PRIME</a>
  <span class="pdigits">1·3·7·9</span>
  <a href="00 - PRIME INDEX.html">INDEX</a>
</nav>
```
Footer on every page:
```html
<footer>⬡ NELLOGEM PRIME FORMULA · document NN of 38 · <a href="00 - PRIME INDEX.html">back to index</a></footer>
```

## Components
- **Doc cards** (`a.doc`): `--panel` bg, `--border`, radius 10px, gold border on hover
- **Section headers** (`h2`): blue, top border, preceded by `❖ 1·3·7·9 ❖` motif optional
- **Status pills**: `.pill-ok`(green) `.pill-run`(gold) `.pill-bad`(red) — `border-radius:999px; padding:2px 10px; font:11px mono`
- **Prime divider**: `─ ❖ 1 · 3 · 7 · 9 ❖ ─` as `<hr class="pdiv">` between major sections

## Rules for agents
1. Dark theme ALWAYS — no light pages
2. Gold = attention/identity, blue = navigation, green = done, red = danger
3. Numbered ordering mirrors the primorial ladder: foundations first, advanced last
4. Self-contained HTML — no external fonts/CDN (offline-safe)
5. Every page links back to `00 - PRIME INDEX.html` (the command center)
6. Code blocks: `--panel` bg, gold-tinted text, rounded, scrollable
