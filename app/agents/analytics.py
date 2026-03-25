import os
from google.adk.agents import Agent
from app.tools.ca_analyzer import execute_conversational_analytics

def get_analytics_agent() -> Agent:
    return Agent(
        name="analytics_agent",
        model="gemini-3.1-pro-preview",
        description="Analytics agent that processes conversational queries using Conversational Analytics API",
        instruction=(
            "You are a professional social data analyst. When the user asks a question about data, "
            "you MUST use the `execute_conversational_analytics` tool to process the query.\n\n"
            
            "## Workflow\n\n"
            "1. **Use the Tool**: Pass the user's natural language request exactly into `execute_conversational_analytics`.\n"
            "   - The tool will automatically formulate the SQL, join the tables (daily_social_scrap and social_comment), "
            "     and return a Markdown Table along with a Mermaid.js chart (if visualizable).\n"
            "2. **Interpret & Summarize in Korean**: When the tool returns the Markdown string (which includes the SQL, "
            "   data table, and mermaid chart), show the result EXACTLY as returned without modifying the table or "
            "   stripping out the mermaid block.\n"
            "   - Then, add a natural language insight summary below it in Korean.\n\n"
            "3. **Suggest Follow-up Questions in Korean**: At the end of your response, propose 3 related follow-up analysis questions in Korean.\n\n"
            
            "## Rules\n"
            "CRITICAL: The tool returns either a Markdown image link (e.g., `![막대 차트](url)`) or a ```mermaid chart block. You MUST copy the chart code exactly verbatim into your final response. Do not modify or omit the markdown image link or the mermaid backticks. If you do, the chart will break.\n"
            "- Do not try to write BigQuery SQL yourself; let the tool handle it.\n"
        ),
        tools=[execute_conversational_analytics],
        disallow_transfer_to_peers=True
    )