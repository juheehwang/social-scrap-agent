import os
import json
import logging
import proto
import pandas as pd
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Import CA API sdk
try:
    from google.cloud import geminidataanalytics
except ImportError:
    geminidataanalytics = None

load_dotenv()

# We only invoke the real API if it's installed.
if geminidataanalytics:
    try:
        data_agent_client = geminidataanalytics.DataAgentServiceClient()
        data_chat_client = geminidataanalytics.DataChatServiceClient()
    except Exception as e:
        logging.warning(f"CA API Clients could not be initialized: {e}")

def _value_to_dict(v):
    """Helper to cleanly parse MapComposite returning from protobufs"""
    if isinstance(v, proto.marshal.collections.maps.MapComposite):
        return {k: _value_to_dict(v[k]) for k in v}
    elif isinstance(v, proto.marshal.collections.RepeatedComposite):
        return [_value_to_dict(el) for el in v]
    return v

def generate_mermaid_from_vega(vega_config: Dict[str, Any], data_rows: List[Dict[str, Any]]) -> str:
    """
    Attempt to convert a Vega-Lite config and current data rows into a Mermaid JS chart.
    Since deep vega conversion is hard, we look for basic hints or just default to a Bar/Pie chart
    based on the first few columns if we can't parse Vega easily.
    """
    if not data_rows:
        return ""
    
    # Very simple heuristics for Mermaid charting
    # Determine Mark type
    mark_type = vega_config.get("mark", "bar")
    if isinstance(mark_type, dict):
        mark_type = mark_type.get("type", "bar")
        
    encoding = vega_config.get("encoding", {})
    x_field = encoding.get("x", {}).get("field")
    y_field = encoding.get("y", {}).get("field")
    color_field = encoding.get("color", {}).get("field")
    
    if not x_field or not y_field:
        # Fallback: find the first string and first numeric column
        cols = list(data_rows[0].keys())
        string_cols = [c for c in cols if isinstance(data_rows[0][c], str)]
        numeric_cols = [c for c in cols if isinstance(data_rows[0][c], (int, float))]
        if string_cols and numeric_cols:
            x_field = string_cols[0]
            y_field = numeric_cols[0]
        else:
            return "" # Can't chart securely
            
    # Clean data to avoid mermaid syntax errors
    clean_data = []
    for row in data_rows:
        x_val = str(row.get(x_field, "")).replace('"', '').replace('\n', ' ')
        y_val = row.get(y_field, 0)
        if isinstance(y_val, (int, float)):
            clean_data.append((x_val, y_val))
            
    # Take top 20 to avoid giant mermaid strings
    clean_data = clean_data[:20]

    import urllib.parse
    
    if mark_type in ["arc", "pie"]:
        # Mermaid Pie Chart
        lines = ["```mermaid", f"pie title Data Chart"]
        for label, val in clean_data:
            lines.append(f'    "{label}" : {val}')
        lines.append("```")
        return "\n".join(lines)
    else:
        # Use QuickChart API for beautiful Bar Charts universally supported via Markdown Image
        labels = [str(label) for label, val in clean_data]
        values = [val for label, val in clean_data]
        
        chart_config = {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "Value",
                    "data": values,
                    "backgroundColor": "rgba(54, 162, 235, 0.8)"
                }]
            },
            "options": {
                "legend": {"display": False},
                "title": {"display": True, "text": "Data Chart"}
            }
        }
        import json
        json_str = json.dumps(chart_config)
        # 500x250 ensures it stays compact and does not overpower the chat UI
        encoded_url = "https://quickchart.io/chart?w=500&h=250&c=" + urllib.parse.quote(json_str)
        
        return f"![막대 차트]({encoded_url})"


