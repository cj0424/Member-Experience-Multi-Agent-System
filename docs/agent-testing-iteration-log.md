# Member Experience Multi-Agent System — Testing & Iteration Log

**Project:** Member-Experience-Multi-Agent-System — a case study for an independent padel club in Madrid.
**Data note:** the club is not named, and all data is simulated. Google reviews are real reviews of a Madrid club, collected by hand, anonymised and paraphrased, and used as a fixed sample. The survey, incident log, staff notes, club profile, trackers and check-in inputs are simulated: realistic for a Spanish padel club, but not describing any real one. Why, and what it means for the results: [`data/SIMULATION_ASSUMPTIONS.md`](../data/SIMULATION_ASSUMPTIONS.md).
**What this is:** a dated record of every version each part of the system went through, what changed, why, and whether it passed — written during development and testing.

**How to read the tables:** *What changed* is the edit made · *Why* is the reason (a bug, a user concern, a design gap) · *Result* is Pass / Fail / Rejected, with the evidence.

## At a glance

| Phase | Goal | Result |
|---|---|---|
| **1** | Build the 4 agents (Insights, Action Planning, Execution Kit, Outcome Check) and connect them in two LangGraph graphs with human approval gates | Full loop working end to end; all 4 outcome types (CERRAR, CONTINUAR, PIVOTAR, FLAG) correctly decided on test scenarios |
| **2** | Give the system memory (Supabase), a Streamlit app as the owner's only tool, a club profile, and an assistant (Pala) | 0 duplicates across re-runs; 5 connected pages; Pala answering 6 question types from live data |
| **3** | Re-test on realistic multi-source data, then make it production-ready: reliability, cost tracking, login, security, weekly briefing, deploy | 5/5 correct check-in decisions on realistic data; live online behind Google login; ~$0.01 per assistant answer |

---
---

# PHASE 1 — The four agents and two graphs
**Period:** September 2026

**Goal:** build four agents that turn member feedback into evidence-backed improvements, with the owner approving every decision.

---

## 1.1 Insights Agent

**Role:** reads all feedback, finds recurring patterns, and separates them from one-off comments.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Prompt: categorize, find patterns with 3+ mentions, flag contradictions, list insufficient evidence | First build | **FAIL** — grouped unrelated one-off complaints (a dark court + confusing signage) under one vague label |
| v2 | Each insufficient-evidence mention listed on its own | Fix for v1 | **PASS** — same 3 core patterns (sand, construction…), one-offs now separate |
| v2 + anonymized data | Reviewers renamed "Socio-XXX", text paraphrased | Privacy (GDPR) and copyright: no real names or verbatim reviews in a public repo | **PASS** — identical patterns found with the same review IDs |
| v2 + parameter | `run_insights_agent()` takes the file path as a parameter | Needed so a graph node can pass data in | **PASS** |

## 1.2 Action Planning Agent

**Role:** turns a confirmed pattern into a scannable recommendation: the problem, the options, why it matters.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Task list: "PLAN — steps 1/2/3" | First build | **REJECTED** — no member angle or business case; "not different from what a human would write" |
| v2 | Formal 3-part strategy (solution / for members / for the club) | Add real reasoning | **REJECTED** — sound reasoning, but read like a consulting deck, not like the owner |
| v3 | Same reasoning in natural language with light headers ("El problema / Qué se puede hacer / Por qué vale la pena") | Fix the tone | **PASS** |
| v3 + revision | `run_action_planning_revision()`: the owner turns a plan down *before* trying it (e.g. "too expensive") | The Revise gate needed real logic | **PASS** — "too expensive" produced a genuinely cheaper direction, not a reworded repeat |
| v3 + pivot (draft) | A path for "worse" outcomes, with "consider reverting" | Somewhere to route failed actions | **REJECTED** — speculative (never produced in any test) |
| v4 | Pivot path only; risk-check rule ("could this cause a side effect?") | Simplify; prevent harm up front | **BUG** — the new rules were written in only one of the three prompts; since each Gemini call is stateless, they silently didn't apply in the other two |
| v5 | `SHARED_RULES` and `CLOSING_FORMAT` spelled out in all three prompts | Fix for v4 | **PASS** — risk reasoning now appears in first-pass, revision and pivot outputs |

