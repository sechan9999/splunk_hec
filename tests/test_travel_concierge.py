"""Comprehensive unit and integration tests for Travel Concierge multi-agent system

and pre_trip_agent translation tool upgrade.
"""

import pytest
from travel_concierge.concierge import TravelConcierge
from travel_concierge.tools.translation_tool import get_destination_translation, get_supported_languages
from travel_concierge.agents import (
    InspirationAgent,
    PlanningAgent,
    BookingAgent,
    PreTripAgent,
    InTripAgent,
    PostTripAgent
)

def test_translation_tool_amsterdam():
    """Test translation tool returns Dutch phrases and phonetics for Amsterdam."""
    res = get_destination_translation("Amsterdam")
    assert res["destination"] == "Amsterdam, Netherlands"
    assert res["primary_language"] == "Dutch"
    assert "greetings" in res["phrases"]
    assert "dining" in res["phrases"]
    assert "emergency" in res["phrases"]
    
    greetings = res["phrases"]["greetings"]
    assert any("Goedemorgen" in g["local"] for g in greetings)
    assert any("Dank u wel" in g["local"] for g in greetings)


def test_translation_tool_category_filter():
    """Test category filtering in translation tool."""
    res = get_destination_translation("Amsterdam", category="dining")
    assert res["category"] == "dining"
    assert "phrases" in res
    assert any("tafel voor twee" in p["local"].lower() for p in res["phrases"])


def test_translation_tool_fallback():
    """Test fallback response for unsupported cities."""
    res = get_destination_translation("Atlantis")
    assert res["destination"] == "Atlantis"
    assert "phrases" in res


def test_pre_trip_agent_baseline_behavior():
    """Test baseline behavior of pre_trip_agent WITHOUT translation tool."""
    agent = PreTripAgent(enable_translation_tool=False)
    context = {"origin": "United States", "destination": "Amsterdam", "nationality": "American"}
    result = agent.process("Get pre-trip information", context)
    
    assert result["status"] == "success"
    assert result["translation_tool_enabled"] is False
    assert "visa_requirements" in result["trip_info"]
    assert "language_info" not in result


def test_pre_trip_agent_upgraded_behavior():
    """Test upgraded behavior of pre_trip_agent WITH translation tool enabled."""
    agent = PreTripAgent(enable_translation_tool=True)
    context = {"origin": "United States", "destination": "Amsterdam", "nationality": "American"}
    result = agent.process("Get pre-trip information and helpful phrases for Amsterdam", context)
    
    assert result["status"] == "success"
    assert result["translation_tool_enabled"] is True
    assert "visa_requirements" in result["trip_info"]
    assert "language_info" in result
    
    lang_info = result["language_info"]
    assert lang_info["primary_language"] == "Dutch"
    assert "greetings" in lang_info["phrases"]


def test_orchestrator_routing():
    """Test TravelConcierge orchestrator routing across all sub-agents."""
    concierge = TravelConcierge(enable_pre_trip_translation=True)
    context = {"destination": "Amsterdam", "origin": "Chicago", "nationality": "American"}
    
    # Pre-trip route
    res_pretrip = concierge.route_query("What visa and local Dutch phrases do I need?", context)
    assert res_pretrip["agent"] == "pre_trip_agent"
    assert "language_info" in res_pretrip
    
    # Inspiration route
    res_inspire = concierge.route_query("Can you inspire me with what to do in Amsterdam?", context)
    assert res_inspire["agent"] == "inspiration_agent"
    
    # Planning route
    res_plan = concierge.route_query("Plan an itinerary and search flights for Amsterdam", context)
    assert res_plan["agent"] == "planning_agent"
    
    # Booking route
    res_book = concierge.route_query("Process payment and book my itinerary", context)
    assert res_book["agent"] == "booking_agent"
    
    # In-trip route
    res_intrip = concierge.route_query("Check in-trip live transit and tram status", context)
    assert res_intrip["agent"] == "in_trip_agent"
    
    # Post-trip route
    res_posttrip = concierge.route_query("Submit feedback and rate my trip experience", context)
    assert res_posttrip["agent"] == "post_trip_agent"