def get_or_create_ca_agent() -> str:
    """Gets or creates the Gemini Data Analytics Agent, returns agent path."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT or GCP_PROJECT is missing. Run 'make setup-env' first.")
    dataset_id = os.getenv("BQ_DATASET_ID") or "social_dataset"
    location = "global"
    data_agent_id = "social_scrap_analytics_agent_v9"
    
    agent_path = f"projects/{project_id}/locations/{location}/dataAgents/{data_agent_id}"
    
    try:
        # Try getting first
        request = geminidataanalytics.GetDataAgentRequest(name=agent_path)
        data_agent_client.get_data_agent(request=request)
        return agent_path
    except Exception:
        # Create it if not found
        system_instruction = """
You are an expert social media data analyst. Users will ask questions about social posts, platforms, views, comments, and keywords.

Always use the `scrap_id` column to join the parent and child tables.

Table 1: `daily_social_scrap`
Fields:
- `scrap_id`: Unique identifier for the post.
- `keyword`: The search keyword used to scrape the post.
- `url`: URL of the post.
- `title`: Title or content text of the post.
- `platform`: Social media platform (e.g., youtube, naver_blog).
- `owner`: The author or channel name.
- `published_at`: Publication timestamp.
- `views`: Number of views.
- `comment_count`: Total comments on the post.
- `content`: AI-generated video transcript/summary.


Table 2: `social_comment`
Fields:
- `scrap_id`: Foreign key linking back to the daily_social_scrap table.
- `comment`: The raw text of the comment.
- `reaction`: Sentiment or reaction category. Must be one of exactly '긍정', '부정', or '중립' in Korean ONLY! Always group by this string if user asks for sentiment.
- `comment_keyword`: Extracted keywords from this specific comment.

Join Rule:
- To join post metadata and comment details, always INNER JOIN the two tables on their common `scrap_id`.

Few-shot Examples:

Q: '명품화장품' 키워드로 수집된 영상들의 실제 댓글 총 개수는?
A:
SELECT COUNT(c.comment) AS total_comments
FROM `daily_social_scrap` s
JOIN `social_comment` c ON s.scrap_id = c.scrap_id
WHERE s.keyword = '명품화장품' AND c.reaction = '긍정'