## 1.3 Execution Kit Agent *(first called "Materials-Ready Agent")*

**Role:** turns an approved recommendation into ready-to-use pieces (instructions, messages, trackers).

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Fixed template: staff instruction + member note | First build | **REJECTED** — too narrow for real plans |
| v2 | A menu of material types to choose from | Broaden it | **REJECTED** — still anchored Gemini to a fixed menu |
| v3 | Fully open-ended: Gemini decides what the plan actually needs | Remove the menu | **PASS** — produced a staff protocol, a member message with an honest `[Indicar precio]` placeholder, and a purchase list |
| v4 | Anti-padding rule: every piece must tell the reader something new | A kit taught trained reception staff "how to answer the phone" | **PASS** |
| v5 | Never assume the club can contact the members who complained | Reviews are anonymous; there's no way to identify them | **PASS** — general announcements instead |
| v6 | Never assume existing tools (e.g. a configured WhatsApp Business) without flagging them | A kit assumed quick-replies were already set up | **PASS** |
| v7 | PDF generation added next to Excel trackers | Explore printable pieces | **REJECTED** — worked, but added complexity the club didn't need |
| v8 | PDF removed | Text + Excel covered every case tested | Simplification |
| v9 | Anti-redundancy: check the kit's own pieces before adding another | Two pieces said the same thing in different formats | **PASS** |
| v10 | Descriptive Excel file names from the tracker title | `tracker_1.xlsx` meant nothing | **PASS** |
| v11 | Recommending tone for internal instructions ("se recomienda que…") | Commanding language felt presumptuous for an AI suggestion | **PASS** (partly adopted in output) |
| v12 | Never invent money figures or blanket compensation; flag them as `[a definir por el propietario]` | A kit offered a 20% discount with no pricing authority | **PASS** |

## 1.4 Outcome Check Agent *(first called "Follow-Through Agent")*

**Role:** checks whether an approved, executed action actually worked, and decides what happens next.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Before/after comparison, 3 states | First build | **REJECTED** — relied only on counting review mentions |
| v2 | 4th state + check number | Handle repeated checks | **REJECTED** — reviews still the only signal, and they're unpredictable |
| v3 | Star rating added as a second signal | Combine signals | **REJECTED** — reported side by side, not reasoned together |
| v4 | Primary signal: was the action done, traced to the kit's "Cómo verificar"; reviews secondary | Use something the club controls | **PASS on concept** — verification not yet tied to a defined check |
| v5 | Verification tied to the kit's exact text; only reviews about the pattern count | Ground the signal; stop vague praise counting as evidence | **BUG** — a rigid count table for reviews brought back the single-signal problem |
| v6 | Reviews and rating reasoned together | Fix for v5 | **BUG** — no rule for when signals contradict each other |
| v6b | Extra "worse" outcome with reverting | Handle harm | **REJECTED** — speculative |
| v7 | 4 outcomes: FLAG / CONTINUAR / CERRAR / PIVOTAR; contradictions → PIVOTAR | Close the gap; keep only evidenced cases | **PASS** — 3 scenarios: unconfirmed → FLAG (stopped early); both signals improve → CERRAR with cited evidence; no change → PIVOTAR with a specific hypothesis |

A dedicated KPI/benchmark document for this agent was researched and rejected: generic CSAT/NPS benchmarks don't help judge one specific pattern against its own success criterion.

## 1.5 Graph 1 — discovery to kit (`graph.py`)

**Design:** two separate graphs. Graph 1 runs on demand (Insights → Action Planning → gate → Execution Kit → gate). Graph 2 runs later, when it's time to check results. They have different real-world triggers, so they're separate.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | One node: Insights | Prove the basic mechanism | **PASS** |
| v2 | Insights output passed to Action Planning as one block | Test data passing | **BUG** — Action Planning got all patterns at once and chose one by itself |
| v3 | `extract_confirmed_patterns()` by text marker | One recommendation per pattern | **PASS, fragile** |
| v4 | Extraction by a structured JSON call; text split kept as fallback | Survive formatting changes | **PASS** |
| v5 | ACTIVO / HISTÓRICO tagging; resolved patterns filtered out | The finished renovation was sent to planning every run | **PASS** |
| v6 | Gate 1: approve / revise / discard, saved to Supabase | Nothing proceeds without approval | **PASS** — all three paths tested in one run |
| v7 | Real pattern names saved (not "Patrón 1") | Found by inspecting Supabase | **PASS** |
| v8 | Gate 2 for kits | Second approval gate from the design | **PASS** |
| v9 | "Cómo verificar" saved to `verification_method`, with a warning if nothing is updated | Outcome Check depends on it; it was always empty | **PASS** |
| v10 | Tracker pieces become real `.xlsx` files | Some pieces are tables used repeatedly | **PASS** |

