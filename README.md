# Social Media Analytics Pipeline Agent

An automated, multi-agent data pipeline built with the [Google ADK (Agent Development Kit)](https://github.com/GoogleCloudPlatform/agent-starter-pack). It collects YouTube content by keyword, analyzes comments with Gemini AI, stores everything in BigQuery, and provides natural language analytics through a conversational interface.

## Pipeline Overview

```
User Request (keyword)
        ↓
[1] 🕵️  Scrape YouTube (title, views, comments)        ← scout_tool.py
        ↓
[2] 🤖  Gemini AI analyzes each comment               ← gemini_analyzer.py
        (reaction: 긍정/부정/중립, comment_keyword)
        ↓
[3] ☁️  Upload enriched NDJSON to GCS                 ← gcs_uploader.py
        ↓
[4] 📦  Load from GCS → BigQuery (MERGE)              ← bq_loader.py
        ↓
[5] 📊  Conversational Analytics (CA API + Charts)    ← analytics_agent
```

## Multi-Agent Architecture

```
root_coordinator (gemini-2.5-pro)
├── scrap_and_upload (tool)          ← Step 1~3
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
│   │   └── analytics.py          # NL-to-SQL analytics agent
│   ├── tools/
│   │   ├── scout_tool.py          # Scrape + Gemini analysis + GCS upload
│   │   ├── gemini_analyzer.py     # Gemini comment sentiment analysis
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

Create `app/.env`:

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
# 1. Install dependencies
make install

# 2. Run interactive playground (local)
make playground
```

** Cloud shell setting for Conversational Analytics API **

```bash
gcloud services enable geminidataanalytics.googleapis.com
gcloud services enable cloudaicompanion.googleapis.com
gcloud services enable bigquery.googleapis.com
```

**Example prompts:**
- `"봄신상" 키워드로 10개 수집해줘` → scrape + Gemini analysis + BQ load
- `키워드별 수집된 게시물 수 보여줘` → NL-to-SQL analytics
- `긍정 반응이 많은 댓글 키워드 뽑아줘` → sentiment analysis query

## Deployment

```bash
# 1. Set GCP project
gcloud config set project <your-project-id>

# 2. Deploy to Vertex AI Agent Engine
make deploy

# 3. Register with Gemini Enterprise (App ID is auto-detected)
make register-gemini-enterprise
```

> **Note**: `make register-gemini-enterprise` automatically detects the first Gemini Enterprise App in your project — no hardcoding required.

## Makefile Commands

| Command | Description |
|---|---|
| `make install` | Install dependencies |
| `make playground` | Run interactive local playground |
| `make deploy` | Deploy to Vertex AI Agent Engine |
| `make register-gemini-enterprise` | Register agent with Gemini Enterprise (auto-detects App ID) |
| `make lint` | Run code linting |
| `make test` | Run tests |

---
Built with [agent-starter-pack](https://github.com/GoogleCloudPlatform/agent-starter-pack) · Powered by Google ADK & Gemini 2.5 Pro
