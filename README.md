# Building Data Utilities

> Building Data Utilities Workflow

Given a list of addresses, this workflow will automatically go through the following steps:

- Normalize each address - address consists of (at least) street, city, state. Could contain postal_code and country.
- Geocode each address via Amazon Location Services to a lat/long coordinate
- Download the [Microsoft Building Footprints](https://github.com/microsoft/GlobalMLBuildingFootprints/) for all areas encompassed by the geocoded coordinates
- Find the footprint that intersects (or is closest to) each geocoded coordinate
- Generate the UBID for each footprint
- Export the resulting data as csv and GeoJSON

### Prerequisites

1. Optionally create a Virtualenv Environment
2. Dependencies are managed through Poetry, install with `pip install poetry`
3. Install dependencies with `poetry install`
4. Create a `.env` file in the root with your Amazon Location Services API key in the following format. You will also need to specify the Amazon base url. If none is specified, the following will be used: https://places.geo.us-east-2.api.aws/v2. For NLR gateway, you will also need to specify an APP ID.

   ```dotenv
   AMAZON_API_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   AMAZON_BASE_URL=https://places.geo.us-east-2.api.aws/v2
   AMAZON_APP_ID=XXXXXXXXX
   ```

Note that if the env keys for AMAZON_API_KEY, AMAZON_BASE_URL, and AMAZON_APP_ID exist in your profile, then it use that over the .env file.

For NLR users using the rate-limited key, use the following as the AMAZON_BASE_URL: https://developer.nlr.gov/api/tada/amazon-location-service/places/v2

Due to the nature of this application, we are passing IntendedUse=Storage to the Amazon Location Services API. This results in a slightly higher rate per transaction, but allows us to store the results.

5. Create a `locations.json` file in the root containing a list of addresses to process in the format:

   ```json
   [
     {
       "street": "100 W 14th Ave Pkwy",
       "city": "Denver",
       "state": "CO"
     },
     {
       "street": "200 E Colfax Ave",
       "city": "Denver",
       "state": "CO"
     },
     {
       "street": "320 W Colfax Ave",
       "city": "Denver",
       "state": "CO"
     }
   ]
   ```

### Running the Workflow

1. Run the workflow with `python main.py` or `poetry run python main.py`
2. The results will be saved to `./data/covered-buildings.csv` and `./data/covered-buildings.geojson`. Example of these files are in the `tests/data` directory as well.

### Notes

- This workflow is optimized to be self-updating, and only downloads quadkeys and quadkey dataset-links if they haven't previously been downloaded or if an update is available
- Possible next steps:
  - Cache geocoding results (if allowed) to avoid API limit penalties when re-running
  - Allow other geocoders like Google, without persisting the geocoding results
  - Add distance from geocoded result to footprint boundary, `proximity_to_geocoding_coord` (intersections would be 0)

### Disclaimer

When using this tool with the Amazon Location Services geocoding API (or any other geocoder) always confirm that the terms of service allow for using and storing geocoding results. For Amazon Location Services, passing the IntendedUse=Storage parameter to each query allows the user to store the geocoding results.