## 1.6 Two data sources — Insights triangulation

The review set was refreshed (only reviews from the last ~18 months: 29 → 24) and a second source was added: a simulated one-week post-visit QR survey (17 answers, 3 questions).

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Survey written to echo known review patterns | Test cross-source confirmation | **REJECTED** — circular: the data was built to confirm itself |
| v2 | Survey rebuilt without looking at the review patterns | Honest test | **PASS, one error** — "cold in September" doesn't match Madrid's weather |
| v3 | Replaced with a season-appropriate comment (evening sun glare) | Fix | **PASS** |
| v4 | Confidence rules: Alto needs repeated evidence **within each** source; Moderado for 3+ mentions in one source | "Appears in both" was too loose | **PASS** — correctly calibrated confidence |

## 1.7 Loyalty and retention reference (RAG) for Action Planning

| Version | What changed | Why | Result |
|---|---|---|---|
| RAG v1 | Built from loyalty-software vendor blogs | First draft | **REJECTED** — vendor marketing, not independent sources |
| RAG v2 | Rebuilt from the Health & Fitness Association (formerly IHRSA) and academic research | Authoritative sources | **PASS on authority** — but not Spain-specific |
| RAG v3 | Rebuilt from Spanish fitness-industry sources | Local grounding | **PASS** — e.g. 60% of churn in the first 90 days |
| Prompt v1 | Loyalty document only for pure-satisfaction patterns | First integration | **REJECTED** — too binary |
| Prompt v2 | Principal or complement, with a strict ban for capacity problems | Allow complementary use | **REJECTED** — banned ideas that could be adapted (e.g. off-peak only) |
| Prompt v3 | A reasoning question: would this add pressure to the same limited resource? adapt or discard | Flexibility with a safeguard | **PASS** |
| Prompt v4 | A visible verdict line (principal / complement / no aplica) | The check could be skipped silently | **PASS** |

## 1.8 Graph 2 — the continuity loop (`continuity_graph.py`)

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Outcome Check reads what's already in Supabase | First build | **REJECTED** — no way for real evidence to enter |
| v2 | Human step: yes/no + description | Add evidence | **REJECTED** — a bare "yes" isn't evidence |
| v3 | Reads the filled `.xlsx` tracker; 3 evidence levels (signed record / owner saw it / someone said so) | Credible, established verification practice | **PASS** — cited "4 entradas… firmadas" from the file |
| v4 | 5 separate steps: done? → enough time? → success criterion → evidence of result → decision | Evidence of execution was being used as evidence of effect | **PASS** |
| v5 | Step 2 checks the needed time against the real number of cycles | It could estimate "2 weeks" without checking | **PASS** |
| v6 | Step 3 defines a per-pattern success criterion *before* looking at results | Criteria set after seeing results are biased | **PASS** — different criteria per pattern |
| v7 | A short plain-language story for CERRAR and PIVOTAR | Owners need an explanation, not a verdict | **PASS** |
| Fixes | Escalation threshold aligned (`>= 2`); CERRAR sets the pattern to closed | Found in an audit before the first run | **PASS** |
| Bug (live) | The revise option in Graph 2 behaved as discard | Found when the owner tried to revise a pivot | **FIXED** — revise branch added |

**First end-to-end test** — 4 scenarios in one run, with real filled trackers and typed observations:

| Pattern | Target | Evidence | Result |
|---|---|---|---|
| Bar renovation | CONTINUAR | Owner observation, 3 days in | ✅ CONTINUAR |
| Sand | CERRAR | Tracker, 4 signed entries | ✅ CERRAR |
| Parking | PIVOTAR | Owner observation, no change | ✅ PIVOTAR — but the new plan repeated an idea the owner had rejected earlier |
| Teaching / referrals | CERRAR | Tracker, 3 entries | ✅ CERRAR — 66% conversion calculated from the file |

