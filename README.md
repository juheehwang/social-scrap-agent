# Social Media Analytics Pipeline Agent

This is an automated, multi-agent data pipeline built with the [Google ADK (Agent Development Kit)](https://github.com/GoogleCloudPlatform/agent-starter-pack). It specializes in fetching, storing, and analyzing social media data (currently YouTube) through a conversational interface.

## Overview

The agent automates a full data lifecycle:

1.  **Collection (Scraping)**: Fetches video data (titles, views, comments) using the YouTube Data API based on user keywords.
2.  **Storage**: Temporarily stores data in NDJSON format and uploads it to **Google Cloud Storage (GCS)**.
3.  **Data Engineering**: Automatically merges/appends the GCS data into a **BigQuery** table for persistent storage.
4.  **AI Analytics**: Queries the BigQuery dataset using natural language to SQL conversion, providing structured summaries and **Looker Studio** visualization links.

## Multi-Agent Architecture

This project uses an orchestrated multi-agent pattern:

-   **`root_coordinator`**: The main entry point that manages the pipeline flow from scraping to analysis.
-   **`data_engineering_agent`**: Specialized in GCS-to-BigQuery data movement and schema management.
-   **`analytics_agent`**: Focuses on natural language data exploration, SQL generation, and reporting.

## Project Structure

```
social-scrap-agent/
├── app/                        # Core agent logic
│   ├── agent.py               # Entry point (interactive mode)
│   ├── agents/                # Specialized sub-agents
│   │   ├── root_coordinator.py # Pipeline orchestrator
│   │   ├── data_engineering.py # BQ loading logic
│   │   └── analytics.py       # Data analysis logic
│   └── tools/                 # Custom tools for agents
│       ├── youtube_api.py     # YT Data API interface
│       ├── scout_tool.py      # Scrape + GCS upload wrapper
│       ├── bq_loader.py       # BigQuery ingestion tool
│       ├── bq_analyzer.py     # SQL execution tool
│       └── looker_tool.py     # Visualization URL provider
├── .cloudbuild/               # CI/CD configs
├── deployment/                # Infrastructure (Terraform)
├── tests/                     # Unit & integration tests
├── Makefile                   # Dev & deployment commands
└── pyproject.toml             # Dependencies & metadata
```

## Requirements

-   **uv**: Python package manager - [Install](https://docs.astral.sh/uv/getting-started/installation/)
-   **Google Cloud SDK**: For GCP authentication - [Install](https://cloud.google.com/sdk/docs/install)
-   **Terraform**: For infra deployment - [Install](https://developer.hashicorp.com/terraform/downloads)

## Environment Variables

Create a `.env` file in the `app/` directory (or set them in your environment):

```bash
YOUTUBE_API_KEY=your_api_key
GCS_BUCKET_NAME=your_bucket_name
BQ_DATASET_ID=social_dataset
BQ_TABLE_NAME=daily_social_scrap
```

## Quick Start

1.  **Install dependencies**:
    ```bash
    make install
    ```

2.  **Run locally (Interactive Mode)**:
    ```bash
    make playground
    ```

## Deployment

1.  **Set GCP Project**:
    ```bash
    gcloud config set project <your-project-id>
    ```

2.  **Deploy to Vertex AI Agent Engine**:
    ```bash
    make deploy
    ```

3.  **Register with Gemini Enterprise**:
    ```bash
    make register-gemini-enterprise
    ```

---
Agent generated with `googleCloudPlatform/agent-starter-pack` version `0.39.4`
