# Member Experience Multi-Agent System — Testing & Iteration Log
### Development Record — Phase 1 (Agents 1–4) and Phase 2 (memory, Streamlit app, Pala)
**Project:** Member-Experience-Multi-Agent-System (case study: an independent padel club in Madrid)
**Data note:** the club is not named. Reviews are anonymized and paraphrased; the post-visit survey, club profile, trackers and check-in inputs are simulated — realistic for a Spanish padel club, but not describing any real one.
**Purpose of this document:** a real, dated record of every version each agent went through, what changed, why, and whether it passed — compiled directly from actual development and testing sessions, not written retroactively from memory.

---

## How to read this log

Each agent section lists every version tested, in order. For each version:
- **What changed** — the real edit made
- **Why** — the actual reason (a bug found, a user concern raised, a design gap caught)
- **Result** — Pass / Fail / Rejected, with the real evidence

---

## Agent 1 — Insights Agent

**Role:** reads all reviews, finds real recurring patterns, distinguishes them from one-off noise.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Initial prompt — categorize, find 3+ mention patterns, flag contradictions, list insufficient evidence | First build | **FAIL** — grouped multiple distinct isolated complaints (e.g. dark court + confusing signage) under one vague label in the "insufficient evidence" section |
| v2 | Added explicit rule: list each insufficient-evidence mention individually, never grouped | Direct fix for the grouping bug found in v1 | **PASS** — re-ran, same 3 core patterns held (sand: REV-004/007/008/015; construction: REV-005/006/010/012), insufficient-evidence section now correctly split into individual lines |
| v2 (anonymized data) | Same prompt, dataset switched from real names/verbatim text to anonymized "Socio-XXX" + paraphrased text | Privacy/GDPR concern raised — real reviewer names and verbatim copyrighted text should not be in a public repo | **PASS** — identical core patterns (sand, construction) found with exact same REV-IDs, confirming anonymization didn't lose anything the agent depended on |
| v2 (code fix) | `run_insights_agent()` changed from zero parameters (hardcoded filepath) to accepting `filepath` as a parameter with a default | Required for LangGraph orchestration readiness — a Supervisor node can't dynamically feed data to a hardcoded function | **PASS** — re-ran with default filepath, output equivalent to prior run (2 new patterns surfaced due to normal LLM variance, both legitimate; teaching-quality pattern, general-satisfaction pattern) |

**Status: LOCKED IN — no further changes planned for Phase 1.**

---

## Agent 2 — Action Planning Agent

**Role:** turns a confirmed pattern into a real, scannable recommendation (problem, options, why it matters).

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Basic task-list format: "PLAN — steps 1/2/3" | First build | **REJECTED** — task-level only, no member-experience angle, no business case; user found it "not impactful, not different from what a human would write" |
| v2 | Restructured to formal 3-part "🎯 ESTRATEGIA — 🔧 Solución / 👥 Para los socios / 📈 Para el club" | Add real strategic reasoning (solution + member benefit + club benefit) | **REJECTED on presentation** — reasoning was sound but format read as "consulting deck," didn't match how the real club owner's own review replies are written (short, direct, human) |
| v3 | Same reasoning, delivered as natural language with light headers the model chooses itself ("El problema / Qué se puede hacer / Por qué vale la pena") | Fix the tone mismatch from v2 while keeping the real reasoning | **PASS** — genuinely scannable, natural tone, same real member/business reasoning retained |
| v3 + revision path | Added `run_action_planning_revision()` — owner rejects a proposal before trying it (e.g. "too expensive") | Design always called for a Revise gate; this builds the actual logic | **PASS** — tested with real feedback ("both options too expensive, need very cheap"); revised output genuinely different direction (free ventilation-timing protocol + portable comfort items vs. original HVLS fans/insulation) — not a reworded repeat |
| v3 + outcome path (draft) | Added `run_action_planning_from_outcome()` with `is_urgent` flag for Pivotar vs. Empeorado, including "consider reverting" logic for Empeorado | Agent 4 needed somewhere to route Pivotar/Empeorado results back to | **REJECTED** — user determined Empeorado handling was speculative (never once produced by any real test), and reluctant to have the system immediately re-suggest after causing harm |
| v4 | Empeorado removed entirely. Renamed to `run_action_planning_from_pivot()`. Added explicit risk-check rule to the shared reasoning ("could this cause a side effect?") | Simplify to only what's evidenced; add prevention instead of after-the-fact handling | **BUG FOUND** — risk-check rule and RAG-citation rules were only physically present in `build_prompt`, referenced (not restated) in the other two functions — since each Gemini call is stateless, the rules silently didn't apply in the revision/pivot paths |
| v5 (final) | Introduced `SHARED_RULES` and `CLOSING_FORMAT` constants, fully spelled out in all three prompt functions — no cross-function references | Fix the stateless-call bug found in v4 | **PASS** — re-ran all 3 paths (first-pass, revision, pivot); risk-check reasoning now appears consistently in all three outputs (airflow/ball-trajectory risk, humidity/glass-fogging risk, fan-speed/serve risk) |

**Status: LOCKED IN — 3 entry points (first-pass, revision, from_pivot), committed to GitHub.**

---

## Agent 3 — Execution Kit Agent *(originally "Materials-Ready Agent")*

**Role:** turns an approved recommendation into real, ready-to-use pieces.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 (Materials-Ready) | Fixed 2-slot template: staff instruction + member note | First build | **REJECTED** — too narrow; real approved plans needed different kinds of output (promo text, procurement lists) the fixed template couldn't produce |
| v2 | Explicit list of possible material types (checklist / member message / app text / vendor note) with "choose what applies" instruction | Broaden beyond the 2-slot template | **REJECTED** — still anchored Gemini to a fixed menu; user flagged this wasn't genuinely open-ended, risked forcing future patterns into pre-decided categories |
| v3 (final) | Fully open-ended: Gemini reasons from the approved recommendation's own content, asking itself what's actually needed — no example types listed at all | Genuinely remove the fixed-menu constraint | **PASS** — tested against the real low-cost temperature recommendation; produced a genuinely varied kit on its own: a timed door-opening staff protocol, a real WhatsApp/app promo message (with an honest `[Indicar precio]` placeholder instead of inventing a number), and a weatherstripping procurement list |
| — | Renamed "Materials-Ready Agent" → "Execution Kit Agent" | Clearer name reflecting what the output actually is | Naming change only, no logic change |

**Status: LOCKED IN — no changes needed after v3.**

---

## Agent 4 — Outcome Check Agent *(originally "Follow-Through Agent")*