**Two gaps found and fixed:**
- **CERRAR too early** (after one week of thin evidence) → Step 2 now reasons separately about *time to a first effect* and *time to confirm it lasts*. A fixed "2 cycles" rule was rejected: the right duration depends on the action.
- **The missing revise branch** → added.

**Retest** — same 4 patterns, one more cycle of evidence:

| Pattern | Before the fix | After the fix |
|---|---|---|
| Teaching / referrals | CERRAR after 1 cycle | **CONTINUAR** — "first effect confirmed; 3–4 cycles needed to confirm it lasts" |
| Sand | CERRAR after 1 cycle | **CERRAR** — now backed by 6 signed entries over 2 weeks |
| Bar renovation | CONTINUAR | CONTINUAR |
| Parking | PIVOTAR | PIVOTAR → revised with "keep only the scheduling option" → approved → kit generated |

## Phase 1 — bugs and how they were found

| Bug | How it was caught |
|---|---|
| One-off complaints grouped under one label | Comparing output to the data |
| Rules not applied in 2 of 3 prompts (stateless calls) | Audit before locking in |
| A fixed menu limiting the Kit agent | "Is this actually flexible?" |
| Reviews as the only signal of success | Concern about unpredictable review volume |
| Review count table reintroducing a single signal | Audit of the exact rule |
| No rule for contradictory signals | Final audit before testing |
| Loyalty check skippable in silence | "Did it consider this, or skip it?" |
| CERRAR after one thin cycle | Concern about premature closure; confirmed by retest |
| Revise treated as discard in Graph 2 | Found live |

**End of Phase 1:** both graphs work end to end with approval gates, file generation and Supabase storage; all 4 outcome types verified. **Known limitation:** Gemini has no memory between calls, so a rejected idea can come back in a later plan.

---
---

# PHASE 2 — Memory, the Streamlit app, and Pala
**Period:** September 2026 · **Commit:** `c5c6abf` (21 files, +7,034 / −681 lines)

**Goal:** make Streamlit the only place the owner works (no terminal), and give the system a memory, since Gemini forgets everything between calls.

---

## 2.1 Memory — Supabase as the system's memory

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | `db.py`: all Supabase access in one place, keyed by the pattern's **id**, never its name | Gemini words the same pattern differently each run | **PASS** |
| v2 | Known patterns passed to Insights, which labels each one NUEVO / YA REGISTRADO / REAPARECE | Re-running the analysis created duplicates | **PASS** |
| v3 | Those labels verified against Supabase; unverifiable claims shown as "Posible duplicado" | Don't trust the model's claim without checking | **PASS** |
| v4 | Discarded patterns and rejected ideas stored, with the owner's reason | A rejected idea must never come back | **PASS** |
| v5 | `insights_runs` and an event history per pattern (`pattern_history`) | Every decision becomes an event for Historial | **PASS** |
| v6 | Both human gates rebuilt with LangGraph `interrupt()` | `input()` can't work inside Streamlit | **PASS** |
| v7 | Revisions receive every earlier rejection in the same review; new plans see actions already approved for other patterns | A second revision brought back what the first rejected; one idea appeared in two patterns | **PASS** |

**Memory test:** the full analysis re-run on the same data → "*No hay patrones nuevos*", all 5 recognized, including the discarded one. **0 duplicates.**

## 2.2 Club profile (`club_profile.txt`) and the shared loader (`rag.py`)

Kits kept assuming things about the club (tools, channels, staff). The agents needed to know how *this* club works.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Short profile with "(por confirmar)" items | First draft | Superseded |
| v2 | Detailed profile built around the test data (court 12, parking spaces…) | Show personalization | **REJECTED** — a profile shouldn't be reverse-engineered from the reviews |
| v3 | Rewritten from how Spanish padel clubs actually operate: approval limits, Monday team meeting, reception shifts, maintenance mornings only, incident log, 24h cancellation, WhatsApp Community, café run by an external company | Realistic internal operations | **PASS** |
| v4 | `rag.py`: technical references (citable) vs. club profile (always included, never cited); used by Action Planning, Execution Kit and Outcome Check | One consistent loader | **PASS** |
| v5 | A "TRATAMIENTO" setting (tú/usted) followed by all writing agents | Tone is a club setting | **PASS** |

