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

"""Translation tool for Travel Concierge."""

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from pydantic import BaseModel, Field


class Translation(BaseModel):
    """Translation of common phrases."""

    destination: str = Field(description="The city or country name")
    language: str = Field(description="The local language")
    phrases: dict[str, str] = Field(
        description="Dictionary of English phrase to Local phrase"
    )


def get_common_phrases(destination: str) -> dict:
    """Returns common phrases in the local language for a given destination.

    Args:
        destination: The city or country name (e.g., 'Amsterdam', 'Netherlands', 'Paris').

    Returns:
        Dictionary containing destination, local language, and essential phrases.
    """
    dest = destination.lower().strip() if destination else "amsterdam"
    if any(k in dest for k in ["amsterdam", "netherlands", "dutch"]):
        return {
            "destination": "Amsterdam, Netherlands",
            "language": "Dutch",
            "phrases": {
                "Hello": "Goedemorgen / Hallo",
                "Thank you": "Dank u wel",
                "Please": "Alstublieft",
                "Excuse me": "Pardon",
                "Help": "Help!",
                "Goodbye": "Tot ziens",
                "Where is the tram stop?": "Waar is de tramhalte?",
                "Do you speak English?": "Spreekt u Engels?"
            }
        }
    return {
        "destination": destination,
        "language": "Local Language",
        "phrases": {
            "Hello": "Hello",
            "Thank you": "Thank you",
            "Please": "Please",
            "Excuse me": "Excuse me",
            "Help": "Help!"
        }
    }


_translation_agent = Agent(
    model="gemini_flash_model_id",
    name="get_common_phrases_agent",
    description="Returns common phrases in the local language for a given destination.",
    instruction="""
You are a helpful travel translator.
Given a destination (city or country), identify the primary local language.
Then provide a dictionary of 5-10 essential travel phrases.
Include: Hello, Thank you, Please, Excuse me, Help, and any others that are culturally important.

Return the result strictly as a valid JSON object matching the Translation schema.
""",
    output_schema=Translation,
)

# AgentTool reference
translation_agent_tool = AgentTool(agent=_translation_agent)
