import sys
from operator import itemgetter

import pandas as pd
from jarowinkler import jarowinkler_similarity

from utils.normalize_address import normalize_address

santa_monica = pd.read_excel('data/Santa Monica Covered Buildings.xlsx')
costar = pd.read_excel('data/OUO_Santa Monica All.xlsx')

santa_monica['CoStar Match'] = None
santa_monica['CoStar ID'] = None
santa_monica['CoStar Address'] = None

normalized_addresses = list(map(normalize_address, santa_monica['Street Address']))
normalized_costar_addresses = list(map(normalize_address, costar['Property Address']))

exact_matches = 0
for i, address in enumerate(normalized_addresses):
    print('==========', address)
    costar_matches = normalized_costar_addresses.count(address)
    if costar_matches == 1:
        print('  Found exact costar address:', address)
        exact_matches += 1

        costar_index = normalized_costar_addresses.index(address)
        santa_monica.at[i, 'CoStar Match'] = 'Exact'
        santa_monica.at[i, 'CoStar ID'] = costar.at[costar_index, 'PropertyID']
        santa_monica.at[i, 'CoStar Address'] = costar.at[costar_index, 'Property Address']
    elif costar_matches > 1:
        print('  !!! Found multiple exact costar addresses')
        santa_monica.at[i, 'CoStar Match'] = 'Multiple'
    else:
        closest_matches = sorted([(jarowinkler_similarity(address, costar_address), costar_address) for costar_address in normalized_costar_addresses], key=itemgetter(0), reverse=True)
        print('  Found closest costar address:', closest_matches[0][1])

        costar_index = normalized_costar_addresses.index(closest_matches[0][1])
        santa_monica.at[i, 'CoStar Match'] = 'Closest'
        santa_monica.at[i, 'CoStar ID'] = costar.at[costar_index, 'PropertyID']
        santa_monica.at[i, 'CoStar Address'] = costar.at[costar_index, 'Property Address']

print('Total:', len(normalized_addresses))
print('Exact matches:', exact_matches)
santa_monica.to_excel('data/Santa Monica Covered Buildings with CoStar.xlsx', index=False)
