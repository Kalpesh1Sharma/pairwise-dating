# Pairwise — Agentic Dating

Pairwise gives every person an agent. The agent reads exactly two supplied public sources — LinkedIn and Instagram — builds a structured profile, evaluates other profiles, conducts an agent-to-agent first date, and produces a person-specific ranking.

## Demo flow

1. Open `/profiles` and choose a person.
2. Inspect the agent profile: needs, values, interests, hobbies, style, and the two source links.
3. Open **personalized matches**. The ranking is calculated relative to that person's profile; there is no global leaderboard.
4. Pick any candidate to start an actual agent-to-agent date.
5. The date uses the two structured profiles to ask grounded questions, explore shared interests, probe differences, and produce a debrief.
6. On the home page, paste any public LinkedIn + Instagram pair. The app creates a temporary custom profile and lets you open its profile and candidate ranking.

## Stack

- FastAPI + Python
- Jinja2 templates
- Vanilla JavaScript
- CSS
- Requests + BeautifulSoup for public-page metadata extraction
- Deterministic structured agent engine for the no-API-credit demo
- Docker / Render configuration included

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`.

## Source policy

The product is designed around the challenge constraint: each profile has exactly two information sources, LinkedIn and public Instagram. The seeded demo stores those two URLs and structured notes. The live analyzer only extracts public page metadata and explicitly marks information it cannot establish.

The system does not require account credentials or private content and does not attempt to bypass platform access controls.

## Architecture

```text
LinkedIn ─┐
          ├─ public metadata → structured person profile → agent
Instagram ┘                                      │
                                                 ▼
                                      candidate compatibility
                                                 │
                                      ┌──────────┴──────────┐
                                      ▼                     ▼
                                  agent A ↔ agent B     agent A ↔ agent C
                                      │                     │
                                      └──────────┬──────────┘
                                                 ▼
                                      personalized ranking
```

## Submission demo

For the three-minute video, show:

- 25 seeded people
- one complete agent profile
- one complete agent-to-agent date
- date debrief and reasoning
- a personalized ranking
- a different person's ranking to demonstrate personalization
- live LinkedIn + Instagram analysis

See `SUBMISSION.md` for the suggested video script and submission copy.