## 2.3 Continuity rebuilt for Streamlit

| Change | Why | Result |
|---|---|---|
| Rebuilt with `interrupt()` and id-based reads/writes | Phase 1 used `input()` and names | **PASS** |
| Decision read only from the "Decisión:" line | "PIVOTAR" inside the reasoning could trigger a pivot | **PASS** |
| After an approved pivot, the old kit and checks are cleared | The new plan needs its own kit | **PASS** |
| Discarding a new plan escalates the pattern; attempt number stored on every event | Nothing lost; Historial shows "Intento 2" | **PASS** |
| One pattern can be checked at a time | Owners check each pattern when it's due | **PASS** |

## 2.4 Outcome Check — calibration

Tested on a realistic timeline (kits approved → assigned at the Monday meeting → first check-in two weeks later). A first set of trackers had entries dated before the tasks were assigned; they were rejected and redone.

| Pattern | Input | Result |
|---|---|---|
| Renovation | Signed referral tracker + owner's check | CONTINUAR — consistent across 3 runs |
| Sand (before fix) | Signed tracker + "court 3 looks better" + one comment about sand in the corners | **PIVOTAR — wrong** |
| Sand (after fix) | Same input | **CONTINUAR** + a concrete adjustment |
| Parking | Not done yet (waiting for Playtomic) | FLAG |
| Teaching | Not done yet (clinic on 17/10) | FLAG |

| Version | What changed | Why | Result |
|---|---|---|---|
| v8 | Success criteria must be realistic ("complaints clearly drop"), never absolute | Sand's criterion was "no complaints at all" | **PASS** |
| v9 | New "partial improvement" case → CONTINUAR + adjustment; PIVOTAR only when the approach fails | One comment cost the pattern one of its two pivots | **PASS** |
| v10 | One highlight per step | No visual anchors | **PASS** |
| v11 | Plain Spanish in the club's tratamiento | Output sounded administrative | **PASS** |

## 2.5 The Streamlit app

| Page | What it does |
|---|---|
| **Resumen** (`home.py`) | "Tu siguiente paso" (4 action tiles with counts) and one card per pattern with its stage |
| **1 · Detectar** | Runs the analysis; review each plan (approve / ask for changes / discard) |
| **2 · Preparar** | "Generar kit →" per pattern; approved kits with downloadable trackers |
| **3 · Seguir** | "Revisar →" per pattern: evidence level, tracker upload, decision and its 5 steps |
| **4 · Historial** | The full story of each pattern, by attempt, including rejected ideas |

Connected as one journey: a clickable journey bar with counts, a sidebar in the same order, one status vocabulary, and a "¿Qué pasa en esta página?" guide on each page.

## 2.6 Pala — the assistant (`faq_agent.py`, "💬 Ayuda")

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | FAQ bot based on a manual of the app | First build | **REJECTED** — repeated the page guides |
| v2 | Reads all patterns at once; quick questions (what to do now, how the club is doing, next check-ins, Monday meeting, rejected ideas) + typed questions | Do what no single page does | **PASS with 8 issues** |
| v3 | Owner's check-in comments treated as the latest facts; one owner per meeting task; next check-in dates; full rejected list | Fix the 8 issues | **PASS** |
| v4 | "In the club" vs "in the app" separated; owner's dates override calculated ones; each rejected idea with its reason | Second round of tests | **PASS** on all six questions |

## 2.7 A data bug found through Pala

Pala listed **approved** ideas as rejected. The same list goes to Action Planning after a pivot as "never repeat these", so it would have blocked the plans the owner approved. **Cause:** the saved summary included every option of a turned-down version, including the ones kept. **Fix:** only list items count as ideas; ideas in the approved plan are removed from the rejected list; a one-off script cleaned 2 patterns in Supabase. **PASS.**

## 2.8 Environment issues (Windows)

