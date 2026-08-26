"""Booking Agent for Travel Concierge.

Given an itinerary, helps process those items in the itinerary that require payment.
"""

from typing import Dict, Any, List

class BookingAgent:
    """Agent responsible for booking processing and payment execution."""

    def __init__(self, name: str = "booking_agent"):
        self.name = name

    def process(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process user booking and payment request."""
        itinerary = context.get("itinerary", [])
        
        payable_items = [item for item in itinerary if item.get("requires_payment", False)]
        total_amount = sum(item.get("cost_usd", 0) for item in payable_items)
        
        confirmations = []
        for index, item in enumerate(payable_items, 1):
            confirmations.append({
                "item_title": item.get("title"),
                "confirmation_code": f"CYMBAL-BK-2026-{index:04d}",
                "amount_paid": item.get("cost_usd"),
                "status": "CONFIRMED"
            })

        return {
            "agent": self.name,
            "status": "success",
            "message": f"Processed payment for {len(confirmations)} itinerary item(s).",
            "total_charged_usd": total_amount,
            "confirmations": confirmations
        }
