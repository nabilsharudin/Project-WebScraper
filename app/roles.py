from __future__ import annotations


ACADEMIC_MARKERS = (
    "PENSYARAH",
    "PROFESOR",
    "LECTURER",
    "PROFESSOR",
)

INACTIVE_ACADEMIC_MARKERS = (
    "EMERITUS",
    "ADJUNCT",
    "ADJUNG",
    "VISITING",
    "PELAWAT",
    "AMAL BAKTI",
)


def is_lecturer_position(position: str) -> bool:
    """Return True for active lecturer/professor titles used by UTM."""
    normalized = " ".join((position or "").upper().split())
    if not normalized:
        return False
    return any(marker in normalized for marker in ACADEMIC_MARKERS) and not any(
        marker in normalized for marker in INACTIVE_ACADEMIC_MARKERS
    )

