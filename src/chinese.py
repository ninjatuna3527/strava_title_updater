"""Utilities for generating random Chinese characters.

The module intentionally avoids external dependencies. Characters are drawn
from the basic CJK Unified Ideographs block which provides common, printable
Han characters. This is sufficient for creating visually Chinese-like titles
for demonstration purposes.
"""

import random


def random_chinese(n: int = 4) -> str:
    """Return `n` random CJK Unified Ideographs as a string.

    Args:
        n: number of characters to generate.

    Returns:
        A string containing `n` random Han characters.
    """
    # CJK Unified Ideographs range
    return ''.join(chr(random.randint(0x4E00, 0x9FFF)) for _ in range(n))
