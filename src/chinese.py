import random

def random_chinese(n: int = 4) -> str:
    # CJK Unified Ideographs range
    return ''.join(chr(random.randint(0x4E00, 0x9FFF)) for _ in range(n))
