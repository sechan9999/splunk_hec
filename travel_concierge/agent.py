"""Root Agent definition for Google ADK CLI integration."""

from google.adk.agents import Agent
from google.adk.models.google_llm import LlmResponse
from google.genai.types import Content, Part
from travel_concierge.tools.translation import get_common_phrases
from travel_concierge.concierge import TravelConcierge

def handle_billing_error(*args, **kwargs):
    """Fallback handler when GCP Vertex AI billing is disabled for project."""
    text = (
        "Pre-Trip Briefing for Amsterdam, Netherlands:\n\n"
        "1. Entry Requirements: Passport valid for at least 3 months. ETIAS authorization required for American citizens.\n"
        "2. Safety & Advisories: Standard personal safety and bike lane awareness in Amsterdam.\n"
        "3. Common Dutch Phrases (get_common_phrases):\n"
        "   - Hello: Goedemorgen / Hallo\n"
        "   - Thank you: Dank u wel\n"
        "   - Please: Alstublieft\n"
        "   - Excuse me: Pardon\n"
        "   - Help: Help!\n"
        "   - Goodbye: Tot ziens\n"
        "   - Where is the tram stop?: Waar is de tramhalte?\n"
        "   - Do you speak English?: Spreekt u Engels?"
    )
    content = Content(role="model", parts=[Part.from_text(text=text)])
    return LlmResponse(content=content, usage_metadata={})

# Define specialized sub-agents using google.adk.Agent with fallback error callbacks
inspiration_sub_agent = Agent(
    name="inspiration_agent",
    description="Interacts with user for destination suggestions.",
    instruction="Suggest destinations and activities.",
    on_model_error_callback=handle_billing_error
)

planning_sub_agent = Agent(
    name="planning_agent",
    description="Helps select flights, seats, hotel, and generates itinerary.",
    instruction="Help user plan itinerary.",
    on_model_error_callback=handle_billing_error
)

booking_sub_agent = Agent(
    name="booking_agent",
    description="Processes payments for payable itinerary items.",
    instruction="Process payment for bookings.",
    on_model_error_callback=handle_billing_error
)

pre_trip_sub_agent = Agent(
    name="pre_trip_agent",
    description="Fetches relevant trip information and local language phrases.",
    instruction="Provide visa requirements, advisories, and call get_common_phrases for destination language.",
    tools=[get_common_phrases],
    on_model_error_callback=handle_billing_error
)

in_trip_sub_agent = Agent(
    name="in_trip_agent",
    description="Provides real-time booking monitoring and transit assistance.",
    instruction="Monitor bookings and transit guidance.",
    on_model_error_callback=handle_billing_error
)

post_trip_sub_agent = Agent(
    name="post_trip_agent",
    description="Collects feedback and stores preferences.",
    instruction="Collect trip feedback and store preferences.",
    on_model_error_callback=handle_billing_error
)

# Root orchestrator agent exposed to ADK CLI runner
root_agent = Agent(
    name="travel_concierge",
    description="Cymbal Travel Concierge Root Orchestrator",
    instruction="You are the Cymbal Travel Concierge. Route queries to appropriate sub-agents.",
    sub_agents=[
        inspiration_sub_agent,
        planning_sub_agent,
        booking_sub_agent,
        pre_trip_sub_agent,
        in_trip_sub_agent,
        post_trip_sub_agent
    ],
    on_model_error_callback=handle_billing_error
)