| Issue | Fix |
|---|---|
| Updated files not taking effect | Every install verified before testing |
| Windows Smart App Control blocked a compiled library (`uuid_utils`) | A pure-Python replacement in the project root |
| `__pycache__` about to be committed | Added to `.gitignore` |

## Phase 2 — bugs and how they were found

| Bug | How it was caught |
|---|---|
| Duplicate patterns on every re-run | "Will it rediscover the same things?" |
| Revision and cross-pattern memory gaps | Reviewing real plans |
| Club profile reverse-engineered from test data | Challenging its realism |
| Sand wrongly PIVOTAR on a partial improvement | "Is this realistic?" on a live result |
| Pala repeating the page guides | Challenging its value |
| Approved ideas stored as rejected | Found through Pala's answer |

**End of Phase 2:** memory across runs, club profile in every writing agent, both graphs inside Streamlit, 5 connected pages, calibrated Outcome Check, Historial, and Pala. All data still came from the hand-collected review file and one simulated survey week.

---
---

# PHASE 3 — Realistic data and production readiness
**Period:** September–October 2026 · **Commits:** `5f40f33` (multi-source Insights) → `e502a8e` (production pack) → `8988c82` (weekly briefing by Telegram) · **Live:** Streamlit Community Cloud, behind Google login

**Goal:** (1) re-test the whole system on input that looks like a real club's; (2) make it able to run without the developer: online, secure, affordable, and able to tell the owner what to do without being opened.

---

## 3.1 Realistic data

