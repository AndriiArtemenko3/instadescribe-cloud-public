import copy
import json
import logging
import re
from pathlib import Path
from typing import Any

from config import MAX_KNOWN_CHARACTERS, MAX_PREVIOUS_SCENES

logger = logging.getLogger(__name__)


def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    return s


def dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for v in values:
        key = normalize_text(v)
        if key and key not in seen:
            seen.add(key)
            out.append(v.strip())
    return out


def load_memory(memory_file: Path) -> dict[str, Any]:
    if memory_file.exists():
        try:
            return json.loads(memory_file.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupt memory file {memory_file}: {e}") from e

    return {"characters": [], "scene_history": []}


def merge_character_into_memory(memory_chars, new_char) -> str:
    if not new_char.get("name"):
        raise ValueError(
            f"merge_character_into_memory: new_char missing required 'name' field: {new_char!r}"
        )
    new_name_norm = normalize_text(new_char["name"])
    new_aliases_norm = {normalize_text(a) for a in new_char.get("aliases", [])}

    for existing in memory_chars:
        existing_name_norm = normalize_text(existing["name"])
        existing_aliases_norm = {normalize_text(a) for a in existing.get("aliases", [])}

        if (
            new_name_norm == existing_name_norm
            or new_name_norm in existing_aliases_norm
            or existing_name_norm in new_aliases_norm
            or new_aliases_norm.intersection(existing_aliases_norm)
        ):
            existing["aliases"] = dedupe_strings(
                existing.get("aliases", []) + new_char.get("aliases", [])
            )

            if new_char.get("first_mention_label"):
                existing["first_mention_label"] = new_char["first_mention_label"]

            if new_char.get("pronoun"):
                existing["pronoun"] = new_char["pronoun"]

            existing["name_history"] = dedupe_strings(
                existing.get("name_history", []) + new_char.get("name_history", [])
            )

            existing["user_renamed"] = existing.get("user_renamed", False) or new_char.get(
                "user_renamed", False
            )

            return existing["id"]

    new_id = f"char_{len(memory_chars) + 1}"
    memory_chars.append(
        {
            "id": new_id,
            "name": new_char["name"],
            "first_mention_label": new_char.get(
                "first_mention_label", f"a {new_char['name'].lower()}"
            ),
            "pronoun": new_char.get("pronoun", "it"),
            "aliases": dedupe_strings(new_char.get("aliases", [])),
            "name_history": dedupe_strings(new_char.get("name_history", [])),
            "user_renamed": new_char.get("user_renamed", False),
        }
    )

    return new_id


def compress_memory(memory: dict[str, Any]) -> dict[str, Any]:
    chars = memory["characters"]
    scenes = memory["scene_history"]
    if len(chars) > MAX_KNOWN_CHARACTERS:
        logger.warning(
            "compress_memory: truncating %d characters to MAX_KNOWN_CHARACTERS=%d",
            len(chars),
            MAX_KNOWN_CHARACTERS,
        )
    if len(scenes) > MAX_PREVIOUS_SCENES:
        logger.warning(
            "compress_memory: truncating %d scenes to MAX_PREVIOUS_SCENES=%d",
            len(scenes),
            MAX_PREVIOUS_SCENES,
        )
    return {
        "known_characters": chars[:MAX_KNOWN_CHARACTERS],
        "recent_scene_history": scenes[-MAX_PREVIOUS_SCENES:],
    }


def remap_template_ids(template: str, id_map: dict[str, str]) -> str:
    """Replace temp_id prefixes inside token strings, e.g. {new_1_first} -> {char_1_first}."""
    for temp_id, canonical_id in id_map.items():
        if temp_id != canonical_id:
            template = template.replace(f"{{{temp_id}_", f"{{{canonical_id}_")
    return template


def remap_scene_character_ids(scene_character_ids: list[str], id_map: dict[str, str]) -> list[str]:
    remapped = []
    seen = set()

    for char_id in scene_character_ids:
        canonical_id = id_map.get(char_id, char_id)
        if canonical_id not in seen:
            seen.add(canonical_id)
            remapped.append(canonical_id)

    return remapped


def update_memory(memory: dict[str, Any], chunk_output: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(memory)

    mem_updates = chunk_output.get("memory_updates", {})
    temp_to_canonical: dict[str, str] = {}

    # Canonical IDs the model reused from memory — pass through directly
    for canonical_id in mem_updates.get("seen_character_ids", []):
        temp_to_canonical[canonical_id] = canonical_id

    # New characters — assign canonical IDs and record temp_id -> canonical mapping
    for new_char in mem_updates.get("new_characters", []):
        temp_id = new_char.get("temp_id")
        canonical_id = merge_character_into_memory(updated["characters"], new_char)
        if temp_id:
            temp_to_canonical[temp_id] = canonical_id

    # Store scenes with all IDs resolved to canonical form
    for scene in chunk_output.get("scenes", []):
        remapped_character_ids = remap_scene_character_ids(
            scene.get("character_ids", []), temp_to_canonical
        )
        remapped_ad_template = remap_template_ids(scene.get("ad_template", ""), temp_to_canonical)

        updated["scene_history"].append(
            {
                "chunk_id": chunk_output["chunk_id"],
                "scene_id": scene["scene_id"],
                "start": scene["start"],
                "end": scene["end"],
                "frame_indices": scene.get("frame_indices", []),
                "character_ids": remapped_character_ids,
                "ad": scene.get("ad", ""),
                "ad_template": remapped_ad_template,
            }
        )

    return updated
