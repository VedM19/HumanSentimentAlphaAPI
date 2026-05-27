# Human Sentiment Alpha API

A FastAPI service that compares the recent GitHub momentum of two repositories using weekly star growth and an EWMA-based trend score.

This project was built to explore whether open-source developer attention can act as a lightweight leading indicator of AI platform momentum. A practical example is comparing NVIDIA's `TensorRT` ecosystem with AMD's `ROCm` ecosystem by looking at how their GitHub star growth is trending over recent weeks.

## Why this project is interesting

- It combines API design, external data fetching, analytics, and application architecture in one small project.
- It uses real GitHub repository data instead of static examples.
- It compares both raw growth and recent momentum, which gives a more nuanced view than total stars alone.
- It turns a vague market intuition into a concrete, testable service.

## What it does

Given two public GitHub repositories and a time window in weeks, the API:

1. Fetches each repository's stargazer history from the GitHub API.
2. Buckets new stars by week.
3. Calculates weekly star growth for each repository.
4. Computes an EWMA-based momentum score from that weekly series.
5. Fetches the current live `stargazers_count` (total stars) for each repository.
6. Returns a comparison summary and declares a momentum winner.

## Example use case

You can compare:

- `NVIDIA/TensorRT` vs `ROCm/ROCm`
- `pytorch/pytorch` vs `tensorflow/tensorflow`
- any other pair of public GitHub repositories

## Tech stack

- Python
- FastAPI
- Uvicorn
- httpx
- Pydantic
- pytest

## Project structure

- `src/app/api`: route definitions and dependency wiring
- `src/app/agents`: orchestration logic for comparisons
- `src/app/services`: GitHub client, analytics service, and metrics
- `src/app/models`: request and response schemas
- `src/app/core`: application settings
- `tests`: API and service-level tests

## How the scoring works

The project uses weekly star growth as the base signal.

Example:

- week 1: 12 new stars
- week 2: 20 new stars
- week 3: 34 new stars
- week 4: 55 new stars

That tells you how attention changes over time.

To compare recent trend strength, the app uses an EWMA (Exponentially Weighted Moving Average). The EWMA is calculated using alpha = 2 / (span + 1), where span is the number of weekly observations to emphasize. Lower spans make the score more reactive; higher spans make it smoother. This makes it better at answering:

"Which repository appears to be gaining momentum right now?"

This is useful because total star growth and recent momentum are not always the same thing. A repository may have strong total growth over a month, while another repository may be accelerating more sharply in the most recent week or two.

## Limitations

GitHub stars are a soft signal, not a direct measure of:

- revenue
- production usage
- customer count
- model deployment volume

This project is best understood as a developer-interest and ecosystem-momentum signal, not a full business-performance model.

## Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## GitHub token setup

The app uses GitHub's API, so adding a token is recommended to avoid low unauthenticated rate limits.

Create a `.env` file in the project root:

```env
GITHUB_TOKEN=your_github_token_here
```

The app reads this automatically through [`src/app/core/config.py`](src/app/core/config.py).

## Run the server

```bash
python3 -m uvicorn app.main:app --reload --app-dir src
```

Once running, open:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## API endpoint

- `POST /api/v1/comparisons/weekly-stars`

Example request:

```json
{
  "weeks": 4,
  "left_repository": {
    "owner": "NVIDIA",
    "name": "TensorRT"
  },
  "right_repository": {
    "owner": "ROCm",
    "name": "ROCm"
  }
}
```

Example response shape:

```json
{
  "winner": "NVIDIA/TensorRT",
  "summary": "NVIDIA/TensorRT shows stronger recent GitHub adoption momentum...",
  "repositories": [
    {
      "repository": "NVIDIA/TensorRT",
      "total_growth": 123,
      "momentum_score": 37.45,
      "current_stargazers": 12000,
      "weekly_deltas": [
        {
          "week_start": "2026-05-04",
          "stars_gained": 20
        }
      ]
    }
  ]
}
```

## Testing

Run tests with:

```bash
pytest -q
```

## License

This project is released under the MIT License. See [`LICENSE`](LICENSE).

## Architecture notes

The code is intentionally separated by responsibility:

- the GitHub client handles HTTP calls and API-specific errors
- the analytics service converts raw stargazer events into weekly growth data
- the metrics module computes EWMA momentum
- the agent coordinates the comparison and builds the final explanation

This makes the project easier to extend and easier to test.

## Future improvements

- add caching to reduce repeated GitHub API calls
- support multiple comparison modes such as `momentum`, `total_growth`, and `hybrid`
- improve large-repo performance for stargazer history collection
- deploy a live demo
- add contributor and release activity signals alongside star growth

## Resume-friendly summary

Built a FastAPI analytics service that compares GitHub repository momentum using weekly star-growth history, live GitHub API data, and an EWMA-based scoring model to evaluate recent open-source ecosystem traction.
