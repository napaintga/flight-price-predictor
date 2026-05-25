"""Normalize airline labels for model features and analytics."""

from __future__ import annotations

from typing import Any

import pandas as pd


AIRLINE_ALIASES = {
    "aegean": "Aegean",
    "aer lingus": "Aer Lingus",
    "air baltic": "Air Baltic",
    "air corsica": "Air Corsica",
    "air dolomiti": "Air Dolomiti",
    "air europa": "Air Europa",
    "air france": "Air France",
    "air maroc": "Royal Air Maroc",
    "air serbia": "Air Serbia",
    "austrian": "Austrian Airlines",
    "austrian airlines": "Austrian Airlines",
    "ba": "British Airways",
    "british airways": "British Airways",
    "brussels airlines": "Brussels Airlines",
    "croatia": "Croatia Airlines",
    "croatia airlines": "Croatia Airlines",
    "discover airlines": "Discover Airlines",
    "easyjet": "easyJet",
    "edelweiss air": "Edelweiss Air",
    "egyptair": "EgyptAir",
    "el al": "El Al",
    "ethiopian": "Ethiopian Airlines",
    "ethiopian airlines": "Ethiopian Airlines",
    "eurowings": "Eurowings",
    "finnair": "Finnair",
    "iberia": "Iberia",
    "icelandair": "Icelandair",
    "ita": "ITA Airways",
    "ita airways": "ITA Airways",
    "klm": "KLM",
    "klm royal dutch airlines": "KLM",
    "km malta airlines": "KM Malta Airlines",
    "loganair": "Loganair",
    "lot": "LOT Polish Airlines",
    "lot polish airlines": "LOT Polish Airlines",
    "lufthansa": "Lufthansa",
    "lufthansa city airlines": "Lufthansa City Airlines",
    "lufthansa cityline": "Lufthansa City Airlines",
    "luxair": "Luxair",
    "mea": "MEA",
    "norwegian": "Norwegian",
    "royal air maroc": "Royal Air Maroc",
    "ryanair": "Ryanair",
    "ryanair uk": "Ryanair",
    "sas": "Scandinavian Airlines",
    "scandinavian airlines": "Scandinavian Airlines",
    "swiss": "SWISS",
    "swiss international air lines": "SWISS",
    "tap air portugal": "TAP Air Portugal",
    "tap portugal": "TAP Air Portugal",
    "transavia": "Transavia",
    "tunisair": "Tunisair",
    "turkish airlines": "Turkish Airlines",
    "twin jet": "Twin Jet",
    "volotea": "Volotea",
    "vueling": "Vueling",
    "vueling airlines": "Vueling",
    "wizz": "Wizz Air",
    "wizz air": "Wizz Air",
}


def _clean_component(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_airline_component(value: Any) -> str:
    if pd.isna(value):
        return "Unknown"
    text = _clean_component(str(value))
    if not text:
        return "Unknown"
    key = text.casefold()
    return AIRLINE_ALIASES.get(key, text)


def normalize_airline_value(value: Any) -> str:
    if pd.isna(value):
        return "Unknown"
    text = str(value).strip()
    if not text:
        return "Unknown"

    components = [
        normalize_airline_component(part)
        for part in text.split(",")
        if str(part).strip()
    ]
    if not components:
        return "Unknown"

    deduped = list(dict.fromkeys(component for component in components if component != "Unknown"))
    if not deduped:
        return "Unknown"

    deduped.sort(key=lambda item: item.casefold())
    return ", ".join(deduped)
