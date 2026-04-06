# Social Media Analytics Pipeline Agent

An automated, multi-agent data pipeline built with the [Google ADK (Agent Development Kit)](https://github.com/GoogleCloudPlatform/agent-starter-pack). It collects YouTube content by keyword, analyzes comments with Gemini AI, stores everything in BigQuery, and provides natural language analytics through a conversational interface.

## Pipeline Overview

```
User Request (keyword)
        ↓
[1] 🕵️  Scrape YouTube (title, views, comments)        ← scout_tool.py
        ↓
[2] 🤖  Gemini AI analyzes content & comments           ← gemini_analyzer.py
        (Multilingual Sentiment, Sarcasm/Metaphor Detection)
        ↓
[3] ☁️  Upload enriched NDJSON to GCS (UUID-named)       ← gcs_uploader.py
        ↓
[4] 📦  Load from GCS → BigQuery (MERGE)                ← bq_loader.py
        ↓
[5] 📊  Conversational Analytics (CA API + Charts)      ← analytics_agent
```

## Multi-Agent Architecture

```
root_coordinator (gemini-3.1-pro-preview)
├── scrap_and_upload (tool)          ← Step 1~3 (Parallel processing)
├── data_engineering_agent           ← Step 4
│   └── load_daily_report_to_bigquery (tool)
└── analytics_agent                  ← Step 5
    └── execute_conversational_analytics (tool)
```

## BigQuery Schema

### `daily_social_scrap` — 게시물 원본
| Column | Type | Description |
|---|---|---|
| scrap_id | STRING | URL 기반 고유 ID |
| keyword | STRING | 수집 키워드 |
| url | STRING | 게시물 URL |
| title | STRING | 게시물 제목 |
| platform | STRING | 플랫폼 (youtube) |
| owner | STRING | 채널/작성자 |
| published_at | TIMESTAMP | 게시일 |
| views | INT64 | 조회수 |
| comment_count | INT64 | 댓글 수 |
| content | STRING | AI 영상 분석/요약 결과 |

### `social_comment` — Gemini 분석 댓글
| Column | Type | Description |
|---|---|---|
| scrap_id | STRING | 부모 게시물 ID (FK) |
| comment | STRING | 원본 댓글 |
| reaction | STRING | AI 감성 분석 (긍정/부정/중립) |
| comment_keyword | STRING | AI 추출 핵심 키워드 (쉼표 구분) |

## Project Structure

```
social-scrap-agent/
├── app/
│   ├── agent.py                    # ADK App entry point
│   ├── agent_engine_app.py         # Vertex AI Agent Engine wrapper
│   ├── agents/
│   │   ├── root_coordinator.py    # Pipeline orchestrator
│   │   ├── data_engineering.py    # BQ loading agent
│   │   ├── analytics.py           # NL-to-SQL analytics agent
│   │   └── md_loader.py           # Load markdown prompt templates
│   ├── tools/
│   │   ├── scout_tool.py          # Scrape + Gemini analysis + GCS upload
│   │   ├── gemini_analyzer.py     # Gemini comment sentiment analysis
│   │   ├── sql_analyzer.py        # BigQuery SQL analyzer with validation
│   │   ├── gcs_uploader.py        # GCS upload helper
│   │   ├── bq_loader.py           # BigQuery MERGE loading
│   │   ├── ca_analyzer.py         # Conversational Analytics API (Charts & Markdown)
│   │   ├── youtube_api.py         # YouTube Data API v3 client
│   │   └── models.py              # Data models
│   └── app_utils/
│       └── deploy.py              # Deployment utilities
├── Makefile                       # All dev & deployment commands
└── pyproject.toml                 # Dependencies
```

## Requirements

- **Python 3.11+**
- **uv** — Python package manager ([Install](https://docs.astral.sh/uv/getting-started/installation/))
- **Google Cloud SDK** — GCP auth ([Install](https://cloud.google.com/sdk/docs/install))
- **jq** — JSON processor for Makefile scripts (`brew install jq`)

## Environment Variables

The easiest way to set up your environment is running `make setup-env`, which automatically detects your active `gcloud` project and creates/updates `app/.env`.

Alternatively, manually create `app/.env`:

```bash
# YouTube Data API Key
YOUTUBE_API_KEY=your_youtube_api_key

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=1

# GCS & BigQuery
GCS_BUCKET_NAME=your-gcs-bucket-name
BQ_DATASET_ID=social_dataset
BQ_TABLE_NAME=daily_social_scrap
```

## Quick Start

```bash
# 1. Authenticate with Google Cloud (ADC)
gcloud auth application-default login

# 2. Setup environment variables
make setup-env

# 3. Install dependencies
make install

# 4. Run interactive playground (local)
make playground
```

**Example prompts:**
- `"봄신상" 키워드로 10개 수집해줘` → scrape + Gemini analysis + BQ load (Datasets and tables are created automatically if missing)
- `키워드별 수집된 게시물 수 보여줘` → CA API Data Table + Auto Chart
- `긍정 반응이 많은 댓글 키워드 막대 차트로 그려줘` → CA API Sentiment analysis + QuickChart Bar Chart

## Deployment

```bash
# 1. Authenticate with Google Cloud (ADC)
gcloud auth application-default login

# 2. Set GCP project
gcloud config set project <your-project-id>

# 3. Deploy to Vertex AI Agent Engine
make deploy

# 4. Register with Gemini Enterprise (App ID is auto-detected)
make register-gemini-enterprise
```

> **Note**: `make register-gemini-enterprise` automatically detects the first Gemini Enterprise App in your project — no hardcoding required.

## Makefile Commands

| Command | Description |
|---|---|
| `make install` | Install dependencies |
| `make setup-env` | Setup `app/.env` with current `gcloud` project |
| `make playground` | Run interactive local playground |
| `make deploy` | Deploy to Vertex AI Agent Engine |
| `make register-gemini-enterprise` | Register agent with Gemini Enterprise (auto-detects App ID) |
| `make lint` | Run code linting |
| `make test` | Run tests |

## Key Features

- **Universal Video Analysis**: Support for summarizing video content (audio/speech) from YouTube and other video platforms using `gemini-3.1-pro-preview`.
- **Multilingual Sentiment Analysis**: Advanced sentiment analysis detecting sarcasm and metaphors across various languages.
- **Concurrent & Scalable**: UUID-based file naming and explicit GCS URI passing prevent race conditions during concurrent agent runs.
- **Parallel Processing**: Uses `asyncio.gather` for high-throughput scraping and AI analysis.
- **Automated Data Pipeline**: From raw social data to BigQuery tables and visual charts via natural language.

---
## Upgrade Feature 

- **Multi-Platform Social Media Integration**: Extend the pipeline to support other platforms like Instagram, TikTok, and Twitter/X by implementing pluggable API adapters.
- **Scalable Batch Sentiment Analysis with BigQuery ML (BQML)**: As data volume grows, shift from real-time API calls to BigQuery ML (using Vertex AI models within BQ) for high-performance, cost-effective batch sentiment analysis and keyword extraction.

---
Built with [agent-starter-pack](https://github.com/GoogleCloudPlatform/agent-starter-pack) · Powered by Google ADK & Gemini 3.1 Pro Preview
