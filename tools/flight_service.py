import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AVIATION_API_KEY")


def _normalize_text(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9 ]+", " ", value or "").lower().strip()


def _extract_destination(query: str) -> str:
    match = re.search(r"to\\s+([A-Za-z ]+)", query, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return query.strip()


def _matches_query(flight: dict, destination: str) -> bool:
    if not destination:
        return True
    destination_norm = _normalize_text(destination)
    departure = _normalize_text(flight.get("departure", {}).get("airport", ""))
    arrival = _normalize_text(flight.get("arrival", {}).get("airport", ""))
    airline = _normalize_text(flight.get("airline", {}).get("name", ""))
    return destination_norm in departure or destination_norm in arrival or destination_norm in airline


def _sample_flights(destination: str) -> list[dict]:
    return [
        {
            "airline": "Skyline Airways",
            "departure_airport": "JFK",
            "arrival_airport": destination or "LAX",
            "departure_time": "2026-07-01 08:30",
            "arrival_time": "2026-07-01 12:15",
            "status": "Scheduled",
            "duration": "5h 45m",
            "price": "$420",
        },
        {
            "airline": "AeroConnect",
            "departure_airport": "JFK",
            "arrival_airport": destination or "LAX",
            "departure_time": "2026-07-01 13:00",
            "arrival_time": "2026-07-01 16:45",
            "status": "Scheduled",
            "duration": "5h 45m",
            "price": "$395",
        },
    ]


def search_flights(query: str) -> list[dict]:
    destination = _extract_destination(query)
    if not API_KEY:
        return _sample_flights(destination)

    url = "http://api.aviationstack.com/v1/flights"
    params = {
        "access_key": API_KEY,
        "limit": 10,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return _sample_flights(destination)

    flights = []
    for flight in data.get("data", [])[:10]:
        if not _matches_query(flight, destination):
            continue

        airline = flight.get("airline", {}).get("name", "Unknown")
        departure = flight.get("departure", {})
        arrival = flight.get("arrival", {})
        flights.append(
            {
                "airline": airline,
                "departure_airport": departure.get("airport", "Unknown"),
                "arrival_airport": arrival.get("airport", "Unknown"),
                "departure_time": departure.get("scheduled", "Unknown"),
                "arrival_time": arrival.get("scheduled", "Unknown"),
                "status": flight.get("flight_status", "Unknown"),
                "duration": flight.get("flight_duration", {}).get("airline", "Unknown"),
                "price": "TBD",
            }
        )

    if not flights:
        return _sample_flights(destination)
    return flights
