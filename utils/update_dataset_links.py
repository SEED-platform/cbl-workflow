# !/usr/bin/env python
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/seed-platform/seed/main/LICENSE.md
"""

import base64
import hashlib
import os

import requests

file = "data/quadkeys/dataset-links.csv"
url = "https://minedbuildings.blob.core.windows.net/global-buildings/dataset-links.csv"


def update_dataset_links():
    """
    Downloads the csv with URLs for all quadkeys
    Skip the download if it has already been downloaded, and it is up-to-date
    """
    download = True
    if os.path.exists(file):
        local_md5 = base64.b64encode(hashlib.md5(open(file, "rb").read()).digest()).decode("UTF-8")
        remote_md5 = requests.head(url).headers["Content-MD5"]
        download = local_md5 != remote_md5
    if download:
        with open(file, "wb") as f:
            f.write(requests.get(url).content)
