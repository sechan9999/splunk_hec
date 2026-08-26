"""Travel Concierge Root Orchestrator.

Manages sub-agent lifecycle and dynamically routes user queries to the appropriate agent:
- inspiration_agent: Vacation ideas and recommendations
- planning_agent: Flight, hotel, seat selection, itinerary planning
- booking_agent: Payment processing for itinerary items
- pre_trip_agent: Pre-trip requirements, advisories, and destination language translations
- in_trip_agent: Live monitoring, guiding, transit assistance
- post_trip_agent: Post-trip feedback and preference extraction
"""

from typing import Dict, Any, Optional
from travel_concierge.agents import (
    InspirationAgent,
    PlanningAgent,
    BookingAgent,
    PreTripAgent,
    InTripAgent,
    PostTripAgent
)

class TravelConcierge:
    """Root multi-agent orchestrator for Cymbal Travel Concierge."""

    def __init__(self, enable_pre_trip_translation: bool = True):
        self.inspiration_agent = InspirationAgent()
        self.planning_agent = PlanningAgent()
        self.booking_agent = BookingAgent()
        self.pre_trip_agent = PreTripAgent(enable_translation_tool=enable_pre_trip_translation)
        self.in_trip_agent = InTripAgent()
        self.post_trip_agent = PostTripAgent()
        
        self.agents = {
            "inspiration_agent": self.inspiration_agent,
            "planning_agent": self.planning_agent,
            "booking_agent": self.booking_agent,
            "pre_trip_agent": self.pre_trip_agent,
            "in_trip_agent": self.in_trip_agent,
            "post_trip_agent": self.post_trip_agent
        }

    def set_pre_trip_translation_enabled(self, enabled: bool) -> None:
        """Enable or disable translation tool on pre_trip_agent for testing baseline vs upgraded functionality."""
        self.pre_trip_agent = PreTripAgent(enable_translation_tool=enabled)
        self.agents["pre_trip_agent"] = self.pre_trip_agent

    def route_query(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Routes a prompt to the appropriate specialized agent based on context and intent keywords."""
        if context is None:
            context = {}

        prompt_lower = prompt.lower()
        target_agent = context.get("target_agent")

        # Dynamic routing rules
        if not target_agent:
            if any(k in prompt_lower for k in ["book", "pay", "checkout", "confirm payment"]):
                target_agent = "booking_agent"
            elif any(k in prompt_lower for k in ["inspire", "destination idea", "what to do", "suggest"]):
                target_agent = "inspiration_agent"
            elif any(k in prompt_lower for k in ["pre-trip", "before trip", "visa", "passport", "translate", "language", "phrases", "dutch", "advisory"]):
                target_agent = "pre_trip_agent"
            elif any(k in prompt_lower for k in ["in-trip", "transit", "tram", "museum direction", "live status", "during trip"]):
                target_agent = "in_trip_agent"
            elif any(k in prompt_lower for k in ["post-trip", "feedback", "rating", "review", "experience"]):
                target_agent = "post_trip_agent"
            elif any(k in prompt_lower for k in ["plan", "itinerary", "flight", "hotel", "seat", "dates"]):
                target_agent = "planning_agent"
            else:
                # Default route for pre-booking/pre-trip stage queries
                target_agent = "pre_trip_agent"

        agent = self.agents.get(target_agent, self.pre_trip_agent)
        return agent.process(prompt, context)
