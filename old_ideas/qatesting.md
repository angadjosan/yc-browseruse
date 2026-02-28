**One-liner:** A swarm of browser agents with distinct personas runs through your product and landing flows, measures real conversion and drop-off, and surfaces bottlenecks — all via the Browser Use API.

**In short:** You define personas (e.g. skeptical visitor, price-sensitive buyer, power user). Agents act as those users in a real browser: hit your landing page, signup, and key flows. You get conversion-by-persona and where each persona gets stuck.

---

**QA + swarm testing — personas and bottlenecks**

**What it is**  
Multiple agents, each with a **persona** (goals, skepticism, context), use the Browser Use API to drive a real browser. They don’t just click through — they “decide” like that persona would (e.g. bounce if value isn’t clear, convert if the offer fits). You learn: *Would this persona use your product?* and *Where do they drop off?*

**Personas and conversion**  
- Each agent has a short brief: who they are, what they care about, what would make them convert or leave.  
- Agents land on your page (or funnel entry), read copy and CTAs, and either convert (sign up, add to cart, etc.) or bounce — with a reason.  
- Output: conversion rate **by persona**, not just an aggregate. Example: *Skeptical visitor* 12% signup, *Price-sensitive* 8%, *Power user* 34%.  
- Lets you test messaging and flows against “would they even use this?” and tune for the personas that matter.

**Bottlenecks**  
- Same swarm runs through core product flows (onboarding, key actions, checkout, etc.).  
- Each agent reports where it got stuck: unclear step, broken element, slow load, confusing UI, or dead end.  
- Aggregated: you see which steps have the most drop-off or confusion across personas.  
- Bottlenecks are tagged by type (UX, performance, copy, technical) so you can prioritize.

**Output**  
- **Conversion:** Persona → signup/convert rate + stated reason (e.g. “value not clear”, “price too high”).  
- **Bottlenecks:** Step or screen → count of agents stuck, failure reason, and optional screenshot or selector.  
- Optional: funnel view (landing → signup → first action) with drop-off by persona and by step.

**Why Browser Use API**  
Real browser, real DOM — no headless shortcuts. Agents see what users see (including dynamic content, auth, and client-side state). They can fill forms, click, scroll, and follow links like a human. Swarm = many agents in parallel, so you get distribution across personas and paths without running one long script.

---
