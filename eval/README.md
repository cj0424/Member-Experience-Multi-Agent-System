# Evaluation set

Fixed cases that measure the AI parts of the system, run several times so the
numbers show both **accuracy** and **consistency** (Gemini doesn't answer
identically every time).

```
python scripts/run_eval.py                 # everything
python scripts/run_eval.py --part outcome  # tagging | outcome | kits
python scripts/run_eval.py --runs 2        # fewer runs: cheaper, quicker
python scripts/run_eval.py --trial         # 1 case per part, 1 run (~4 calls): checks it works
```

| Part | Cases | Answer key | Metrics |
|---|---|---|---|
| **Tagging** (Insights) | Every club entry of the analysed weeks | The simulation plan — what the generator decided happened, independent of Gemini | Complaint recall and precision, praise accuracy, consistency across runs |
| **Outcome Check** | `cases/outcome_cases.json`: the 5 real Phase 3 check-ins + 5 hard cases (season change, no data, not done, failed approach, real contradiction) | Acceptable decision(s) per case, from the rules in the agent's prompt | Accuracy, preferred-decision rate, consistency |
| **Plans + kits** | `cases/plan_kit_cases.json`: heat (seasonal), sand (workload), parking (member messages) | The kit rules | Rule compliance per check |
| **Cost and time** | This run's Gemini calls (`llm_calls`) | — | Calls, retries, seconds and cost per agent |

**Limits:** all cases come from simulated data (see `data/SIMULATION_ASSUMPTIONS.md`), so
the results show the agents work correctly on realistic inputs, not how accurate they would
be on real members' writing. The plan/kit checks are text heuristics (they catch rule breaks, not
overall quality — the full outputs are saved in the `.json` for manual review).
The eval reads the data folders but never writes to the club's data in Supabase.

Reports are saved in `eval/results/` (`.md` summary + `.json` raw results).
