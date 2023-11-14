# !/usr/bin/env python
# encoding: utf-8
"""
SEED Platform (TM), Copyright (c) Alliance for Sustainable Energy, LLC, and other contributors.
See also https://github.com/seed-platform/seed/main/LICENSE.md
"""
import os

import pandas as pd
import requests
from tqdm import tqdm


def update_quadkeys(quadkeys: list[int]):
    """
    Downloads a list of quadkeys
    Skip the download if it has already been downloaded, and it is up-to-date
    """
    df = pd.read_csv('data/quadkeys/dataset-links.csv')

    for quadkey in tqdm(quadkeys):
        download = True
        file = f"data/quadkeys/{quadkey}.geojsonl.gz"
        rows = df[df['QuadKey'] == quadkey]
        if rows.shape[0] == 1:
            url = rows.iloc[0]['Url']
        elif rows.shape[0] > 1:
            raise ValueError(f"Multiple rows found for QuadKey: {quadkey}")
        else:
            raise ValueError(f"QuadKey not found in dataset: {quadkey}")

        if os.path.exists(file):
            local_size = os.path.getsize(file)
            remote_size = int(requests.head(url).headers['Content-Length'])
            download = local_size != remote_size

        if download:
            with open(file, 'wb') as f:
                f.write(requests.get(url).content)