**Role:** checks whether an approved, executed action actually worked — the continuity loop of the system.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 (Follow-Through) | Simple before/after comparison, 3 states | First build | **REJECTED** — too simple; no distinction between "not enough data" and "mixed evidence," relied entirely on review-mention counting |
| v2 | Added 4th state, `check_number` parameter for multi-cycle awareness | Address "what if this keeps getting checked with no resolution" | **REJECTED (partial)** — still relied solely on review mentions as the only signal; user raised the core concern: reviews are unpredictable, can't be the sole basis |
| v3 | Added aggregate star rating as a second signal, reported alongside mentions | Combine signals per real customer-success industry best practice (confirmed via research) | **REJECTED** — signals were reported side-by-side, not genuinely reasoned together; still didn't solve "what if there's no review data at all for months" |
| v4 | Redesigned around execution-verification (traced to Agent 3's own "Cómo verificar" field) as the primary, controllable signal; reviews became secondary | Direct fix for the "external signals are unpredictable" concern — ties to something the club can actually confirm | **PASS on concept, BUG in execution** — `verification_result` was still just manually-typed test text with no real, defined check behind it; not yet tied to anything concrete |
| v5 | Explicitly tied verification to Agent 3's exact `Cómo verificar` text; added strict relevance-filtering for reviews (must specifically address the pattern, not just be positive) | Ground the primary signal in something real and specific; stop vague reviews from counting as evidence | **BUG FOUND** — Paso 3 (review evaluation) used a rigid count-to-decision lookup table (0/1/2+ reviews), functioning in isolation from the rating signal — reintroduced the "single signal" problem this redesign was meant to fix |
| v6 | Paso 3 rewritten to genuinely synthesize reviews AND rating together, reasoning about whether they converge or conflict, rather than a lookup table | Direct fix for the isolated-signal bug in v5 | **BUG FOUND (2nd)** — decision logic never defined what to do when signals genuinely contradicted each other (named in the reasoning instructions, but no branch existed for it) |
| v6 (Empeorado added) | Added 5th outcome (Empeorado) with "consider reverting" logic, distinct from Pivotar | Handle the "action made things worse" case differently from "no effect" | **REJECTED** — user determined this was speculative (never produced by any real test) and, more importantly, expressed genuine discomfort with the system immediately re-suggesting after causing real harm |
| v7 (final) | Empeorado removed, folded into Pivotar. Missing "contradictory signals" branch added, explicitly routing to Pivotar. 4 final outcomes: Flag / Continuar / Cerrar / Pivotar | Simplify to evidenced need only; close the contradiction-handling gap | **PASS** — tested 3 real scenarios: (A) execution not confirmed → correctly flagged, stopped before evaluating anything else; (B) execution confirmed + review and rating both improve → correctly synthesized both signals together, closed with real cited evidence; (C) execution confirmed + zero relevant reviews + flat rating → correctly pivoted, and generated a genuinely specific hypothesis for why the fix likely failed (redistributing sand ≠ removing excess volume) |

**Status: LOCKED IN — 4 outcomes (Flag/Continuar/Cerrar/Pivotar), committed to GitHub.**

---

## Agent 3 — Post-lock refinements (discovered once real LangGraph testing began)

**Even after Agent 3 was "locked in" above, real end-to-end testing through LangGraph surfaced several additional real gaps — recorded here as their own phase, since they were found through integration testing, not standalone testing.**

| Version | What changed | Why | Result |
|---|---|---|---|
| v4 | Added anti-padding rule: every piece must pass "does this tell the reader something they wouldn't already know" | Real graph output included a piece teaching trained reception staff "how to answer the phone" — genuine filler, not useful | **PASS** — subsequent kits stopped including basic-procedure filler |
| v5 | Added explicit rule: never assume the club can identify/contact specific complaining members; default to a general announcement + a note for the owner | Real kit assumed the club could message "the socios who complained" — no real mechanism exists to identify them from anonymized review data | **PASS** — subsequent kits correctly used general announcements with an optional-contact note |
| v6 | Added explicit rule: never assume pre-existing infrastructure (e.g. an already-configured WhatsApp Business account) without flagging it | Real kit assumed WhatsApp Business quick-replies were already set up — unverified assumption about the club's actual tooling | **PASS** — subsequent kits correctly flagged infrastructure as a prerequisite, not an assumption |
| v7 (PDF added) | Added real `.pdf` generation via `reportlab` for print-and-post pieces, alongside real `.xlsx` generation via `openpyxl` for tracker pieces | Explore whether execution pieces should be real files, not just described text | **PASS technically, REJECTED on judgment** — PDF generation worked correctly, but user determined PDF added real complexity without clear necessity (the club operates digitally; no strong case for printed material specifically) |
| v8 (PDF removed) | PDF generation entirely removed — reportlab import, `build_poster_pdf`, `extract_pdf_specs`, and `PDF_SPEC` format all deleted | Simplification decision — two real, working output types (text + Excel) were sufficient for every real case tested; PDF was solving a problem that hadn't actually appeared | User-directed simplification, not a bug fix |
| v9 | Added anti-redundancy rule: check own prior pieces in the same kit before generating a new one, to avoid two pieces saying the same thing in different formats | Real kit generated near-duplicate content as both a text message AND a PDF poster with the same instructions | **PASS** — subsequent kits stopped duplicating content across pieces |
| v10 | Added descriptive Excel filenames (`safe_filename(spec['titulo'])`) replacing a generic counter (`tracker_1.xlsx`) | Generic counter filenames become meaningless once more than one tracker exists | **PASS** — confirmed real file `Registro_Semanal_de_Cepillado_de_Pistas.xlsx` generated correctly |
| v11 (final) | Added tone rule: internal instructions should use recommending language ("se recomienda que...") rather than commanding language ("debe...") | User review from the owner's perspective — a commanding tone toward staff/self felt presumptuous for an AI-generated suggestion, even when accurate | **PASS, not fully verified** — rule added and committed; real output showed partial adoption (some sentences still direct) — flagged as a minor, non-blocking inconsistency, not retested in isolation |

**Real, substantive concerns raised during Gate 2 review of actual generated kits (not yet turned into prompt rules — noted for future refinement):**
- A real kit invented specific compensation figures (a 20% discount) without any real pricing authority — user determined economic commitments should never be invented by the agent, only flagged as `[a definir por el propietario]`
- A real kit assumed compensation should apply to every booking incident — user determined compensation should be reserved for genuine club/platform-side failures, not automatically triggered
- A real kit described a WhatsApp support channel without specifying who staffs it or during what hours — user determined operational assignments (who, when) should be flagged as an owner decision, not assumed

---

## LangGraph Integration — Graph 1 (`graph.py`)

**Architecture decision:** the system is built as TWO separate graphs, not one. Graph 1 handles new-pattern discovery through to prepared materials (Agents 1-3, two approval gates). Graph 2 (`continuity_graph.py`, in progress) handles time-delayed outcome checking (Agent 4) and loops back into Agents 2-3 only when Pivotar requires a genuinely new attempt. This split reflects that the two workflows have fundamentally different real-world triggers — on-demand discovery vs. scheduled/later check-ins — and forcing them into one continuous graph execution would mean asking "did you finish this yet?" in the same sitting a task was created, which doesn't match reality.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Single node (`insights`), `START → insights → END` | Prove the most basic LangGraph mechanism works before adding complexity | **PASS** — real Insights output printed correctly via `graph.invoke()` |
| v2 | Added `action_planning` node, passing Insights' full raw output directly into Action Planning as one blob | Test real data passing between two agents automatically | **PASS on mechanism, BUG on design** — Action Planning received the ENTIRE analysis (all patterns, contradictions, insufficient evidence) as if it were one pattern; Gemini silently chose which part to focus on rather than the system deciding |
| v3 | Added `extract_confirmed_patterns()` — initially a brittle text-marker split (`"🔍 PATRÓN"`) | Direct fix — one recommendation should be generated per confirmed pattern, deterministically extracted, not left to chance | **PASS but flagged as fragile** — user specifically asked whether this would survive future formatting variance (e.g. real Google Live API data later) |
| v4 | Extraction rewritten as a dedicated, robust Gemini call returning structured JSON, with the original text-marker split kept only as a fallback | Close the fragility gap — content-based extraction survives formatting drift; marker-based extraction doesn't | **PASS** — confirmed working across multiple runs with varying real Insights output |
| v5 | Added ACTIVO/HISTÓRICO tagging directly in Agent 1's own prompt (not this file) + a matching filter in `extract_confirmed_patterns()` to exclude HISTÓRICO patterns entirely | Insights Agent was correctly finding the real construction/renovation pattern, but it was already resolved — sending it to Action Planning every run wasted real API calls on a non-actionable pattern | **PASS** — confirmed via explicit count-matching: "X PATRONES ACTIVOS" printed by the extraction step matched exactly how many patterns actually reached the approval prompt |
| v6 | Added `approval_node` — GATE 1, real `input()`-based Approve/Revise/Discard, real Supabase `.insert()` on approval | Build the first real human-in-the-loop checkpoint — nothing should proceed to materials without explicit approval | **PASS** — tested all three paths in one real run (approve, discard, revise-then-approve) |
| v7 | Fixed: approved rows were being saved with a placeholder name ("Patrón 1", "Patrón 2") instead of the real pattern name | User caught this directly by inspecting the real Supabase table after a test run | **PASS** — `recommendation` state changed from `list[str]` to `list[dict]` carrying both the real name and text; verified real, descriptive names appearing in Supabase afterward |
| v8 | Added `execution_kit_node` — GATE 2, same Approve/Revise/Discard pattern, calling Execution Kit Agent per approved recommendation | Build the second real approval gate from the original design, which had been designed and tested standalone but never actually wired into the graph | **PASS** — real kits generated and gated correctly for multiple different approved patterns in the same run |
| v9 | Added real Supabase `.update()` writing the extracted `Cómo verificar` text into the `verification_method` column, with a loud warning if the update matches zero rows (instead of failing silently) | Agent 4 depends entirely on this field; before this fix it was permanently `null` for anything approved through the graph | **PASS** — confirmed real, non-null verification text appearing in Supabase after Gate 2 approval |
| v10 (final) | Wired in real `.xlsx` tracker generation (`extract_tracker_specs`, `build_tracker_excel`, `safe_filename`) so an approved kit's tracker piece becomes an actual downloadable file, not just described text | Close the "text-only" gap for pieces that are genuinely tabular/repeated-use, identified as a real, distinct output type from communications | **PASS** — confirmed real `.xlsx` files generated with correct, descriptive filenames during real graph runs |

**Real infrastructure bugs caught during this phase (not agent-logic bugs, but genuine environment/tooling issues):**
- Multi-line feedback pasted into PowerShell's `input()` prompt was interpreted as separate commands, breaking the revision flow — fixed by using single-line feedback only
- Generated files initially failed with `FileNotFoundError` because the target `outputs/` folder didn't exist locally — fixed by creating it at the project root
- Generated `.xlsx`/`.pdf` files were initially untracked by `.gitignore` (only `*.xlsx` was excluded, missing the `.pdf` also present) — fixed by ignoring the whole `outputs/` folder

**Status: Graph 1 LOCKED IN — full path (Insights → extraction → Action Planning → Gate 1 → Execution Kit → Gate 2 → real file generation) tested and committed.**

---

## Data refresh — business name genericized, review data refreshed

Partway through this phase, the project's data was substantially refreshed:
- All business-name references removed from filenames (now fully generic, e.g. `padel_club_reviews_anonymized.txt`) to remove the last identifying thread from the anonymization.
- The review dataset was rebuilt from the public review source, keeping only genuinely recent reviews (within ~18 months), correctly excluding several patterns that had gone stale (a 2-year-old no-doors/shouting-monitor incident, an old signage complaint) — reduced from 29 to 24 reviews, a deliberate quality filter, not a data loss.
- A second, fully simulated data source was added: a realistic 1-week post-visit QR survey dataset (17 responses), built using a 3-question format (overall experience / specific problem, if any / one suggested improvement) chosen after researching real CX post-visit survey design practice.

---

## Agent 1 — Dual-source triangulation (post-lock addition)

**Role addition:** treat Google Reviews and the post-visit survey as two genuinely independent evidence sources, each with different biases, and apply stronger confidence when a pattern is corroborated by both.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 (first attempt) | Survey test data deliberately built to echo already-known review patterns (sand, climate) | Prove the triangulation mechanism works when real overlap exists | **REJECTED by user** — test data was circular; of course cross-source confirmation "worked" if the test data was engineered to confirm it |
| v2 | Survey data rebuilt "blind," reasoning fresh about plausible weekly issues, not referencing existing patterns | Genuine test of triangulation on honestly independent data | **PASS but flagged** — user caught that a "cold in September" entry didn't match real Madrid weather (verified: Sept evenings are 14-17°C, not cold) |
| v3 | Weather-implausible entry replaced with a season-appropriate one (evening sun glare) | Direct fix for the factual error | **PASS** — confirmed against real climate data before use |
| v4 (final) | Confidence logic rewritten: 🟢 Alto requires genuinely repeated evidence within EACH source separately (not just presence in both); 🟡 Moderado for 3+ mentions concentrated in one source only | Initial "appears in both = Alto" rule was too loose — a single stray survey mention could inflate confidence; initial fixed-number-per-source rule (e.g. "3 in each") was later found unrealistic since reviews accumulate far slower than survey responses | **PASS** — real run showed correctly calibrated Moderado ratings across the board when evidence was genuinely modest, correctly avoided inflating confidence on thin cross-source presence |

**Status: LOCKED IN — dual-source triangulation tested and working correctly on genuinely independent data.**

---

## Agent 2 — Loyalty/retention RAG addition (post-lock addition)

**Role addition:** a second RAG document (`loyalty_program_best_practices.txt`) for patterns about general satisfaction/retention, distinct from the existing technical maintenance document.

| Version | What changed | Why | Result |
|---|---|---|---|
| RAG v1 | Built from SaaS loyalty-software vendor blogs (Rivo, BLOY, Referrizer, etc.) | First draft of real, cited sources | **REJECTED on source quality** — user asked if these were reputable; research revealed they were vendor content marketing (e.g. Rivo is an e-commerce Shopify loyalty tool, not a fitness authority), not independent sources |
| RAG v2 | Rebuilt using Health & Fitness Association (formerly IHRSA) — a real global fitness-industry trade body — plus genuine peer-reviewed academic research | Real, authoritative, independently-published sources | **PASS on authority, flagged on locality** — user asked if this was Madrid/Spain-specific; it was not, sourced from US/international data |
| RAG v3 (final) | Rebuilt again using real Spain-specific fitness-industry sources (IESPORT, GYM FACTORY, Fitnova, chanojimenez.com), with the international IHRSA finding kept only as one clearly-labeled supplementary point | Genuine Spain-grounding, addressing the locality gap | **PASS** — real, Spain-specific statistics (60% of churn occurs in first 90 days; referrals generate 20-35% of new members; community reduces churn ~60%) confirmed via direct citation checking |
| Prompt v1 | Added a rule: loyalty doc only for pure satisfaction patterns | First integration attempt | **REJECTED** — too binary; didn't allow using loyalty tactics as a genuine complement to a real operational problem |
| Prompt v2 | Added dual-use rule: loyalty doc as PRINCIPAL (pure satisfaction) or COMPLEMENTO (alongside a real fix) — but with a rigid "never combine growth tactics with a capacity-limited problem" ban | Address the dual-use gap found in v1 | **REJECTED by user as too restrictive** — removed a legitimate case where a growth tactic could be adapted (e.g. limited to off-peak hours) rather than banned outright |
| Prompt v3 | Rule rewritten as a genuine reasoning question ("would this add pressure to the same constrained resource — if so, adapt or discard, but don't discard a good idea out of excess caution") | Restore flexibility while keeping the real safeguard | **PASS** — real test (parking pattern) showed the model correctly reasoning through and explicitly rejecting a conflicting tactic, citing the specific reason |
| Prompt v4 (final) | Added a MANDATORY, always-visible traceability line (used as PRINCIPAL / used as COMPLEMENTO / NO APLICA), since the "if considered" wording in v3 allowed silently skipping the check | Close a loophole — user asked directly "did it actually consider this, or just skip it silently" | **PASS** — confirmed in a real graph run: parking's output explicitly showed "NO APLICA" with real reasoning, not a silent omission |

**Real, substantive concerns raised during Gate 2 review of actual generated kits, addressed as prompt fixes:**
- Real kit invented specific compensation figures (a 20% discount) with no pricing authority — rule added: never invent monetary figures, flag as `[a definir por el propietario]`
- Real kit assumed compensation should apply to every incident — rule added: reserve for genuine club/platform-side failures only

**Status: LOCKED IN — loyalty RAG document Spain-grounded and source-verified, dual-use reasoning tested successfully across 5 varied real patterns in a single live graph run (general satisfaction, capacity-limited problem, staff-strength reinforcement, teaching-quality opportunity).**

---

## Agent 4 + Graph 2 (`continuity_graph.py`) — full build and real-world redesign

**Role:** the continuity loop — checks on already-approved, already-executed patterns after real time has passed, closing the loop (CERRAR), continuing to wait (CONTINUAR), trying a new approach (PIVOTAR), or flagging unconfirmed execution (FLAG).

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Basic `outcome_check_node` reading whatever was already sitting in Supabase (no real confirmation step) | First build, reusing Agent 4's already-tested standalone logic | **REJECTED by user** — genuinely no way for real evidence to enter the system; the graph would only ever read stale or empty fields |
| v2 | Added `confirm_execution_node` — a real, human-in-the-loop step asking yes/no and a free-text description | Close the missing-evidence gap | **REJECTED by user as still too weak** — "yes/no" alone isn't real evidence; user specifically wanted real proof (an uploaded/read tracker, a specific description), not a bare claim |
| v3 | Added `read_real_tracker_evidence()` — genuinely opens and reads a real, filled `.xlsx` file's actual rows using `openpyxl`, plus a 3-tier evidence system (real signed tracker / personal observation / verbal relay, ranked by credibility) | Ground evidence quality in real, established practice — researched real corrective-action verification standards (named person + timestamp + signature is the real, credible format) | **PASS** — confirmed working in a live run: Agent 4's Paso 1 explicitly cited "4 entradas... firmadas por los responsables," proving the real file was read, not just referenced |
| v4 | Split Agent 4's reasoning into 5 flat sequential steps (was previously conflating "did it happen" with "did it work" evidence in the same step) | User caught that evidence-tiering (a signed tracker) was being applied to the wrong question — tiering proves EXECUTION, not EFFECTIVENESS, which needs a different, separate kind of evidence | **PASS after 2 corrections** — first fix moved tiering to the correct step (Paso 1); user also caught an unrealistic nested-numbering idea (3a/3b/3c) that was rejected in favor of staying flat (Paso 1-5), matching the proven pattern already used elsewhere in the system |
| v5 | Added Paso 2 explicit comparison: reasoning about needed timeframe must be explicitly checked against the real `cycles_since_approval` number, not just reasoned about abstractly | User caught a real logical gap — the model could correctly estimate "needs 2 weeks" and never actually verify 2 weeks had passed | **PASS** |
| v6 | Added Paso 3: define a pattern-specific success criterion BEFORE looking at any effectiveness evidence, replacing one fixed generic rule applied to every pattern | Researched real CAPA/corrective-action practice — effectiveness criteria should be defined at plan-time, not improvised after the fact from whatever evidence happens to exist | **PASS** — confirmed in live run: sand's criterion (no slip complaints) was genuinely different from teaching's (referral conversions), proving per-pattern reasoning, not a fixed template |
| v7 | Added plain-language "closing story" narrative requirement for both CERRAR and PIVOTAR outcomes | Researched real 2026 "agentic analytics" practice — the current standard is a proactive, human-readable explanation, not a static report or bare verdict; explicitly decided AGAINST building a separate formal document, since that would be the outdated pattern | **PASS** — both real CERRAR narratives in the live test read as clear, natural explanations of the full before/after arc |
| Graph fix | Fixed a real off-by-one bug: `route_after_outcome` escalated at `pivot_count >= 2`, but `action_planning_from_pivot_node` only skipped at `> 2`, meaning an already-escalated pattern could still get a 3rd automatic attempt | Found during a full, deliberate re-audit requested by the user before first real run | **PASS** — both functions aligned to `>= 2` |
| Graph fix | `outcome_check_node` now updates `status` to `closed` when Agent 4 returns CERRAR | Researched real practice — a validated, permanent fix should exit the active monitoring loop, not be re-checked indefinitely; CONTINUAR/FLAG correctly remain `open` | **PASS** |
| Graph bug (found live) | `approval_node`'s "r" (revise) option was never actually implemented — only checked for "a," treating "r" identically to discard, despite the prompt text offering it | Found live, during the actual first full test run, when the user tried to revise a real Pivotar recommendation that reused an idea (vendor parking negotiation) the user had explicitly rejected earlier that same night | **BUG CONFIRMED, FIX WRITTEN** — real revise branch added, reusing `run_action_planning_revision()`, matching Graph 1's already-proven pattern; not yet re-tested after the fix |

**Real, successful full end-to-end test (first complete run of the whole continuity system):**

4 real, distinct scenarios run in a single pass, using genuinely filled evidence (2 real, hand-edited `.xlsx` tracker files read directly by the system, 2 real typed personal-observation accounts):

| Pattern | Target outcome | Evidence used | Actual result |
|---|---|---|---|
| Bar/cafetería renovation | CONTINUAR | Tier 2 (personal observation, 3 days in) | ✅ CONTINUAR — correctly estimated needed timeframe (1-2 more cycles) |
| Sand/court maintenance | CERRAR | Tier 1 (real tracker file, 4 real entries) | ✅ CERRAR — correctly read real file rows, cited specific signed entries |
| Parking capacity | PIVOTAR | Tier 2 (personal observation, no improvement) | ✅ PIVOTAR — correctly generated a genuinely new approach (staggered court timing), though the new recommendation also resurfaced a previously-rejected idea (vendor negotiation) that the system has no memory of rejecting — a real, honest limitation of stateless prompt calls, not a bug in this run itself |
| Teaching/referral program | CERRAR | Tier 1 (real tracker file, 3 real entries incl. 1 non-conversion) | ✅ CERRAR — correctly calculated a real 66% conversion rate from actual file rows |

**All 4 outcomes matched their intended target exactly — the first genuine, full proof that Agent 4's 5-step reasoning correctly discriminates between all four real outcome types using real file-reading, real human input, and real Supabase state.**

**Honest limitations surfaced by this test, worth carrying into future iteration, not yet resolved:**
- CERRAR fired after only 1 week / a small number of real data points (3-4 tracker entries, 1 review comment) for two patterns — functionally correct per the system's own logic, but a real business owner might reasonably want a longer track record before treating something as permanently closed; no minimum-cycle floor currently enforced
- The system has no memory across separate Action Planning calls — a specific idea explicitly rejected once can resurface unprompted in a later, unrelated recommendation, since each prompt is stateless

**Status: Graph 2 (`continuity_graph.py`) BUILT AND SUCCESSFULLY TESTED end-to-end on all 4 real outcome types. One known, found bug (missing revise branch) fixed in code but not yet re-tested after the fix.**

---

## Agent 4 — Retest after the sustained-evidence and revise-branch fixes (Phase 1 lock-in test)

**Two real gaps were found in the first full continuity test above, both fixed, and both re-verified in a genuine second live run — not just patched and assumed correct.**

**Gap 1 — CERRAR firing too early.** Researched real CAPA/corrective-action practice first (confirmed: no universal fixed number of cycles is correct practice — duration must be reasoned per action). Rejected an initial fix attempt that added a hardcoded "at least 2 cycles" rule, since that repeated the same "one fixed number for every case" mistake the research explicitly warned against. **Final fix:** Paso 2 rewritten to reason about TWO separate things per pattern — (a) time for a first genuine effect, and (b) time to confirm the effect is sustained, not a one-time snapshot — both compared explicitly against the real cycle count.

**Gap 2 — `continuity_graph.py`'s `approval_node` missing the "r" (revise) branch entirely**, found live when the user tried to revise a Pivotar recommendation that had resurfaced a previously-rejected idea. Fixed by adding the real revise branch, reusing `run_action_planning_revision()`.

**Retest — same 4 patterns, genuinely advanced to cycle 2 with real, additional evidence (2 new tracker rows added to Sand, 1 new to Teaching, fresh real reviews/ratings provided for all 4):**

| Pattern | Cycle 1 result (before fix) | Cycle 2 result (after fix) | What this proves |
|---|---|---|---|
| Teaching/referral | 🟢 CERRAR (after only 1 cycle, thin evidence) | 🔵 CONTINUAR — explicitly separated "first sign confirmed" from "3-4 cycles needed to confirm sustained" | **Direct, checkable proof the sustained-evidence fix works** — same strong-looking evidence that closed it too early before now correctly holds it open |
| Sand/court maintenance | 🟢 CERRAR (after only 1 cycle) | 🟢 CERRAR — this time explicitly reasoning through both the first-effect AND sustained-confirmation checks, backed by 6 real tracker rows spanning 2 full weeks | **A legitimately earned CERRAR this time**, not a repeat of the premature one — same final letter, genuinely different (correct) reasoning behind it |
| Bar/cafetería | 🔵 CONTINUAR | 🔵 CONTINUAR — correctly distinguished a real early positive sign from proof of sustained adoption | Consistent, correct behavior maintained |
| Parking capacity | 🟠 PIVOTAR | 🟠 PIVOTAR — reinforced by a real rating decline this cycle, correctly generated a new recommendation | Consistent, correct behavior maintained |

**Real, live test of the revise-branch fix:** the new Parking recommendation again included the previously-rejected vendor-negotiation idea (confirming the "no cross-call memory" limitation is real and repeatable, not a one-off). User typed `r` for the first time on this path and gave real feedback ("already rejected this idea, keep only the scheduling option"). **The revise branch executed correctly** — produced a genuinely improved, more detailed version (real staggered-scheduling matrix, named real Spanish booking platforms, added an unprompted transition-period safeguard) with the rejected idea fully removed. Approved, then passed cleanly through Execution Kit Gate 2, generating a real 3-piece kit and a working tracker file.

**Status: Both fixes CONFIRMED WORKING through direct before/after comparison on identical patterns, not just described as fixed. Graph 2 fully re-verified end to end. PHASE 1 LOCKED IN.**

---

## Summary — real bugs caught across all 4 agents, and how each was found

| Bug | Found in | How it was caught |
|---|---|---|
| Grouped insufficient-evidence items under one vague label | Agent 1 v1 | User comparison against real output |
| Cross-function rule reference silently not applying (stateless API calls) | Agent 2 v4 | User-requested audit before locking in |
| Fixed material-type menu constraining Gemini's reasoning | Agent 3 v1-v2 | User explicitly questioned "is this actually flexible" |
| Single-signal (reviews-only) fragility | Agent 4 v1-v3 | User raised real-world concern about unpredictable review volume |
| Isolated review-count lookup reintroducing single-signal problem | Agent 4 v5 | User-requested audit, direct callout of the exact rule |
| Missing decision branch for contradictory signals | Agent 4 v6 | User-requested final audit before testing |
| Loyalty-doc reasoning silently skippable ("if considered" wording had no enforcement) | Agent 2 (post-lock) | User asked directly "did it actually consider this, or just skip it" |
| CERRAR closing after only 1 cycle of thin evidence | Agent 4 continuity retest | User raised concern about premature closure; confirmed via direct before/after retest |
| `continuity_graph.py` missing the revise branch entirely (silently treated "r" as discard) | Graph 2, live first run | Found live when user tried to revise a recommendation and got an unexpected discard instead |

**Pattern worth noting for the portfolio write-up:** every real bug in this system was caught through a deliberate audit step — asking "is this really correct" before testing, not discovered by accident. This iterative, audit-first discipline is itself a demonstrable engineering practice, not just a record of things going wrong. Notably, the two most recent bugs (premature CERRAR, missing revise branch) were both found live, during real end-to-end testing — proof the testing discipline held up even after the system was believed "done."

---

## What's confirmed working, end to end, as of this log — PHASE 1 LOCKED IN

- **Agent 1:** real pattern detection, ACTIVO/HISTÓRICO resolution-awareness, dual-source triangulation (reviews + survey) with calibrated confidence, tested on refreshed, current data
- **Agent 2:** 3 entry points (first-pass, revision, from-pivot), risk-aware, Spain-grounded loyalty/retention RAG with mandatory traceable reasoning, tested across 5 varied real patterns in one live run
- **Agent 3:** genuinely open-ended kit generation, real Excel file output, anti-redundancy and anti-assumption rules, fully wired into Graph 1 with its own approval gate
- **Agent 4:** 5-step sequential reasoning (execution evidence → timing check → success criterion → effectiveness evidence → decision), real tiered evidence including genuine `.xlsx` file-reading, plain-language closure narratives, sustained-evidence requirement before CERRAR — every step confirmed via direct before/after retesting, not just designed
- **Supabase:** real persistent storage, confirmed read/write across both graphs, `status` correctly transitions to `closed` on real resolution
- **Graph 1 (`graph.py`):** complete, tested end-to-end multiple times, real file generation confirmed, committed
- **Graph 2 (`continuity_graph.py`):** complete, tested end-to-end across all 4 real outcome types twice (once before, once after two real fixes), including a fully successful Pivotar → Revise → Approve → Execution Kit chain

**Deliberately, permanently removed from scope (not deferred — a real, considered decision):**
- **Google Places API live review pulls.** The system's core value (evidence-grounded reasoning, human-approved continuity) is fully demonstrated using real, anonymized historical review data plus a realistic simulated survey source; this is a documented boundary of the design, not an unfinished task.
- **A dedicated success-metrics/KPI RAG document for Agent 4.** Researched and deliberately rejected — generic CSAT/NPS/CES benchmarks don't fit Agent 4's actual task (judging one specific pattern's effectiveness against a criterion the pattern's own approved action already supplies), unlike the loyalty RAG case where real, specific, otherwise-unknowable statistics genuinely improved reasoning.

**Honest, carried-forward limitation — real, observed twice, not hypothetical:**
- *(Resolved in Phase 2 — see "Memory model" and "Rejected ideas" below.)* No memory across separate Action Planning calls. A specific idea the user explicitly rejected once (vendor parking negotiation) resurfaced unprompted in a later, unrelated Pivotar recommendation for the same pattern — observed in both the first and second continuity test runs. Mitigated in the moment via the Revise gate (which worked correctly when tested), but not solved architecturally. A real, worthwhile Phase 2 candidate: passing a short "previously considered and rejected" note into future prompts for the same pattern.

**Phase 2 (explicit, deliberate deferral — not required to call Phase 1 complete):**
- Streamlit dashboard
- Chatbot/FAQ layer
- Richer multi-cycle trend analytics
- Cross-call memory of rejected ideas per pattern (see limitation above)

**Honest scope of the "complete" claim, worth stating plainly:** this system's *engineering* — sound reasoning, evidence-grounding, human-approval gates, real dual-source triangulation, and end-to-end continuity across every real outcome type — is genuinely complete and demonstrable. This isn't a claim made once and left untested: two real, meaningful bugs were found through deliberate end-to-end testing *after* the system was first believed done, and both were confirmed fixed through direct, controlled before/after retests on identical patterns, not simply patched and assumed correct. Whether the specific recommendations generated would satisfy a real padel-facility domain expert has not been verified by anyone outside this build process, and that claim is not made.

---
---

# PHASE 2 — Memory, the Streamlit app, and Pala
**Period:** September 2026 · **Last commit:** `c5c6abf` — *"Phase 2: Seguimiento + Historial pages, connected journey, Pala assistant, club profile RAG, memory and calibration fixes"* (21 files, +7,034 / −681 lines)

**Goal of Phase 2:** make Streamlit the only place the owner works (no terminal, no VS Code), and give the system a real memory. Gemini is stateless, so Phase 1's biggest carried-forward limitation — rejected ideas resurfacing, the same pattern rediscovered under a new name — had to be solved through Supabase, not through prompts alone.

---

## Memory model — Supabase becomes the system's memory

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | New `db.py`: every Supabase read/write in one place, keyed by the pattern's **id** (never its name) | Gemini words the same pattern differently from run to run; matching by name was fragile | **PASS** |
| v2 | Before Insights runs, all known patterns (with status) are passed into its prompt; Insights labels each pattern NUEVO / YA REGISTRADO — #id / REAPARECE — #id | Re-running the analysis on the same reviews was creating duplicate patterns | **PASS** — see memory test below |
| v3 | `classify_node` validates Gemini's labels against Supabase by id AND normalized name; an unverifiable "known" claim is shown as "Posible duplicado" and skipped | Don't trust the model's claim that something is known without checking | **PASS** |
| v4 | Discards saved with `status = discarded`; `rejected_ideas` stores the rejected options + the owner's reason | A discarded or rejected idea must never come back as new | **PASS** (a data bug in *how* options were summarized was found later — see "Rejected ideas") |
| v5 | New tables/columns: `insights_runs` (background record of every analysis), `pattern_history` gains `pattern_id`, `attempt`, `event_type`, `insights_run_id` | Every decision becomes an event, so Historial can show the full story | **PASS** |
| v6 | `graph.py` rebuilt with LangGraph `interrupt()` for both human gates (discovery graph + kit graph); no more `input()` | `input()` can't work inside Streamlit | **PASS** |

**Live test (fresh tables):** 5 patterns found → 4 approved (3 after revisions), 1 discarded; `pattern_history` recorded 13 events, `insights_runs` 1 row.
**Memory test:** re-ran the full analysis on the same data → *"No hay patrones nuevos en este análisis"*, all 5 recognized (including the discarded one: *"Lo descartaste en un análisis anterior"*). **0 duplicates.**

### Memory gaps found during kit testing, fixed in `graph.py`
| Gap | Evidence | Fix | Result |
|---|---|---|---|
| Revision memory within one review | Round 2 of "Pedir cambios" could bring back what round 1 rejected | Every revision also receives all earlier rejections from the same review | **PASS** (verified with stand-in agents) |
| Cross-pattern memory | A referral program appeared in two different patterns' plans | New plans receive the actions already approved for other patterns + plans proposed earlier in the same run | **PASS** |

---

## RAG — the club profile (`club_profile.txt`) and the shared loader (`rag.py`)

**Why:** revised kits kept assuming things about the club (tools, channels, staff). The agents needed to know how *this* club works, not generic best practice.

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | Short profile with known facts + "(por confirmar)" | First draft | Superseded |
| v2 | Detailed simulated profile built around the test data (court 12, renovation, parking spaces…) | Showcase personalization | **REJECTED by user** — a profile shouldn't be reverse-engineered from the reviews; it should describe private, internal operations nobody outside the club knows |
| v3 | Rewritten from research into how Spanish padel clubs actually operate: decision/approval thresholds, Monday team meeting, reception shifts + handover, maintenance mornings only, daily SOPs, incident log, 24h cancellation, wallet refunds, WhatsApp level groups, cafetería concession, data rules | Realistic inner workings | **PASS** after review: WhatsApp broadcast list → WhatsApp Community (broadcast lists only reach saved contacts and have a size limit); "climatización" limited to reception/changing rooms. Portfolio/"simulated" mentions removed from the RAG file itself (belongs in the README) |
| v4 | New `rag.py`: technical references (citable as "Fuente") vs. club profile (always included, never cited). Action Planning (3 prompts), Execution Kit (2 prompts) and Outcome Check all receive it | One consistent loader; the profile must never appear as a "Fuente" chip | **PASS** — verified every prompt contains the profile and never lists it as a source |
| v5 | New "TRATAMIENTO" section (tú/usted, for owner and members) that all writing agents follow | Tone should be a club setting, not hardcoded | **PASS** |

---

## Agent 4 + Graph 2 — continuity rebuilt for Streamlit (`continuity_graph.py`)

| Change | Why | Result |
|---|---|---|
| Rebuilt with `interrupt()`, id-based reads/writes | Phase 1 version used `input()` and matched by name | **PASS** |
| Decision read ONLY from the "Decisión:" line | A word like "PIVOTAR" inside the reasoning could trigger a pivot | **PASS** — "No hace falta PIVOTAR" in the reasoning no longer triggers one |
| After an approved PIVOTAR, the old kit/verification is cleared (`start_new_attempt`) | The new plan must get its own kit and its own checklist | **PASS** |
| Discarding a new plan escalates the pattern; attempt numbers stored on every event | Nothing silently lost; Historial can show "Intento 2" | **PASS** |
| Optional `only_ids`, so one pattern can be checked at a time | UX: owners check patterns when each is due, not all at once | **PASS** |

---

## Agent 4 — calibration and language (found in the Seguimiento tests)

**Test setup (realistic timeline):** kits approved Sat 26/09 → assigned at the Monday meeting → work from Tue 29/09 → first check-in ~12/10. Trackers were first filled unrealistically (entries before the task was assigned, referrals before the announcement, a clinic before it was announced) — **rejected by the user and redone** to match the timeline; the clinic tracker was left empty because nothing had happened yet.

| Pattern | Input | Result |
|---|---|---|
| Renovación | Signed referral tracker + owner's check of the tournament list | 🔵 CONTINUAR — high evidence, too early to confirm it lasts. Consistent across 3 runs |
| Arena (before fix) | Signed brushing tracker + "court 3 looks better" + one member: "some sand in the corners" | 🟠 **PIVOTAR — wrong** |
| Arena (after fix) | Same input | 🔵 **CONTINUAR** with a concrete adjustment (brush corners toward the centre) |
| Aparcamiento | Not done yet (waiting for Playtomic support) | 🚩 FLAG — correct |
| Profesorado | Not done yet (first clinic 17/10) | 🚩 FLAG — correct |

| Version | What changed | Why | Result |
|---|---|---|---|
| v8 | Paso 3: success criterion must be realistic ("complaints clearly drop"), never absolute ("cero quejas") | Arena's criterion was "ausencia total" | **PASS** |
| v9 | Paso 5: new MEJORA PARCIAL case → CONTINUAR + small adjustment; PIVOTAR only for a *real* contradiction; "reserve PIVOTAR for when the approach fails, not when it needs a tweak" | One isolated comment was treated as contradictory evidence, costing the pattern one of its two pivot chances | **PASS** — same input, correct decision |
| v10 | One bold highlight per step (shown as lime marker) | Results had no visual anchors | **PASS** |
| v11 | Plain Spain Spanish, speaking to the owner in the club's tratamiento; prompt label "RESULTADO REPORTADO" renamed | Output was administrative ("figura como no confirmado", "reportado"); Gemini was copying the prompt's own label | **PASS** in prompt; to be confirmed on real output in the week 4 test |

---

## Streamlit app — pages and journey

| Page | What it does | Key iterations |
|---|---|---|
| Resumen (`home.py`) | "Tu siguiente paso" (4 action tiles with counts), pattern cards with stage stepper and timeline | Summary box showed the raw evidence dump → now shows the agent's conclusion; timeline "C0/C1" → "Seguimiento 1"; notes for new-attempt and escalated states; numbers moved under "Estado actual de cada patrón" (an unnamed section was confusing; "Cifras generales" rejected as unnatural) |
| 1 · Detectar | Runs discovery graph, review one plan at a time | Distinct dashed "Cambios respecto a tu feedback" style (was indistinguishable from lime highlights) |
| 2 · Preparar | One "Generar kit →" per pattern + "Generar todos" | One global button forced generating everything at once |
| 3 · Seguir | One "Revisar →" per pattern, tiered evidence, tracker upload, decision banner + Paso 1–5 | Step details were wrongly placed in the lime box; "seguimiento 0" → real check-in count; vague "Completa la evidencia" → specific message per evidence type; placeholder no longer suggests typing survey answers (owner wouldn't know them) |
| 4 · Historial | Read-only timeline per pattern, grouped by attempt, which agent produced each event, rejected ideas | Ready-to-send kit texts appeared faded grey (Markdown quotes) → now styled like "Listo para copiar"; line breaks kept |

**Connected journey (all pages):** clickable journey bar with badges, sidebar that follows the journey (`st.navigation`; dashboard moved to `home.py`), lifecycle stepper, one status vocabulary everywhere, navy next-step buttons, visible agent line under each title, "📈 Historia" link only where a decision is made (kept in Seguimiento, removed from Kits as clutter).

---

## Pala — the assistant (`faq_agent.py`, floating "💬 Ayuda" button)

| Version | What changed | Why | Result |
|---|---|---|---|
| v1 | FAQ bot grounded on a built-in manual of the app | First build | **REJECTED by user** — duplicated "¿Qué pasa en esta página?"; noise, not help |
| v2 | Data-aware: reads ALL patterns at once; quick questions (qué hago ahora / cómo va / próximos seguimientos / reunión del lunes / ideas descartadas) + typed questions; "Ir a …" buttons under answers | Do what no single page does | **PASS with 8 issues** found in testing |
| v3 | Owner's check-in comments included as the latest facts; last check-in preferred over the kit's original check; one owner per meeting task; next check-in dates; "Atascado" → "Pendiente" with reason; shorter lines; full rejected list (was cut at 260 chars, hiding "repintar"); plain-language rule | Fix the 8 issues | **PASS** — e.g. now "reclamar la respuesta de Playtomic", "cubrir la última plaza del clinic del 17/10" |
| v4 | "En el club" vs "En la app" separation; owner's dates override calculated dates; each rejected idea with its reason; intro "No cambio nada **en la app**" | Round 2 tests: sent the owner to the app too early; a check-in dated *before* the clinic; reasons missing | **PASS** on all six questions |

**Rejected as noise (user decision):** pattern shortcut buttons and follow-up suggestion buttons — they would grow with every pattern and add a second kind of button under each answer. **Naming:** "Pala" (the padel racket in Spain) for the assistant; the button stays "💬 Ayuda" because it explains itself before clicking.

---

## Rejected ideas — a data bug found through Pala

**Found:** Pala's "¿Qué ideas ya hemos descartado?" listed *approved* ideas as rejected (parking's staggering, profesorado's level meetups) and section titles as ideas ("El punto de partida").
**Why it mattered:** the same list goes to the Action Planning Agent after a PIVOTAR with "never repeat these" — it would have avoided the very plans the owner approved.
**Root cause:** the saved summary included every option of the turned-down version (also the kept ones) and picked up bold section titles.

| Fix | Result |
|---|---|
| Only numbered/bulleted options count as ideas | **PASS** |
| `drop_kept_ideas()`: on approval, remove from the rejected list any idea present in the approved plan (in `create_pattern`, `start_new_attempt`, and the reappear path) | **PASS** — tested on the exact real cases |
| One-off `fix_rejected_ideas.py` (shows before/after, saves only on confirmation) | **PASS** — 2 patterns cleaned in Supabase |

---

## Environment issues (Windows) — not agent bugs, but real blockers

| Issue | Cause | Fix |
|---|---|---|
| Updated files not taking effect (`count_checkins` missing, old "Ayuda" text) | File cards sometimes delivered cached older versions, or pastes weren't saved | Practice adopted: verify every install with `Select-String`; complete files pasted directly in chat when needed |
| 2 · Preparar and 3 · Seguir crashed: *"An Application Control policy has blocked this file"* | Windows Smart App Control blocked `uuid_utils`' compiled DLL (used by LangChain/LangSmith) | Pure-Python `uuid_utils/` in the project root (only `uuid7` is needed); Streamlit loads it first. Verified: LangGraph imports with it |
| `ConnectionResetError [WinError 10054]` in the terminal | Normal Windows asyncio noise when a connection closes | Harmless, left as is |
| Streamlit stuck on "Stopping..." | Slow connection shutdown on Windows | Close the terminal; `Get-Process python \| Stop-Process -Force` if the port stays busy |
| `__pycache__` folders would have been committed | `.gitignore` only covered `agents/__pycache__/` | Added `__pycache__/` and `*.pyc` |

---

## Summary — Phase 2 bugs and how they were found

| Bug | How it was caught |
|---|---|
| Duplicate patterns on every re-run (no memory) | User asked "will it rediscover the same things?" before building more pages |
| Revision and cross-pattern memory gaps (referral duplicated) | User review of real plans |
| Club profile reverse-engineered from test data | User challenged its realism |
| Arena wrongly PIVOTAR on partial improvement | User asked "is this realistic?" on a live result |
| Dashboard summary showing raw evidence; "C0" labels; "seguimiento 0" | User compared screens against expectations |
| Kit texts faded grey in Historial | User asked why some text was grey |
| Pala duplicating page guides | User challenged its value |
| Pala answers ignoring owner's comments, wrong dates, cut lists | Systematic question-by-question testing |
| Approved ideas stored as rejected | Found through Pala's answer — would have affected the agents themselves |

**Pattern worth noting:** most Phase 2 bugs were found by the user asking whether a result was *realistic for a real club*, not whether it ran without errors — the system was technically working in almost every case, but not yet trustworthy.

---

## Status as of commit `c5c6abf`

**Working and tested:** memory across runs · club profile RAG in all writing agents · both graphs with `interrupt()` · all 5 pages connected as one journey · per-pattern Revisar / Generar kit · calibrated Outcome Check · Historial · Pala (6 question types).

**Open items (UX, display only):** section icons by section number; section 3 lime box regardless of title; stray `*` after "Ojo con"; backticks in source chips; full analysis one pattern per line; single `*` in copy boxes; more prominent tracker download button.

**Next — week 4 end-to-end test:** new reviews + survey week on a consistent timeline (simulated story dates vs. real check-in timestamps must line up); two new sources for Insights (reception incident log `INC-`, staff observations `OBS-`); attach survey/review mentions since approval to check-ins automatically; confirm the new plain-language rules on real output; a native Spanish reader to check wording (including whether "FLAG" should become "AVISO").

**Phase 3 (production readiness):** Places API weekly snapshot (5-review limit accepted; Business Profile API rejected as too much setup for a real club), the club's own feedback as the main source (QR survey, incident log, staff notes), weekly scheduler + owner notification, average rating saved automatically, `check_env.py` + pinned `requirements.txt`, deployment to Streamlit Community Cloud (also removes the Windows blocking issues for testers).

**Honest scope:** the system now behaves consistently and realistically across every tested path, but all data is simulated, and whether a real club owner would keep using it every week can only be shown by a pilot.
