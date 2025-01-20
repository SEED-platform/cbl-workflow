# !/usr/bin/env python
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/SEED-platform/seed/blob/main/LICENSE.md
"""

import base64
import hashlib
from pathlib import Path

import requests

DATASET_URL = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"


def update_dataset_links(save_directory: Path = Path("data/quadkeys")):
    """
    Downloads the csv with URLs for all quadkeys
    Skip the download if it has already been downloaded, and it is up-to-date
    """
    # make sure the save directory exists
    save_directory.mkdir(parents=True, exist_ok=True)
    quadkey_links_file = save_directory / "dataset-links.csv"

    download = True
    if quadkey_links_file.exists():
        local_md5 = base64.b64encode(hashlib.md5(open(quadkey_links_file, "rb").read()).digest()).decode("UTF-8")
        remote_md5 = requests.head(DATASET_URL).headers["Content-MD5"]
        download = local_md5 != remote_md5

    if download:
        with open(quadkey_links_file, "wb") as f:
            f.write(requests.get(DATASET_URL).content)
