"""Inspiration Agent for Travel Concierge.

Interacts with the user to make suggestions on destinations and activities,
inspiring the user to choose one.
"""

from typing import Dict, Any, List

class InspirationAgent:
    """Agent responsible for vacation inspiration, destination ideas, and activity recommendations."""

    def __init__(self, name: str = "inspiration_agent"):
        self.name = name

    def process(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process user inspiration request."""
        destination = context.get("destination", "Amsterdam")
        interests = context.get("interests", ["culture", "museums", "dining", "canals"])

        suggestions = [
            f"Explore the historical canals of {destination} on a scenic boat tour.",
            f"Visit world-class museums such as the Rijksmuseum and Van Gogh Museum in {destination}.",
            f"Stroll through charming historic neighborhoods and sample local culinary specialties."
        ]

        return {
            "agent": self.name,
            "status": "success",
            "message": f"Inspiration recommendations for {destination}:",
            "suggestions": suggestions,
            "recommended_destination": destination
        }
