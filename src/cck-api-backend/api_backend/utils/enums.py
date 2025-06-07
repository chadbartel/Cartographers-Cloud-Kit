# Standard Library
from enum import Enum


class AssetType(str, Enum):
    npc = "NPC"
    location = "Location"
    item = "Item"
    handout = "Handout"
    character_sheet = "Character Sheet"
    world_map = "World Map"
    campaign_notes = "Campaign Notes"
    lore = "Lore"
    custom = "Custom"
    other = "Other"
