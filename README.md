# Entertainment Planner

An AI agent that takes a plain-English entertainment request, searches the web live, and returns curated movie and/or music recommendations — rendered in clean, structured markdown.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your API keys

# 3. Run
python app.py
# Opens at http://localhost:5000
```

## API Keys Required

| Key | Where to get it |
|-----|-----------------|
| `GROQ_API_KEY` | https://console.groq.com |
| `SERPER_API_KEY` | https://serper.dev |

## How it works

1. User visits `/new`, picks intent (Movies / Music / Both) and types a query
2. On submit, a background agent starts: searches the web via Serper, then calls Groq/Llama to structure results into formatted markdown
3. Browser navigates to `/results/<id>` and polls until the plan is ready
4. Results are displayed in structured tabs with rendered markdown tables and lists

## Project structure

```
app.py          # Flask routes + background worker
agents.py       # LLM agent pipeline (Movie → Music → Planner)
tools.py        # Serper search helpers
templates/
  new.html      # /new — query input page
  results.html  # /results/<id> — results page with polling
requirements.txt
.env.example
```