"""Translation Tool for Travel Concierge Pre-Trip Agent.

Provides destination language phrases, phonetic guidance, and translations
for travelers visiting international destinations.
"""

from typing import Dict, List, Any, Optional

# Knowledge base of destination languages and useful phrases
LANGUAGE_DATABASE: Dict[str, Dict[str, Any]] = {
    "amsterdam": {
        "destination": "Amsterdam, Netherlands",
        "primary_language": "Dutch",
        "phrases": {
            "greetings": [
                {"english": "Hello / Good day", "local": "Goedemorgen / Hallo", "phonetic": "KHOOH-duh-mor-khuh / HAH-loh"},
                {"english": "Thank you very much", "local": "Dank u wel / Dank je wel", "phonetic": "dahnk oo vel / dahnk yuh vel"},
                {"english": "Please", "local": "Alstublieft", "phonetic": "ahlst-oo-BLEEFT"},
                {"english": "Goodbye", "local": "Tot ziens", "phonetic": "tot ZEENS"}
            ],
            "dining": [
                {"english": "A table for two, please", "local": "Een tafel voor twee, alstublieft", "phonetic": "ayn TAH-ful voor tway, ahlst-oo-BLEEFT"},
                {"english": "The bill, please", "local": "De rekening, alstublieft", "phonetic": "duh RAY-kuh-ning, ahlst-oo-BLEEFT"},
                {"english": "Delicious!", "local": "Heerlijk!", "phonetic": "HAIR-luhk!"},
                {"english": "Water, please", "local": "Water, alstublieft", "phonetic": "VAH-ter, ahlst-oo-BLEEFT"}
            ],
            "transit_directions": [
                {"english": "Where is the tram stop?", "local": "Waar is de tramhalte?", "phonetic": "vahr iz duh TRAM-hahl-tuh?"},
                {"english": "Where is Central Station?", "local": "Waar is Centraal Station?", "phonetic": "vahr iz sen-TRAHL stah-SYOHN?"},
                {"english": "How much is a ticket?", "local": "Hoeveel kost een kaartje?", "phonetic": "hoo-VAYL kost ayn KAHR-tyuh?"}
            ],
            "emergency": [
                {"english": "Help!", "local": "Help!", "phonetic": "HELP!"},
                {"english": "Where is the pharmacy?", "local": "Waar is de apotheek?", "phonetic": "vahr iz duh ah-poh-TAYK?"},
                {"english": "Do you speak English?", "local": "Spreekt u Engels?", "phonetic": "spraykt oo ENG-uls?"}
            ]
        },
        "tips": "English is widely spoken in Amsterdam, but greeting locals with 'Goedemorgen' or saying 'Dank u wel' is warmly appreciated."
    },
    "paris": {
        "destination": "Paris, France",
        "primary_language": "French",
        "phrases": {
            "greetings": [
                {"english": "Hello / Good day", "local": "Bonjour", "phonetic": "bohn-ZHOOR"},
                {"english": "Thank you very much", "local": "Merci beaucoup", "phonetic": "mair-SEE boh-KOO"},
                {"english": "Please", "local": "S'il vous plaît", "phonetic": "seel voo PLAY"}
            ],
            "dining": [
                {"english": "The bill, please", "local": "L'addition, s'il vous plaît", "phonetic": "lah-dee-SYOHN seel voo PLAY"}
            ]
        },
        "tips": "Always start interactions in Paris with a polite 'Bonjour'."
    },
    "tokyo": {
        "destination": "Tokyo, Japan",
        "primary_language": "Japanese",
        "phrases": {
            "greetings": [
                {"english": "Hello", "local": "Konnichiwa", "phonetic": "kohn-nee-chee-wah"},
                {"english": "Thank you", "local": "Arigatou gozaimasu", "phonetic": "ah-ree-GAH-too go-zahy-mahs"}
            ]
        },
        "tips": "Bowing slightly when saying thank you is customary in Japan."
    }
}


def get_destination_translation(destination: str, category: Optional[str] = None) -> Dict[str, Any]:
    """Fetches useful destination language phrases and translations.

    Args:
        destination: Destination city or country name (e.g., 'Amsterdam', 'Netherlands', 'Paris').
        category: Optional category filter ('greetings', 'dining', 'transit_directions', 'emergency').

    Returns:
        Dictionary containing language information, structured phrases, and tips.
    """
    dest_key = destination.lower().strip()
    
    # Matching exact or partial key (e.g., "Amsterdam, Netherlands" -> "amsterdam")
    matched_data = None
    for key, data in LANGUAGE_DATABASE.items():
        if key in dest_key or dest_key in key or dest_key in data["destination"].lower():
            matched_data = data
            break
            
    if not matched_data:
        # Fallback for generic/unlisted destinations
        return {
            "destination": destination,
            "primary_language": "Local Language",
            "phrases": {
                "greetings": [
                    {"english": "Hello", "local": "Hello / Local Greeting", "phonetic": "N/A"},
                    {"english": "Thank you", "local": "Thank you", "phonetic": "N/A"}
                ]
            },
            "tips": f"For {destination}, basic English is generally helpful, but downloading offline language translation is recommended."
        }

    if category and category in matched_data["phrases"]:
        return {
            "destination": matched_data["destination"],
            "primary_language": matched_data["primary_language"],
            "category": category,
            "phrases": matched_data["phrases"][category],
            "tips": matched_data["tips"]
        }

    return matched_data


def get_supported_languages() -> List[str]:
    """Returns list of destinations supported with custom translation dictionaries."""
    return [data["destination"] for data in LANGUAGE_DATABASE.values()]
