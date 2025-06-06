# Standard Library
from enum import Enum


class ContentType(Enum, str):
    IMAGE_PNG = "image/png"
    IMAGE_JPEG = "image/jpeg"
    APPLICATION_PDF = "application/pdf"
    TEXT_PLAIN = "text/plain"
    APPLICATION_JSON = "application/json"
    APPLICATION_ZIP = "application/zip"
    AUDIO_MPEG = "audio/mpeg"
    VIDEO_MP4 = "video/mp4"


class AssetType(Enum, str):
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
