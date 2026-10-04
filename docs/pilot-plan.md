# From Demo to Pilot

Pala was built and tested with simulated data from a padel club ([how the data was made](../data/SIMULATION_ASSUMPTIONS.md)). The tests show the system works from start to finish. But they can't show two things: whether Pala makes members' experience better at a real club, and whether an owner would use it every week. A pilot would answer both.

A pilot is a trial at one real club for two to three months. It sits between this demo and a full launch: the demo shows the system works, the pilot shows whether it helps, and only then would it be worth building for many clubs.

This document explains what the pilot needs to find out, what has to change, how it would run, and how we'd judge the results.

## What the pilot needs to find out

| Question | How we'd measure it | Target |
|---|---|---|
| **Does it find real problems?** | How many detected problems the owner agrees are real | Most of them |
| **Are the plans and kits useful?** | How many are approved first time, or after one change | Most of them |
| **Do the fixes work?** | The impact indicators (see below), and how often the owner agrees with Outcome Check | Set with the owner after the first weeks |
| **Will the club keep using it?** | Survey answers per week, and how many weekly briefings are read | About 10 answers a week; most briefings read |
| **Is it worth the cost?** | Gemini cost per month | A few euros |

## What needs to change

### Real feedback

**Short forms.** In the demo, the survey, incident log and staff notes come from simulated files. In the pilot, each one becomes a short form: a QR survey for members after they play, an incident form at reception, and a notes form for staff. Each form should take less than a minute. If it takes longer, people stop filling it in.

**Live Google reviews.** The demo uses the same 5 reviews every week. The pilot connects to Google's live reviews instead. The connection point is already in the code (`evidence/loaders.py`), and only a reference to each review is saved, never the text.

### Running on its own

**Automatic weekly run.** The analysis runs by itself every Monday morning, before the team meeting.

**WhatsApp.** Clubs in Spain use WhatsApp, and the code already supports it. The weekly briefing just needs to be set up as an approved WhatsApp message.

**Safety alerts.** If a safety risk is found, the owner gets a message straight away, not on Monday.

### Real users

The owner and the manager log in with Google, and each sees what their role allows. Staff only use the forms, so they don't need an account.

### Measuring impact

The app already has an impact page (**Historial e impacto**) that shows time to resolution, fixes that worked, how complaints changed, and member satisfaction week by week, with the evidence behind each closed case. In the demo it runs on simulated data, so it can only show that the method works. The pilot runs the same page on real feedback, and adds what the demo can't measure yet:

| Indicator | What it shows | What the pilot adds |
|---|---|---|
| Time to resolution | Weeks from finding a problem to closing it | Real dates, and enough cases for the number to mean something |
| Fixes that worked | How many fixes worked with the first plan | Enough closed cases to see a pattern |
| Complaint change | Complaints after a fix vs the same weeks before | Real members' feedback |
| Member satisfaction | Positive survey answers, week by week | Real survey answers, and the live Google rating |
| Recurrence | How often a fixed problem comes back within 90 days | Needs three months after each fix, so only a pilot can show it |

The first weeks show where the club starts. Then the owner and the project agree on targets, and the numbers are reviewed once a month.

## How the pilot runs

| | |
|---|---|
| **Club** | One independent club, with an owner and a manager happy to use the app once a week |
| **Length** | 8–12 weeks, so each fix can be checked at least twice |
| **Weeks 1–2** | The forms start being used. No decisions yet |
| **Every week after** | Monday briefing → decisions in the app → a check-in about 2 weeks after each kit |
| **Support** | A short weekly call with the owner to hear feedback and fix problems |

## Protecting members' data

Comments can include personal details, so before starting:

- **Members are told** on the survey how their answers will be used.
- **Only what's needed is collected.** The survey doesn't ask for names, and staff notes describe what happened, not who.
- **Old data is deleted**, for example raw comments after 12 months, keeping only the patterns.
- **The services that handle the data** (Supabase, Google, WhatsApp) are checked with the club, ideally with legal advice.

Some of this is already in place: Google review text is never saved, each person only sees what their role allows, and the database can't be accessed from outside.

## Cost per month

| Item | Cost |
|---|---|
| Gemini | About €1–5, depending on use |
| Hosting (Streamlit) | Free |
| Database (Supabase) | Free, or about €25 on the paid plan |
| WhatsApp messages | A few cents per weekly briefing |

## Risks

| Risk | What we'd do |
|---|---|
| **Staff stop using the forms** | Keep them short, and show staff at the Monday meeting what their notes led to |
| **Not enough survey answers** | Put the QR code where people finish playing, and keep the survey to three questions |
| **The owner stops opening the app** | The weekly briefing sends the key decisions to their phone |
| **Real comments are messier than the simulated ones** | Test the system again on real comments (with names removed) in the first weeks, and adjust it |
| **Personal details in comments** | Clear survey wording, deleting old data, and access by role |

## After the pilot

The owner and the project look back at the questions at the top. If the problems were real, the fixes reduced complaints, and the weekly routine was worth the owner's time, the next step is a longer pilot or a second club. After that comes a full launch, which would add what running for many clubs needs: monitoring, backups, support and a simple way to set up each new club.

If the pilot doesn't meet its targets, the results show what to improve first.
