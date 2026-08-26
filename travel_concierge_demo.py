"""Travel Concierge Multi-Agent Demonstration Script.

Demonstrates:
1. Baseline system functionality (Pre-Trip Agent without translation tool).
2. Upgraded system functionality (Pre-Trip Agent with translation tool enabled).
3. End-to-end multi-agent orchestration for a trip to Amsterdam.
"""

import json
from travel_concierge import TravelConcierge

def print_section(title: str):
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def run_demo():
    customer_context = {
        "origin": "United States",
        "destination": "Amsterdam",
        "nationality": "American",
        "start_date": "2026-09-15",
        "duration_days": 4
    }

    print_section("SCENARIO: Customer Planning First Trip to Amsterdam, Netherlands")
    print(f"Customer Origin    : {customer_context['origin']}")
    print(f"Destination        : {customer_context['destination']}")
    print(f"Nationality        : {customer_context['nationality']}")
    print(f"Trip Start Date    : {customer_context['start_date']}")
    print(f"Trip Duration      : {customer_context['duration_days']} days\n")

    # 1. BASELINE FUNCTIONALITY (Before upgrade)
    print_section("STAGE 1: Baseline Functionality (Before Translation Tool Upgrade)")
    concierge_baseline = TravelConcierge(enable_pre_trip_translation=False)
    
    baseline_response = concierge_baseline.route_query(
        "I need pre-trip preparation for Amsterdam. What should I prepare?",
        customer_context
    )
    
    print(f"Agent Invoked               : {baseline_response['agent']}")
    print(f"Translation Tool Enabled    : {baseline_response['translation_tool_enabled']}")
    print("\n[Baseline Pre-Trip Info]")
    print(json.dumps(baseline_response["trip_info"], indent=2))
    print(f"\nLanguage Info Included?     : {'language_info' in baseline_response}")

    # 2. UPGRADED FUNCTIONALITY (After upgrade)
    print_section("STAGE 2: Upgraded Functionality (After Translation Tool Upgrade)")
    concierge_upgraded = TravelConcierge(enable_pre_trip_translation=True)
    
    upgraded_response = concierge_upgraded.route_query(
        "I need pre-trip preparation for Amsterdam. Can you also give me helpful local phrases?",
        customer_context
    )
    
    print(f"Agent Invoked               : {upgraded_response['agent']}")
    print(f"Translation Tool Enabled    : {upgraded_response['translation_tool_enabled']}")
    print("\n[Upgraded Pre-Trip Info]")
    print(json.dumps(upgraded_response["trip_info"], indent=2))
    
    print("\n[Local Language Translation Output (Dutch for Amsterdam)]")
    lang_info = upgraded_response.get("language_info", {})
    print(f"Primary Language : {lang_info.get('primary_language')}")
    print(f"Cultural Tip     : {lang_info.get('tips')}\n")
    print("Curated Essential Phrases:")
    for category, phrases in lang_info.get("phrases", {}).items():
        print(f"\n  -- {category.upper()} --")
        for p in phrases:
            print(f"  • English: {p['english']:<35} -> Local: {p['local']:<35} ({p['phonetic']})")

    # 3. END-TO-END MULTI-AGENT WORKFLOW DEMO
    print_section("STAGE 3: End-to-End Multi-Agent Concierge Workflow")
    queries = [
        ("Inspiration", "Inspire me with some unique things to do in Amsterdam!"),
        ("Planning", "Help me select flights, hotels, and plan a 4-day itinerary."),
        ("Booking", "Process payment for my flight and hotel bookings."),
        ("Pre-Trip", "Check visa requirements and local phrases before departure."),
        ("In-Trip", "Provide live tram guidance and check flight status during my trip."),
        ("Post-Trip", "Collect feedback on my trip experience.")
    ]

    for stage, query in queries:
        resp = concierge_upgraded.route_query(query, customer_context)
        print(f"[{stage}] User: '{query}'")
        print(f"         -> Handled by: {resp['agent']} | Status: {resp['status']}\n")

if __name__ == "__main__":
    run_demo()
