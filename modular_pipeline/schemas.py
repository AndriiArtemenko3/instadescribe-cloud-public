from typing import Any

from config import STRICT_JSON_SCHEMA

SCENE_SCHEMA: dict[str, Any] = {
    "name": "semantic_scene_ad_output",
    "strict": STRICT_JSON_SCHEMA,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "chunk_id": {"type": "integer"},
            "chunk_start": {"type": "number"},
            "chunk_end": {"type": "number"},
            "global_summary": {"type": "string"},
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "scene_id": {"type": "integer"},
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "frame_indices": {"type": "array", "items": {"type": "integer"}},
                        "character_ids": {"type": "array", "items": {"type": "string"}},
                        "ad": {"type": "string"},
                        "ad_template": {"type": "string"},
                        "reason_for_split": {"type": "string"},
                    },
                    "required": [
                        "scene_id",
                        "start",
                        "end",
                        "frame_indices",
                        "character_ids",
                        "ad",
                        "ad_template",
                        "reason_for_split",
                    ],
                },
            },
            "memory_updates": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "seen_character_ids": {"type": "array", "items": {"type": "string"}},
                    "new_characters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "temp_id": {"type": "string"},
                                "name": {"type": "string"},
                                "first_mention_label": {"type": "string"},
                                "pronoun": {"type": "string"},
                                "aliases": {"type": "array", "items": {"type": "string"}},
                                "name_history": {"type": "array", "items": {"type": "string"}},
                                "user_renamed": {"type": "boolean"},
                            },
                            "required": [
                                "temp_id",
                                "name",
                                "first_mention_label",
                                "pronoun",
                                "aliases",
                                "name_history",
                                "user_renamed",
                            ],
                        },
                    },
                },
                "required": ["seen_character_ids", "new_characters"],
            },
        },
        "required": [
            "chunk_id",
            "chunk_start",
            "chunk_end",
            "global_summary",
            "scenes",
            "memory_updates",
        ],
    },
}
