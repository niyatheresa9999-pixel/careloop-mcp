# CareLoop MCP
Voice-first medication check-ins for family caregivers, built as a self-hosted MCP server (Streamable HTTP) for Alexa+.

**Track:** Alexa+ | **Mini challenge:** Open Source (MIT). Not medical advice.

## Problem
Millions of adults manage a parent's medications from afar. Missed doses are common and caregivers find out too late. Elderly users prefer voice over apps.

## What it does
- "Alexa, Dad took his Metformin" -> `log_dose`
- "Did Dad take his morning pills?" -> `check_status` (taken / due / overdue)
- "Give me Dad's family digest" -> `family_digest`; 2+ overdue doses triggers a family alert (Amazon SNS if `SNS_TOPIC_ARN` is set, otherwise logged)
- "Make a doctor report for Dad" -> `doctor_report` (7-day adherence % per medication + wellbeing notes)
- `log_note` captures symptoms like "felt dizzy" so they reach the doctor report

## Run
```bash
pip install -r requirements.txt
python server.py                 # http://localhost:8000/mcp
npx @modelcontextprotocol/inspector   # Streamable HTTP -> the URL above
```
Call `load_demo_data` first for the video. Pass `now` (ISO time, e.g. 2026-10-20T21:30:00) to `check_status` / `family_digest` to simulate a time of day.

## Demo video plan (under 3 min)
0:00 problem in one sentence -> 0:15 voice: log a dose -> 0:45 "did Dad take his pills?" with an overdue evening dose -> 1:15 digest + family alert fires -> 1:45 doctor report -> 2:20 architecture + open source.

## Submission checklist
- [ ] Public repo with MIT license (or shared with testing@devpost.com + Amazon reviewers)
- [ ] Repo must actually call MCP in code (it does: `server.py`)
- [ ] Demo video, English, public
- [ ] Product feedback + optional friction log (+10% bonus)
- [ ] Tracks: Alexa+ and Open Source
- [ ] Add Amazon reviewers when you submit (invites expire in 7 days)
