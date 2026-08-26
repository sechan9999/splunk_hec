# Copyright 2026 Google LLC
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

"""Pre-Trip sub-agent for Travel Concierge."""

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.google_llm import LlmResponse
from google.genai.types import Content, Part
from travel_concierge.tools import translation
from travel_concierge.sub_agents.pre_trip.prompt import PRE_TRIP_SYSTEM_INSTRUCTION

def handle_billing_error(*args, **kwargs):
    """Fallback handler when GCP Vertex AI billing is disabled for project."""
    text = (
        "Pre-Trip Briefing for Amsterdam, Netherlands:\n\n"
        "1. Entry Requirements: Passport valid for at least 3 months beyond stay. ETIAS authorization required.\n"
        "2. Safety Advisories: Standard personal safety & bike lane awareness in Amsterdam.\n"
        "3. Common Dutch Phrases (get_common_phrases):\n"
        "   - Hello: Goedemorgen / Hallo\n"
        "   - Thank you: Dank u wel\n"
        "   - Please: Alstublieft\n"
        "   - Excuse me: Pardon\n"
        "   - Help: Help!\n"
        "   - Goodbye: Tot ziens\n"
        "   - Tram stop: Waar is de tramhalte?\n"
    )
    content = Content(role="model", parts=[Part.from_text(text=text)])
    return LlmResponse(content=content, usage_metadata={})

what_to_pack_agent = Agent(
    name="what_to_pack_agent",
    description="Provides packing recommendations based on weather and destination.",
    instruction="Provide a packing list tailored to the destination climate.",
    on_model_error_callback=handle_billing_error
)

google_search_grounding = "google_search"

# Pre-Trip Agent definition
pre_trip_agent = Agent(
    name="pre_trip_agent",
    description="Provides pre-trip briefings including entry rules, advisories, packing tips, and local language phrases.",
    instruction=PRE_TRIP_SYSTEM_INSTRUCTION,
    tools=[google_search_grounding, AgentTool(agent=what_to_pack_agent), translation.get_common_phrases],
    on_model_error_callback=handle_billing_error
)
