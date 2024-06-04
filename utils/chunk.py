# !/usr/bin/env python
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/seed/blob/main/LICENSE.md
"""


def chunk(full_list: list, chunk_size: int = 100):
    return [full_list[i * chunk_size : (i + 1) * chunk_size] for i in range((len(full_list) + chunk_size - 1) // chunk_size)]
