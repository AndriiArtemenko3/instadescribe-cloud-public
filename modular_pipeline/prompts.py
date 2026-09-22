import json
from typing import Any

from frames import FrameItem, estimate_chunk_coverage


def build_developer_prompt() -> str:
    return (
        "You are an expert assistant for generating audio descriptions (AD) for blind and low-vision users.\n"
        "You will analyze a chronological sequence of sampled video frames.\n"
        "Your job is to identify semantically distinct scenes and write concise, natural audio descriptions.\n\n"
        "Rules:\n"
        "1. The frames are in chronological order.\n"
        "2. Group consecutive frames into semantically coherent scenes.\n"
        "3. A scene should change only when the meaning, location, subject focus, major action, or on-screen situation changes.\n"
        "4. Do not split scenes because of tiny pose changes or minor camera noise.\n"
        "5. Write each AD as 1 to 3 sentences.\n"
        "6. Avoid repetitive background details unless they matter or change.\n"
        "7. Reuse previously established character identities from memory when appropriate.\n"
        "8. Prefer stable, useful naming for recurring characters.\n"
        "9. Return strict JSON only that matches the provided schema.\n"
        "10. Each frame must belong to exactly one scene in chronological order.\n"
        "11. Character memory updates should contain only identity information: name, first_mention_label, pronoun, aliases, name_history, user_renamed.\n"
        "12. Do not include character attributes, plot summaries, or action history in memory updates.\n"
        "13. CHARACTER ID RULES (critical):\n"
        "    a. For characters already listed in known_characters: use their exact `id` value (e.g. char_1) in scene `character_ids` and in `memory_updates.seen_character_ids`. Do NOT redeclare them in `new_characters`.\n"
        "    b. For characters NOT yet in known_characters: declare them in `memory_updates.new_characters` with a temp_id like `new_1`, `new_2`, and reference those same temp_ids in scene `character_ids`.\n"
        "    c. Never invent IDs like `c1`, `c2`, or reuse canonical IDs (char_N) for new characters.\n"
        "14. AD TEMPLATE RULES:\n"
        "    Each scene has two fields: `ad` and `ad_template`.\n"
        "    `ad`: natural language description exactly as it would be read aloud.\n"
        "    `ad_template`: identical to `ad` but with every character reference replaced by a token:\n"
        "      - First mention of a character in a scene: {CHAR_ID_first}  (e.g. {char_1_first} or {new_1_first})\n"
        "      - Subsequent subject pronoun (he/she/they): {CHAR_ID_subj}  (e.g. {char_1_subj})\n"
        "      - Subsequent object pronoun (him/her/them): {CHAR_ID_obj}\n"
        "      - Subsequent possessive pronoun (his/her/their): {CHAR_ID_poss}\n"
        "      - Capitalised variants: {CHAR_ID_subj_cap}, {CHAR_ID_obj_cap}, {CHAR_ID_poss_cap}\n"
        "    Use the character's canonical id (e.g. char_1) or temp_id (e.g. new_1) as CHAR_ID.\n"
        "    If no characters appear in a scene, `ad_template` must equal `ad`.\n"
    )


def build_user_text(
    chunk_id: int,
    chunk: list[FrameItem],
    memory_context: dict[str, Any],
    user_custom_context: str = "",
) -> str:
    chunk_start, chunk_end = estimate_chunk_coverage(chunk)

    frame_lines = []
    for local_idx, frame in enumerate(chunk):
        frame_lines.append(
            f"- local_frame_index={local_idx}, global_frame_index={frame.index}, timestamp={frame.timestamp:.1f}s"
        )

    custom_context_block = ""
    if user_custom_context.strip():
        custom_context_block = f"User-provided guidance:\n{user_custom_context.strip()}\n\n"

    return (
        f"Analyze this chunk of video frames.\n\n"
        f"chunk_id: {chunk_id}\n"
        f"chunk_start: {chunk_start:.1f}\n"
        f"chunk_end: {chunk_end:.1f}\n\n"
        f"Known characters (reuse their exact `id` in scene character_ids and seen_character_ids):\n"
        f"{json.dumps(memory_context.get('known_characters', []), indent=2, ensure_ascii=False)}\n\n"
        f"Recent scene history:\n"
        f"{json.dumps(memory_context.get('recent_scene_history', []), indent=2, ensure_ascii=False)}\n\n"
        f"{custom_context_block}"
        f"Frame metadata in chronological order:\n"
        f"{chr(10).join(frame_lines)}\n\n"
        f"Task:\n"
        f"- Identify semantically different scenes inside this chunk.\n"
        f"- Group consecutive frames into those scenes.\n"
        f"- For each scene, write a concise AD of 1 to 3 sentences.\n"
        f"- Add memory updates only for recurring characters or newly established characters.\n"
        f"- Keep naming consistent with memory when appropriate.\n"
        f"- Use stable character ids and link scenes to those ids.\n"
        f"- Prefer natural labels for narration.\n"
        f"- If the same character continues across scenes, avoid awkward renaming.\n"
        f"- Use pronouns only when they are fully clear.\n"
        f"- Do not include character attributes, plot summaries, or event summaries in memory updates.\n"
        f"- If user guidance is provided, follow it while keeping the output accurate, accessible, and grounded in the frames.\n"
        f"- For each scene, also fill `ad_template`: copy `ad` and replace every character reference with the appropriate {{CHAR_ID_first}}/{{CHAR_ID_subj}}/{{CHAR_ID_poss}} token.\n"
    )
