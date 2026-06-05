from src.chinese import random_chinese


def test_random_chinese_length():
    s = random_chinese(5)
    assert isinstance(s, str)
    assert len(s) == 5


def test_random_chinese_range():
    s = random_chinese(10)
    for ch in s:
        code = ord(ch)
        assert 0x4E00 <= code <= 0x9FFF
