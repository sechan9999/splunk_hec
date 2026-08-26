"""Planning Agent for Travel Concierge.

Given a destination, start date, and duration, helps the user select flights, seats,
and hotels, then generates an itinerary containing activities.
"""

from typing import Dict, Any, List

class PlanningAgent:
    """Agent responsible for flight search, hotel selection, seat assignment, and detailed itinerary planning."""

    def __init__(self, name: str = "planning_agent"):
        self.name = name

    def process(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process user planning request."""
        destination = context.get("destination", "Amsterdam")
        start_date = context.get("start_date", "2026-09-15")
        duration_days = context.get("duration_days", 4)
        origin = context.get("origin", "New York (JFK)")

        itinerary_items = [
            {
                "day": 1,
                "title": f"Arrival in {destination} & Hotel Check-in",
                "flight": f"Flight AF123 ({origin} -> {destination})",
                "seat": "14B (Window)",
                "hotel": "Grand Canal Boutique Hotel Amsterdam",
                "requires_payment": True,
                "cost_usd": 1250.00
            },
            {
                "day": 2,
                "title": "Rijksmuseum & Canal Cruise",
                "activity": "Rijksmuseum Guided Tour & Evening Canal Dining Cruise",
                "requires_payment": True,
                "cost_usd": 180.00
            },
            {
                "day": 3,
                "title": "Van Gogh Museum & Jordaan Neighborhood Walking Tour",
                "activity": "Van Gogh Entry & Local Food Tasting Tour",
                "requires_payment": True,
                "cost_usd": 110.00
            },
            {
                "day": 4,
                "title": "Departure & Souvenir Shopping",
                "activity": "Vondelpark walk and transfer to Schiphol Airport",
                "requires_payment": False,
                "cost_usd": 0.00
            }
        ]

        return {
            "agent": self.name,
            "status": "success",
            "message": f"Generated {duration_days}-day itinerary for {destination} starting {start_date}:",
            "destination": destination,
            "start_date": start_date,
            "duration_days": duration_days,
            "itinerary": itinerary_items,
            "total_estimated_cost": sum(item.get("cost_usd", 0) for item in itinerary_items)
        }
