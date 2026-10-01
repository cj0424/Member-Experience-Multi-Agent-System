# From Demo to Pilot

What it would take to run the Member Experience Multi-Agent System at a real padel club, and how to tell whether it helps.

The system has been built and tested on simulated data; why, and what that proves, is explained in [`data/SIMULATION_ASSUMPTIONS.md`](../data/SIMULATION_ASSUMPTIONS.md). A pilot answers the question the simulation can't: **does it improve members' experience at a real club, and will an owner use it every week?**

## What the pilot tests

| Question | How we'd know |
|---|---|
| **Does it find real problems?** | The owner agrees that the detected patterns are real and worth acting on |
| **Are the plans and kits usable?** | Most are approved on the first version, or after one short change |
| **Do the fixes work?** | Complaints about a topic drop after its fix, and Outcome Check's decisions match what the owner sees |
| **Does the owner keep using it?** | The weekly briefing is read, and decisions are made within a few days |
| **Is it worth the cost?** | Running costs stay low compared with the owner's time saved |

## What has to change before the pilot

**1. Real feedback instead of simulated files.** The club's three sources need simple forms that write straight into the database: a short QR survey after each session, an incident form at reception, and a notes form for staff. Each should take under a minute to fill in, or people will stop using it.

**2. Live Google reviews.** The connection to Google's Places API replaces the fixed sample of 5 reviews used in this project. The connection point is already in `evidence/loaders.py`, and reviews stay stored as a reference only.

**3. A weekly schedule.** The weekly job runs automatically every Monday morning, before the team meeting, instead of being started by hand.

**4. WhatsApp instead of Telegram.** A Spanish club runs on WhatsApp. The code already supports it; the weekly briefing needs to become an approved WhatsApp message template, because businesses can only start a conversation with one.

**5. Immediate safety alerts.** A safety risk should reach the owner's phone the moment it's detected, not wait for Monday.

**6. Real users.** The owner and the manager get access through the existing Google login and access matrix. Staff keep contributing through the forms, without logging in.

## Data protection

The pilot would process members' comments, which can contain personal data. Before starting:

* **Members are told** how their survey answers are used, on the survey itself.
* **Only what's needed is collected.** The survey doesn't ask for names, and staff notes describe situations, not people.
* **Retention is defined**, for example deleting raw entries after 12 months and keeping only the patterns.
* **Agreements with the services that process data** (Supabase, Google, the messaging provider) are reviewed with the club, ideally with legal advice.

The system already supports this: Google review text is never stored, access is limited by role, and the database is closed to outside access.

## Duration and setup

| Item | Proposal |
|---|---|
| **Length** | 8–12 weeks: long enough for several fixes to be checked at least twice |
| **Club** | One independent club with an owner and a manager willing to review the app once a week |
| **First 2 weeks** | Forms in use and data flowing; no decisions expected yet |
| **Weekly routine** | Monday briefing → decisions in the app during the week → check-ins about 2 weeks after each kit |
| **Support** | A short weekly check with the owner to collect feedback and fix issues |

## What we'd measure

| Area | Measure | Target |
|---|---|---|
| **Adoption** | Survey answers per week | Enough to detect patterns (around 10+) |
| | Weekly briefings read | Most weeks |
| **Quality** | Patterns the owner agrees are real | Most of them |
| | Plans and kits approved on the first version or after one change | Most of them |
| **Impact** | Complaints per topic, before and after its fix | A clear drop for most closed patterns |
| | Outcome Check decisions the owner agrees with | Most of them |
| **Cost** | Gemini cost per month (from `llm_calls`) | A few euros |

## Cost estimate

| Item | Monthly cost |
|---|---|
| Gemini (weekly runs, plans, kits, check-ins, Pala) | Around €1–5, depending on use |
| Hosting (Streamlit Community Cloud) | €0 |
| Database (Supabase) | €0 on the free tier; around €25 if the club needs the paid tier |
| WhatsApp messages | A few cents per weekly briefing |

## Risks and how to handle them

| Risk | Mitigation |
|---|---|
| **Staff stop filling in the forms** | Keep forms under a minute, and show staff in the Monday meeting what their notes led to |
| **Too few survey answers** | Place the QR code where people finish playing, and keep it to three questions |
| **The owner stops opening the app** | The weekly briefing brings the key decisions to the owner's phone |
| **Real comments are messier than simulated ones** | Re-run the evaluation with real, anonymised entries in the first weeks and adjust the tagging |
| **Personal data in free text** | Clear survey wording, retention limits, and access restricted by role |

## Deciding after the pilot

At the end, the owner and the project review three things: whether the detected problems were real, whether the fixes measurably reduced complaints, and whether the weekly routine was worth the owner's time. If all three hold, the next step is a longer pilot or a second club. If not, the results show which part needs work first.
