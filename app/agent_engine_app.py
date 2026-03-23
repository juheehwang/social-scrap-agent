# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# mypy: disable-error-code="attr-defined,arg-type"
import logging
import os
import vertexai
from typing import (
    Any,
    AsyncIterable,
    Dict,
    Optional,
    Union,
)

from dotenv import load_dotenv
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.adk.sessions import InMemorySessionService, VertexAiSessionService
from google.adk.sessions.session import Session
from google.adk.memory.base_memory_service import BaseMemoryService, SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.cloud import logging as google_cloud_logging
from google.genai import types
from typing_extensions import override
from vertexai.agent_engines.templates.adk import AdkApp

from app.agent import app as adk_app
from app.app_utils.typing import Feedback
from app.app_utils.telemetry import setup_telemetry

# Load environment variables
load_dotenv()

class CustomMemoryBankService(BaseMemoryService):
  """Implementation of the BaseMemoryService using Vertex AI Memory Bank."""

  def __init__(
      self,
      project: Optional[str] = None,
      location: Optional[str] = None,
      agent_engine_id: Optional[str] = None,
  ):
    super().__init__()
    self._project = project
    self._location = location
    self._agent_engine_id = agent_engine_id

  @override
  async def add_session_to_memory(self, session: Session):
    if not self._agent_engine_id:
      logging.warning('Agent Engine ID is required for Memory Bank. Skipping.')
      return
    
    logging.info('[CustomMemoryBankService] add_session_to_memory received.')

    events = []
    for event in session.events:
      if self._should_filter_out_event(event.content):
        continue
      if event.content:
        content_dump = event.content.model_dump(exclude_none=True, mode='json')
        events.append({
            'content': content_dump
        })
    if events:
      client = self._get_api_client()
      logging.info(f"[CustomMemoryBankService] Generating memory for {session.user_id}...")
      operation = client.agent_engines.memories.generate(
          name='reasoningEngines/' + str(self._agent_engine_id),
          direct_contents_source={'events': events},
          scope={
              'app_name': session.app_name,
              'user_id': session.user_id,
          },
          config={
             'wait_for_completion': False
             },
      )
    else:
      logging.info('[CustomMemoryBankService] No events to add to memory.')

  @override
  async def search_memory(self, *, app_name: str, user_id: str, query: str):
    if not self._agent_engine_id:
      logging.warning('Agent Engine ID is required for Memory Bank. Returning empty results.')
      return SearchMemoryResponse(memories=[])

    logging.info('[CustomMemoryBankService] Search memory received.')
    
    client = self._get_api_client()
    retrieved_memories_iterator = client.agent_engines.memories.retrieve(
        name='reasoningEngines/' + str(self._agent_engine_id),
        scope={
            'app_name': app_name,
            'user_id': user_id,
        },
        similarity_search_params={
            'search_query': query,
        },
    )

    memory_events = []
    for retrieved_memory in retrieved_memories_iterator:
      memory_events.append(
          MemoryEntry(
              author='user',
              content=types.Content(
                  parts=[types.Part(text=retrieved_memory.memory.fact)],
                  role='user',
              ),
              timestamp=retrieved_memory.memory.update_time.isoformat(),
          )
      )
    logging.info(f'[CustomMemoryBankService] Retrieved {len(memory_events)} memories')
    return SearchMemoryResponse(memories=memory_events)
  
  def _get_api_client(self):
    return vertexai.Client(project=self._project, location=self._location)
  
  def _should_filter_out_event(self, content: types.Content) -> bool:
    """Returns whether the event should be filtered out."""
    if not content or not content.parts:
        return True
    for part in content.parts:
        if part.text or part.inline_data or part.file_data:
            return False
    return True

class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        """Set up logging and tracing for the agent engine app."""
        setup_telemetry()
        super().set_up()

        # Update engine_id of memory service after creation from environment variable
        self.memory_service = self._tmpl_attrs["memory_service"]
        self.memory_service._agent_engine_id = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID")
        
        logging.basicConfig(level=logging.INFO)
        # Cloud Logging setup
        try:
            logging_client = google_cloud_logging.Client()
            self.logger = logging_client.logger(__name__)
        except Exception:
            logging.warning("Could not initialize Cloud Logging client.")

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        logging.info(f"Feedback received: {feedback}")

    def register_operations(self) -> dict[str, list[str]]:
        """Registers the operations of the Agent."""
        operations = super().register_operations()
        operations[""] = operations.get("", []) + ["register_feedback"]
        return operations
    
    @override
    async def async_stream_query(
        self,
        *,
        message: Union[str, Dict[str, Any]],
        user_id: str,
        session_id: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterable[Dict[str, Any]]:
       async for item in super().async_stream_query(message=message, user_id=user_id, 
                                         session_id=session_id, run_config=run_config, **kwargs):
           yield item
       # After the stream is finished, add the session to long-term memory
       session = await super().async_get_session(user_id=user_id, session_id=session_id)
       await self.memory_service.add_session_to_memory(session)

# Environment variables for configuration
gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

# Create the Agent Engine instance
agent_engine = AgentEngineApp(
    agent=adk_app.root_agent,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
    session_service_builder=lambda: (
        VertexAiSessionService(project=project_id, location=gemini_location)
        if project_id
        else InMemorySessionService()
    ),
    memory_service_builder=lambda: CustomMemoryBankService(
        project=project_id,
        location=gemini_location,
    ),
)

if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("\n--- 🤖 Local Agent Test (ADK + Memory Bank) ---")
        user_query = "Hello, what's new today?"
        print(f"Query: {user_query}\n")

        # Set up a test session
        user_id = "local-test-user"
        
        # Test stream query
        print("Response: ", end="", flush=True)
        async for chunk in agent_engine.async_stream_query(
            message=user_query,
            user_id=user_id,
        ):
            if "content" in chunk:
                # Assuming chunk is a dict with content
                content = chunk["content"]
                if isinstance(content, dict) and "parts" in content:
                    for part in content["parts"]:
                        if "text" in part:
                            print(part["text"], end="", flush=True)
                elif isinstance(chunk, str):
                    print(chunk, end="", flush=True)
        print("\n\n--- Done ---")

    # Ensure required env vars are set or provide fallbacks for local test
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        print("Warning: GOOGLE_CLOUD_PROJECT not set. Using local services.")
    
    asyncio.run(main())
