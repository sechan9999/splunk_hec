"""Pre-Trip Agent for Travel Concierge.

Invoked regularly before the trip starts. Fetches relevant trip information given
origin, destination, and nationality, and provides local language translation assistance when enabled.
"""

from typing import Dict, Any, List, Optional
from travel_concierge.tools.translation_tool import get_destination_translation

class PreTripAgent:
    """Agent responsible for pre-trip preparation, visa/entry requirements, health advisories,

    and local destination language translations.
    """

    def __init__(self, name: str = "pre_trip_agent", enable_translation_tool: bool = True):
        self.name = name
        self.enable_translation_tool = enable_translation_tool
        self.tools = []
        if enable_translation_tool:
            self.tools.append(get_destination_translation)

    def process(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process pre-trip preparation query."""
        origin = context.get("origin", "United States")
        destination = context.get("destination", "Amsterdam")
        nationality = context.get("nationality", "American")

        # Baseline info: entry requirements and travel advisories
        info = {
            "origin": origin,
            "destination": destination,
            "nationality": nationality,
            "visa_requirements": f"Passport valid for at least 3 months beyond intended stay. ETIAS authorization required for {nationality} citizens traveling to Schengen Area.",
            "travel_advisories": "No critical travel warnings. Ensure standard personal safety and bike lane awareness in Amsterdam.",
            "health_advisories": "Routine vaccinations recommended. Comprehensive travel insurance advised."
        }

        # Upgraded functionality: Execute translation tool if registered
        language_info = None
        if self.enable_translation_tool or "translate" in prompt.lower() or "phrase" in prompt.lower() or "language" in prompt.lower():
            if get_destination_translation in self.tools or self.enable_translation_tool:
                language_info = get_destination_translation(destination)

        response = {
            "agent": self.name,
            "status": "success",
            "message": f"Pre-trip preparation details for {nationality} traveler going from {origin} to {destination}:",
            "trip_info": info,
            "translation_tool_enabled": self.enable_translation_tool
        }

        if language_info:
            response["language_info"] = language_info

        return response
