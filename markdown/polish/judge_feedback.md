# Judge Feedback — Compliance Change Radar

**Verdict going into finals: borderline. Here's exactly why.**

---

## First Impression

The one-liner is doing too much work. "We search for specific regulations and vendor policies (across multi-step flows and multiple URLs), detect changes, diff and summarize impact, then auto-create a Jira/Linear ticket with an evidence bundle — so compliance teams see what changed and why it matters, without manual page checks."

That's 44 words. A one-liner is one sentence that makes me lean forward. This made me lean back and re-read it. If you open your demo with this, you've already lost the room.

Try: **"We're a compliance radar — describe your product, and we automatically watch every regulation and vendor policy that affects you, and ticket your team the second something changes."**

---

## Score Breakdown

### Impact Potential — 28/40

The problem is real. 200 regulatory updates a day is a genuinely painful number and compliance teams are genuinely overwhelmed.

But here's my problem: **your two stats are from Thomson Reuters and Risk & Compliance Magazine — both of which are companies that already do this.** You just cited your competition as proof of need. That's a red flag, not a green light. Where's the evidence that existing tools are failing? What's the gap?

Who is your customer, specifically? "Compliance / Legal lead" is not a customer. Is this for a 15-person fintech startup that can't afford Thomson Reuters? A Series B health-tech company navigating HIPAA? A crypto exchange drowning in multi-jurisdictional rules? Each of those is a completely different product. You haven't told me which one you're building.

The use case is believable. The customer is not yet real to me.

### Creativity — 14/20

Using browser agents to navigate multi-step regulatory sites rather than scraping fixed URLs is genuinely the right insight. Regulatory sites are notoriously hostile to automation — they have JS-heavy forms, login walls, pagination, and no APIs. A browser agent that handles all of that is a smart architectural choice and a real differentiator over legacy RegTech tools.

That said, "compliance monitoring + auto-ticket" is a known category. You need to make the demo feel like something I've never seen before, not just a better version of what already exists.

### Technical Difficulty — 15/20

The orchestrator-subagent architecture is solid and appropriate. Retries, self-healing, hash-based diffing, evidence bundles — these are the right engineering instincts.

My concern: you have a lot of open questions that are actually fundamental product decisions. "How the orchestrator assigns search tasks and URL sequences to subagents" and "exact schema for product description → suggested watches" are not future work. Those are the core of your product. If you haven't built them yet, your demo is going to be a happy-path prototype, and I'm going to ask an off-script question that breaks it.

### Demo & Presentation — 10/20

Section 10 is your demo moment: *"We search for the regulation, traverse the multi-step flow across several URLs; within ~20 seconds we have diff + memo + ticket + evidence screenshots + hash."*

That's a **backend plumbing demo.** I'm watching a spinner for 20 seconds and then seeing a Jira ticket. Where's the wow? Where's the moment where I feel the pain before you solve it?

Here's what a strong demo looks like for this product:
1. Open with a real scenario — "Last week, the CFPB updated their guidance on buy-now-pay-later. A compliance analyst at a fintech found out two weeks later from a lawyer. That cost them $40k in legal fees."
2. Show me your product catching that change automatically, the moment it happened.
3. Show me the ticket it created, with the diff and the impact memo already written.
4. Ask me: "Would you rather find out from a lawyer, or from this?"

That's the demo. Right now you have the plumbing described but not the story.

---

## The Thing That Bothers Me Most

The phrase **"judge-friendly and audit-ready"** appears three times in your PRD.

You wrote your product requirements document with judges in mind. That means you are optimizing for my approval, not for your user's workflow. A compliance analyst does not care whether something is "judge-friendly." They care whether it saves them three hours on a Tuesday morning. Write for them, not for me.

---

## What You Need to Fix Before You Present

1. **Nail the one-liner.** One sentence, no jargon, clear user, clear value.
2. **Name your customer.** Pick one specific persona at one specific company type. "A compliance analyst at a Series A fintech" beats "compliance / legal lead" every time.
3. **Reframe your stats.** Don't cite Thomson Reuters. Find a customer quote, a Reddit thread, a Blind post — something that shows existing tools are failing real people.
4. **Find your wow moment in the demo.** The diff appearing is not the wow. The ticket being created is not the wow. The wow is that a human would have missed this change entirely, and your product caught it.
5. **Answer your open questions before you present.** If a judge asks "how does the orchestrator decide which regulations to watch for my product?", you need a crisp, confident answer — not "that's future work."

---

## Bottom Line

The underlying insight is good. Browser agents for regulatory monitoring is a real idea with real pain behind it. But right now this reads like a well-written PRD for a product that doesn't exist yet. In 4 minutes, I need to see it exist. Show me a live watch catching a real change on a real regulatory site, producing a real ticket, and I'll move you to the top of my list.

Right now you're in the middle of the pack. That's fixable before 10 AM.
