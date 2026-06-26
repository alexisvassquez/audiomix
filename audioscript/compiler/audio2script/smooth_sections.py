# audiomix
# AudioMIX
# audioscript/compiler/audio2script/smooth_sections.py

from typing import List
from audioscript.compiler.audio2script.script_ir import Section

"""
Section Smoother - merges micro-sections into larger musical phrases.

Inputs: a list of Section(start, end, label)
Outputs: a cleaner, merged list of Section objs
"""

# Configurable thresholds
MIN_SECTION_DURATION = 0.50    # min seconds a section must have
MERGE_GAP_THRESHOLD = 0.20     # merge adjacent sections if small gap
UNLABELED_PREFIX = "section"   # identifies micro-sections

# Mode helper
# Determine whether to apply micro-mode (small audio files) or full-song mode
def choose_smoothing_mode(sections: List[Section]) -> str:
    if not sections:
        return "full"

    total_duration = sections[-1].end - sections[0].start

    if total_duration < 30.0:
        return "micro"

    return "full"

# Full-sized track merging logic
# Merge sections based on duration, labels, adjacency
def merge_full_sections(sections: List[Section]) -> List[Section]:
    if not sections:
        return sections

    merged = []
    current = sections[0]

    for nxt in sections[1:]:
        # Rule 1: merge unlabeled micro-sections
        is_unlabeled = (current.label.startswith(UNLABELED_PREFIX) or
                        nxt.label.startswith(UNLABELED_PREFIX))

        too_short = (current.duration() < MIN_SECTION_DURATION or
                     nxt.duration() < MIN_SECTION_DURATION)

        small_gap = abs(nxt.start - current.end) <= MERGE_GAP_THRESHOLD

        if is_unlabeled or too_short or small_gap:
            # Merge into one larger musical block
            current = Section(
                start=current.start,
                end=nxt.end,
                label=current.label
            )
        else:
            merged.append(current)
            current = nxt

    merged.append(current)

    # Rule 2: After merging, rename long unlabeled runs
    final = []
    phrase_counter = 1

    for sec in merged:
        if sec.label.startswith(UNLABELED_PREFIX):
            new_label = f"phrase{phrase_counter}"
            phrase_counter += 1
        else:
            new_label = sec.label

        final.append(Section(sec.start, sec.end, new_label))

    return final

# Top Level Entry Point
"""
Adaptive section smoothing based on audio duration.
- short audio (<30s) returns one big "sample" section
- long audio (>=30s) merges and renames sections
"""
def smooth_sections(sections: List[Section]) -> List[Section]:
    mode = choose_smoothing_mode(sections)

    if mode == "micro":
        if not sections:
            return []
        # collapse everything into one meaningful region
        return [Section(sections[0].start, sections[-1].end, "sample")]

    # full track: apply merging logic
    return merge_full_sections(sections)