Q: '메이크업' 영상들의 긍정 댓글 비율은?
A:
SELECT c.reaction, COUNT(*) as cnt
FROM `daily_social_scrap` s
JOIN `social_comment` c ON s.scrap_id = c.scrap_id
WHERE s.keyword = '메이크업'
GROUP BY c.reaction
"""
        bq_parent = geminidataanalytics.BigQueryTableReference(
            project_id=project_id,
            dataset_id=dataset_id,
            table_id="daily_social_scrap"
        )
        bq_child = geminidataanalytics.BigQueryTableReference(
            project_id=project_id,
            dataset_id=dataset_id,
            table_id="social_comment"
        )
        datasource_references = geminidataanalytics.DatasourceReferences(
            bq=geminidataanalytics.BigQueryTableReferences(table_references=[bq_parent, bq_child])
        )
        
        published_context = geminidataanalytics.Context(
            system_instruction=system_instruction,
            datasource_references=datasource_references,
            options=geminidataanalytics.ConversationOptions(
                analysis=geminidataanalytics.AnalysisOptions(
                    python=geminidataanalytics.AnalysisOptions.Python(enabled=False)
                )
            ),
        )
        data_agent = geminidataanalytics.DataAgent(
            data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
                published_context=published_context
            ),
        )
        
        # Create
        try:
            data_agent_client.create_data_agent(request=geminidataanalytics.CreateDataAgentRequest(
                parent=f"projects/{project_id}/locations/{location}",
                data_agent_id=data_agent_id,
                data_agent=data_agent,
            ))
        except Exception as create_e:
            if "already exists" in str(create_e).lower() or "409" in str(create_e):
                logging.info(f"Agent {data_agent_id} already exists (caught 409). Proceeding.")
            else:
                raise create_e
                
        return agent_path

def execute_conversational_analytics(query: str, session_id: str = "default_session") -> str:
    """
    Calls the Conversational Analytics API with the given query.
    Returns a formatted string containing:
      1. Thought process / SQL generated
      2. Markdown Table of the data
      3. Mermaid JS Chart (if vega_config is returned)
    """
    if not geminidataanalytics:
        return "❌ Error: google-cloud-geminidataanalytics package is not installed."
        
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT or GCP_PROJECT is missing. Run 'make setup-env' first.")
    location = "global"
    
    try:
        agent_path = get_or_create_ca_agent()
    except Exception as e:
        return f"❌ Failed to initialize CA API Agent: {e}"

    # Setup Conversation
    conversation_id = f"ca_api_v9_{session_id}"
    conversation_path = f"projects/{project_id}/locations/{location}/conversations/{conversation_id}"
    
    try:
        data_chat_client.get_conversation(name=conversation_path)
    except Exception:
        conversation = geminidataanalytics.Conversation(agents=[agent_path])
        request = geminidataanalytics.CreateConversationRequest(
            parent=f"projects/{project_id}/locations/{location}",
            conversation_id=conversation_id,
            conversation=conversation,
        )
        try:
            data_chat_client.create_conversation(request=request)
        except Exception as conv_e:
            if "already exists" in str(conv_e).lower() or "409" in str(conv_e):
                logging.info(f"Conversation {conversation_id} already exists (caught 409). Proceeding.")
            else:
                raise conv_e

    # Send Message
    messages = [
        geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=query)
        )
    ]
    conversation_reference = geminidataanalytics.ConversationReference(
        conversation=conversation_path,
        data_agent_context=geminidataanalytics.DataAgentContext(data_agent=agent_path),
    )
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id}/locations/{location}",
        messages=messages,
        conversation_reference=conversation_reference,
    )
    
    try:
        stream = data_chat_client.chat(request=request)
    except Exception as e:
        return f"❌ CA API Chat failed: {str(e)}"

    sql_generated = ""
    data_rows = []
    vega_config = {}
    
    # Process stream
    for response in stream:
        m = getattr(response, "system_message", None)
        if not m:
            continue
            
        if "data" in m:
            data_msg = getattr(m, "data")
            if "generated_sql" in data_msg:
                sql_generated = getattr(data_msg, "generated_sql")
            
            if "result" in data_msg:
                # Process dataframe
                fields = [field.name for field in data_msg.result.schema.fields]
                for el in data_msg.result.data:
                    row_dict = {}
                    for field in fields:
                        row_dict[field] = el[field]
                    data_rows.append(row_dict)
                
        if "chart" in m:
            chart_msg = getattr(m, "chart")
            if "result" in chart_msg:
                vega_config = _value_to_dict(chart_msg.result.vega_config)

    # Format output
    output_lines = []
    
    if getattr(m, "data", None) and getattr(m.data, "generated_sql", None):
        pass # SQL is captured correctly above
        
    if sql_generated:
       output_lines.append(f"**💡 생성된 SQL 쿼리:**\n```sql\n{sql_generated}\n```\n")
        
    if data_rows:
        df = pd.DataFrame(data_rows)
        output_lines.append(f"**데이터 표 ({len(df)}건):**")
        
        # Manually generate Markdown table to avoid 'tabulate' optional dependency requirement
        headers = list(data_rows[0].keys())
        output_lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        output_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        for row in data_rows:
            row_values = []
            for h in headers:
                val = row.get(h, "")
                if isinstance(val, float):
                    val = f"{val:,.2f}"
                elif isinstance(val, int):
                    val = f"{val:,}"
                row_values.append(str(val))
            output_lines.append("| " + " | ".join(row_values) + " |")
            
        output_lines.append("\n")
        
        # Chart generation
        if vega_config:
            mermaid_chart = generate_mermaid_from_vega(vega_config, data_rows)
            if mermaid_chart:
                output_lines.append(f"**분석 차트:**\n{mermaid_chart}")
    else:
        output_lines.append("API가 결과를 찾지 못했습니다.")

    return "\n".join(output_lines)
