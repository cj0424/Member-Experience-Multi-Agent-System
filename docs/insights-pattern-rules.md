# Insights: how patterns are detected and ranked

All numbers live in `evidence/rules.py`. Change them there, and update this file.
`tests/test_engine.py` checks that the code behaves as described here.

## How the work is split

1. **Load** (`evidence/loaders.py`): the week's survey, incident log, staff notes
   and Google snapshot are read into one common shape (ID, source, date, text).
2. **Tag** (`evidence/tagging.py`, Gemini): each entry gets its topics, whether each
   is a complaint (*queja*) or praise (*elogio*), and whether it suggests a safety risk.
   Only a fixed list of topics is allowed. Neutral answers get no tags.
3. **Decide** (`evidence/engine.py`, plain Python, no LLM): counting, rules, scores
   and ranking. Exact and repeatable.
4. **Write** (Insights agent, Gemini): the owner-facing description of each pattern,
   with every evidence ID.

## Sources and storage

| Source | IDs | Stored |
|---|---|---|
| Post-session survey | ENC- | In full |
| Reception incident log | INC- | In full |
| Staff observations | OBS- | In full |
| Google reviews | REV- | Reference only (ID + date). Google's terms don't allow storing review content |

## When a topic becomes a pattern

**What counts as a mention:** one entry that refers to the topic. An entry mentioning
two topics counts once for each. Complaints and praise are counted separately; praise
on a complained-about topic is shown as contradicting evidence.

**Windows:** club sources, the last 28 days up to the run date. Google reviews, the
last 12 months, and only alongside club evidence.

**Main rule.** All of these, inside the windows:
1. At least **1 club mention in the last 28 days** (the problem is current)
2. Mentions on at least **2 different dates** (it recurs; the same event reported twice doesn't count)
3. Either at least **3 mentions** (all sources together) **or** at least **2 of the 4 source types**

**Slow rule** (for quiet, long-running problems): mentions in **3 different calendar
weeks within 90 days**, the most recent within the last 28 days, club sources only.

**Never patterns:** lost items and "other".

## Priority (how urgent)

Each factor goes from 1 (least) to 3 (most):

| Factor | 1 | 2 | 3 |
|---|---|---|---|
| Severity | Comfort (parking, glare, heat, music, towels) | Playing conditions or broken service (sand, dim court, hot water, bookings) | Safety (set per mention by the tagger) |
| Reach | A few people | A group (one court, slot, class) | Almost everyone |
| Frequency | 1–2 mentions | 3–5 | 6+ |
| Recency (newest club mention) | 15–28 days ago | 8–14 days ago | Last 7 days |

Severity and reach have a default per topic (`TOPICS` in `rules.py`).
Slow-rule patterns use frequency 1 and recency 1.

**Score = 2 × severity + reach + frequency + recency** (5–15).
Severity counts double so serious problems outrank frequent annoyances.

| Score | Priority |
|---|---|
| 12–15 | Alta |
| 9–11 | Media |
| 5–8 | Baja |

Safety (severity 3) is **always Alta** and also sent as an **immediate alert**, without
waiting for the rule. A comfort problem tops out at 11 (Media) by design.

## Confidence (how sure)

- **Alta:** 3+ source types, or 6+ mentions
- **Moderada:** any other pattern (including every slow-rule pattern)

## Also reported

- **Strengths:** praise that meets the same rule. Listed separately, ranked by mentions, no score.
- **A vigilar:** 2+ mentions that don't meet the rule, or 1 mention of severity 2.
  Shown to the owner; no plan is made.

## Why these numbers

Tested with `scripts/generate_week_plan.py` over 500 simulated 4-week periods:
the rule detects the persistent conditions most of the time (parking and sand ~95%,
court 12 ~77%, outside lights ~67%) while random one-off problems rarely pass
(e.g. loud music ~4%). A 42-day window caught slightly more but doubled the noise;
14 or 21 days missed too many quiet problems. Dropping the "2 source types" option
lost ~10 points on quiet problems without reducing noise.

This checks the rule against our own simulation assumptions, not real data.
A pilot, and the eval set, are the real test.
