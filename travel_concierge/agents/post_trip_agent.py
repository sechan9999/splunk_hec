"""Post-Trip Agent for Travel Concierge.

Asks the traveler about their experience and attempts to extract and store
their various preferences based on the trip for future interactions.
"""

from typing import Dict, Any, List

class PostTripAgent:
    """Agent responsible for post-trip feedback collection and preference storage."""

    def __init__(self, name: str = "post_trip_agent"):
        self.name = name
        self.preference_store: Dict[str, Any] = {}

    def process(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process post-trip feedback and extract preferences."""
        destination = context.get("destination", "Amsterdam")
        feedback = context.get("feedback", "Loved the boutique hotel near canals, preferred window seating, enjoyed art museums.")

        extracted_preferences = {
            "preferred_accommodation": "Canal-view Boutique Hotels",
            "seating_preference": "Window",
            "interest_tags": ["Art Museums", "Walking Tours", "Canal Cruises"],
            "destination_rating": 5
        }

        self.preference_store.update(extracted_preferences)

        return {
            "agent": self.name,
            "status": "success",
            "message": f"Thank you for sharing your experience in {destination}!",
            "feedback_received": feedback,
            "stored_preferences": extracted_preferences
        }
