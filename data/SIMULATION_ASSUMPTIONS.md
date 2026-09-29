# Simulation assumptions

The club's own sources (post-session survey, incident log, staff notes) are
simulated. To avoid planting patterns, nobody writes them freely. Instead:

1. The rules below are written down first.
2. `scripts/generate_week_plan.py` applies them with a fixed random seed
   (the week's start date, e.g. 2026-09-14 → 20260914) and decides what
   happens: how many entries, on which day, from which source, about what.
3. Only the wording of each entry is written by hand, one per slot, without
   changing what the slot says.

Anyone can re-run the script and get the same plan. Google reviews are not
simulated: they are real, anonymised reviews, selected by a fixed rule (A8).

All numbers are assumptions, not measurements. A real pilot would replace
them with the club's actual data.

## A1. Survey volume
About 12 courts, ~6 bookings per court per day, 4 players each → roughly
2,000 player visits a week. A QR survey at reception gets a low response
rate (~0.5–1%), so **about 15 answers a week on average** (it varies week
to week). Busier days get more answers: weekends ~35% of the week.

## A2. Incident log volume
Reception writes down things that break, run out or go wrong, not every
comment. Each transient event (A6) has its own chance of being logged.
Members also occasionally complain at the desk about a persistent condition
(A5): **about 1 every 2 weeks**. Overall this gives roughly **2 entries a
week on average**, and some weeks none.

## A3. Staff notes volume
Coaches, reception and maintenance write a short weekly note when they
notice something: **about 4 notes a week on average**. Each role tends to
write about different things (coaches: courts and classes; reception:
parking, members, temperature; maintenance: courts and lights). If
something is broken that day, there's a 30% chance the note is about it.

## A4. Tone of survey answers
Most people only fill in a survey when things went fine. Answers without a
problem: **75% positive, 25% neutral** ("bien", "normal"). Positive answers
mention: the club in general (45%), classes or teachers (20%), reception
staff (15%), the atmosphere (15%), the courts (5%). Answers that mention a
problem are "fine, but…" 75% of the time and clearly negative 25%.

## A5. Persistent conditions (real facts about the club)
These come from real public reviews of the club, so they exist every week.
What's assumed is only **how often one survey answer mentions them**:

| Condition | Chance per answer | Why |
|---|---|---|
| Parking full | 10% at peak (weekday evenings, weekend mornings), 2% otherwise | Small car park, only a problem when busy |
| Sand on courts | 4% | Depends on brushing; noticed by some players |
| Court 12 dim | 2% | Only affects players on 1 of ~12 courts |
| Outside lights glare | 2% | Everyone passes them; mildly annoying |
| Indoor temperature | 1% | Seasonal; low in Sept–Oct |
| Low ceilings | 1% | Only matters for lobs; rarely mentioned |

## A6. Transient events (may or may not happen in a week)

| Event | Chance per week | Lasts | Mentioned by an answer that day | Logged by reception |
|---|---|---|---|---|
| Towels run out | 30% | 1 day | 10% | 70% |
| Drinks machine empty | 25% | 1 day | 5% | 80% |
| A match runs over into the next booking | 40% | 1 day | 15% | 90% |
| Music too loud | 20% | 1 day | 8% | 50% |
| Tap or toilet fault | 15% | 3 days | 3% | 80% |
| No hot water | 5% | 5 days | 15% | 90% |
| Playtomic booking error | 10% | 1 day | 5% | 90% |
| Cleaning problem | 15% | 1 day | 6% | 30% |
| Lost item | 35% | 1 day | 0% | 100% |
| Net or door fault | 10% | 4 days | 4% | 60% |

## A7. Effect of an approved plan
When the owner has approved and implemented a plan for a condition,
the chance of it being mentioned drops to **40% of the usual**. It doesn't
disappear: fixes are rarely perfect, and some people still notice.

## A8. Google reviews (not simulated)
The production connector would ask Google for the **newest** reviews, max 5
per call. So each weekly snapshot is the **5 newest real reviews** at that
date, anonymised and paraphrased. The club has had no new review in the
last 8 months, so snapshots don't change between weeks unless a real new
review appears. Exact publish dates aren't available in our copy, so days
are estimated within the real month.

## Known limits
- Rates are assumptions, not measured. A pilot would replace them.
- Written entries are tidier than real handwritten notes.
- The model treats each answer independently; in reality, a bad day
  (e.g. a tournament) affects many answers at once.
