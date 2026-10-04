from app.roles import is_lecturer_position


def test_utm_academic_positions_are_included():
    assert is_lecturer_position("PENSYARAH")
    assert is_lecturer_position("PENSYARAH KANAN (SAF)")
    assert is_lecturer_position("PENSYARAH UNIVERSITI")
    assert is_lecturer_position("PROFESOR MADYA")
    assert is_lecturer_position("PROFESOR KHAS C")


def test_non_lecturer_and_inactive_positions_are_excluded():
    assert not is_lecturer_position("PENOLONG JURUTERA")
    assert not is_lecturer_position("PEMBANTU TADBIR (PERKERANIAN/OPERASI)")
    assert not is_lecturer_position("PROFESOR EMERITUS")
    assert not is_lecturer_position("")