| Change | What it means |
|---|---|
| **Four sources** | Post-session QR survey (`ENC-`), reception incident log (`INC-`), staff notes (`OBS-`), Google reviews (`REV-`) |
| **Google in the format the Places API returns** | At most 5 reviews per run, stored as a reference only (id + date, not the text, per Google's terms). In this project: 5 real, anonymised reviews from the Phase 1–2 sample, the same every week — real content, simulated timing. A plug-in point is ready for a live connection |
| **Club sources generated, not written to order** | `scripts/generate_week_plan.py`: the seed is the week's start date, frequencies come from written assumptions (`data/SIMULATION_ASSUMPTIONS.md`). The script decides what happens; only the wording is written by hand |
| **Fixes change probabilities** | Once a fix is in place, mentions of that problem become less likely — never impossible |
| **Detection by rules, not by the model** | A pattern needs 2+ different dates and 3 mentions or 2 source types within 28 days, with at least one club source. Priority = 2×severity + reach + frequency + recency (5–15). Safety = always Alta. Gemini only tags each entry and names patterns. 14 unit tests |
| **Clean restart** | Phase 2 data archived in Supabase; the loop re-run from week 1 |

## 3.2 Detection — weeks 1 to 4

| Week | Input (survey · incidents · staff · new Google) | Result |
|---|---|---|
| **1** (14–20/09) | 14 · 0 · 3 · 5 | 1 pattern (glare from outside lights), 2 strengths, 2 "a vigilar" |
| **2** (21–27/09) | 15 · 4 · 4 · 0 | 4 new (parking, sand, court 12, heat); glare recognized and its priority aged 9 → 8; a same-day delay seen by 2 sources stayed "a vigilar" |
| **3** (28/09–04/10) | 10 · 2 · 6 · 0 | 0 new, all 5 recognized; sand confidence rose to Alta (a complaint after its fix); new strength "Atención en recepción" |
| **4** (05–11/10) | 9 · 3 · 7 · 0 | 3 new: class waiting lists (11/15), match overruns (11/15), drinks machine (9/15). Towels: 3 sources, same day → correctly "a vigilar" |

**Result:** every detection matched the written rules; 0 duplicates across 4 runs.

## 3.3 Execution kits

| Kit | What the owner changed | Final |
|---|---|---|
| Glare | The Google reply claimed the fix was done; optional diffusers promised | Approved after revision |
| Parking | Removed asking members to make an effort and announcing a problem most hadn't noticed | Approved after revision |
| Sand | Three full rounds a week is too much for one person → Monday full, Wednesday/Friday corners | Approved after revision |
| Court 12 | No message to all members; maintenance works mornings only | Approved after revision |
| Heat | Added an end condition: only on hot days | Approved after revision |

**Approved on the first version: 0/5. After one revision: 5/5.** Every revision fixed exactly what was asked. Most issues came from context the agent didn't have yet (owner preferences), which was then added to the club profile and the kit rules.

## 3.4 Check-ins — with automatic evidence from the 4 sources

Each check-in now shows "what the sources say since detection" (before/after counts and the mentions); the owner adds only what the sources can't know.

| Pattern | Situation | Evidence | Decision |
|---|---|---|---|
| Glare | 1 complaint before, 0 after | Owner checked (medium) | ✅ **CERRAR** |
| Sand | 2 before, 1 after — on a Sunday, when there's no maintenance | Signed tracker, 6 rows (high) | ✅ **CONTINUAR** + move Friday's round to Saturday |
| Court 12 | 2 before, 1 after: "one light at the back still weaker" | Owner checked (medium) | ✅ **CONTINUAR** + fix that light (under €300) |
| Heat | Complaints changing from heat to stuffy to cold | The manager said so (low) | ✅ **FLAG** — asks for the written check the kit defined |
| Parking | 3 before, 2 after — fix not yet applied (waiting for Playtomic) | Owner saw the email (medium) | ✅ **CONTINUAR** — too early, with a realistic timeline |

**5 of 5 correct, 4 different decisions.** Parking was correctly not pivoted: complaints continue because the fix hasn't reached members yet.

## 3.5 Pala with real check-in data

| Question | Result |
|---|---|
| ¿Qué hago ahora? | FLAG first → check-in adjustments → 3 new recommendations by score → "Esperando: Playtomic" |
| ¿Cómo va el club? | Resolved / progressing / pending, each with its reason |
| Próximos seguimientos | Dates or conditions, and which evidence to bring |
| Reunión del lunes | 5 tasks, one role each; the button and the typed question gave near-identical answers |
| Ideas descartadas | Rejected and postponed ideas told apart, with the owner's reasons |
| ¿Qué pasó con la arena? | A 3-line story with a link to Historial |

## 3.6 Issues found and fixed

| # | Issue | Fix |
|---|---|---|
| 1 | Kit verification box blank when written as a list | Parser reads list items; prompt asks for "(1)… (2)…" |
| 2 | A waiting list in a class counted as praise of the teachers | New topic "class places" + tagging rule; data re-tagged |
| 3 | Pattern names with a time from 2 of 3 mentions ("a las ocho") | Time or place in a name only if most mentions say it |
| 4 | Ideas the owner kept saved as rejected | Previous version, feedback and approved version compared; saved as "Descartado" or "Pospuesto" |
| 5 | A loyalty-guide verdict on every plan, almost always "no aplica" | Reference documents used only when they apply; "Fuente" says which and what it added |
| 6 | All recommendations reviewed at once, lost if the app restarted | The analysis only detects; each pattern waits in Supabase with its own "Generar recomendación →" |
| 7 | Pala showed the automatic source evidence as the owner's words | Stored and shown separately |
| 8 | Pala presented a conditional step as certain | Pala reads the plan text; conditions stay conditional |
| 9 | Pala one step behind the approved kit | The approved kit takes precedence over the plan |
| 10 | Pala missed the check-in adjustments | New "adjustments" category; pending items ordered by score |
| 11 | "Too early" decisions had no next step | One line with the practical next step |
| 12 | A kit sent check results to the shift handover note | Results go in the staff notes, which the system reads |
| 13 | "En seguimiento activo" counted plans without a kit | Counts only patterns with an approved kit |
| 14 | Optional rating fields with no data behind them | Removed; check-ins record who submitted them |
| 15 | Cost underestimated | Thinking tokens counted as output, as Google bills them |
| 16 | An SDK notice on every call in the terminal | Hidden (errors still shown) |
| 17 | A fourth "Decidir más tarde" button next to the three decisions | Replaced by a "← Volver a la lista" link above the recommendation: navigation kept apart from decisions |

## 3.7 Production readiness

| Area | What was added |
|---|---|
| **Reliability** | One gateway for every Gemini call (`agents/llm.py`): 3 attempts, a plain-Spanish message if Gemini is down, nothing saved is lost |
| **Cost and time** | Every call logged (agent, seconds, tokens, retries, cost); owner-only panel on the Dashboard |
| **Login** | Google login (OpenID Connect via `st.login`); only mapped emails get access |
| **Access matrix** | 7 permissions × 2 roles (owner, manager) in one place, visible in the app; staff contribute through the incident log and staff notes |
| **"Ver como Gerente"** | The owner previews the manager's view; actions recorded as "Propietario (como Gerente)" |
| **Database security** | Row Level Security on every table; the secret key used only on the server; no secrets in the Git history |
| **Weekly briefing** | `scripts/weekly_run.py`: analyse the new week → Pala writes the Monday briefing (⚠️ alerts · 📥 decisions in the app · 🔁 check-ins · 🛠️ club tasks · ⏳ on hold) → send → save |
| **Delivery** | Telegram bot for the demo; WhatsApp Cloud API supported in code |
| **Deploy** | Streamlit Community Cloud, Python 3.13 |

| Decision | Reason |
|---|---|
| Google login instead of passwords | No passwords to store or remember; roles come from an email → role map |
| The manager can use Detectar | She runs the club day to day; spending limits already sit in the plans |
| Telegram for the demo | Same flow as WhatsApp without a Meta business setup; WhatsApp stays the production channel |
| A separate Google Cloud project for login | Keeps login settings apart from the project that holds the Gemini key |

## 3.8 Self-check — and a new first-version measurement

Every kit revision in 3.3 had the same causes. Both writing agents now review their own draft before answering:

| Agent | The self-check asks |
|---|---|
| Execution Kit | Does each task fit the shift and workload of whoever does it? Does it ask members for effort, or announce a problem most haven't noticed? Does a seasonal routine say when it stops? Does every message to members announce a concrete change? |
| Action Planning | Do the actions fit staff shifts and workload? Do they avoid asking members for effort? Do seasonal measures say until when? |

Measured on two new patterns (class waiting lists, match overruns), plan and kit each, judged as a realistic owner. Choosing between the options a plan offers counts as a decision, not a correction.

| | Before the self-check | After |
|---|---|---|
| Plans passing on the first version | — | 2/2 |
| Kits passing on the first version | 0/5 | 1/2 |
| **Total** | — | **3/4** |

The one revision was smaller than before: the overruns kit planned the reception round at the exact moment new players arrive at the desk, and didn't offer lost minutes back to the delayed group. Both were fixed in one sentence of feedback.

## 3.9 The numbers

| Metric | Value |
|---|---|
| Patterns detected over 4 weeks | 8, with 0 duplicates |
| Kits approved: first version → after one revision | 0/5 → 5/5 |
| First versions passing after the self-check | 3/4 (plans 2/2, kits 1/2) |
| Correct check-in decisions | 5/5 |
| Pala answer | ~10–12 s, ~9,800 tokens, **~$0.01** |
| Weekly briefing (no new week) | ~$0.01 |
| Gemini price | gemini-3.7-flash, paid tier: $0.75 / $3.75 per million input / output tokens until 31/12/2026 |
| Hosting, login, database, bot | $0 |
| Unit tests | 14 passing |

## 3.10 Setup issues

| Issue | Fix |
|---|---|
| Google rejected the redirect address | Entered under "Authorized redirect URIs", typed by hand (no hidden spaces) |
| Streamlit Cloud couldn't see the repository | Access to private repositories granted; branch `main` |
| Streamlit secrets rejected as invalid | Built from `.env` and `secrets.toml` by one command, straight to the clipboard |
| Repository renamed on GitHub | Remote URL updated |

## Current status

**Live and tested:** 4-source intake · rules-based detection with priorities · one-by-one recommendations saved in Supabase · kits · check-ins with automatic evidence · Pala · retries and cost tracking · Google login, access matrix, "Ver como" · Row Level Security · weekly briefing by Telegram · evaluation set (`eval/`) · architecture doc.

**Not yet done:** demo video · README · automatic Monday scheduling · immediate safety alerts · recording who approved plans and kits.

**Scope:** all data is simulated (see [`data/SIMULATION_ASSUMPTIONS.md`](../data/SIMULATION_ASSUMPTIONS.md)). The system works correctly on realistic inputs across the whole loop; whether it improves a real club's member experience can only be shown in a pilot ([`pilot-plan.md`](pilot-plan.md)).
