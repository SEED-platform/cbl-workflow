import requests
from geopandas.geodataframe import GeoDataFrame
from geopy.geocoders import Nominatim
from shapely.geometry import Polygon

from .ubid import bounding_box, centroid, encode_ubid

OVERPASS_URL = "http://overpass-api.de/api/interpreter"


def reverse_geocode(lat, lon):
    """should only call at 1 per second per user agreement, no threaded calls either. This
    is per the license agreement"""
    geolocator = Nominatim(user_agent="CBL")
    location = geolocator.reverse((lat, lon), language="en", exactly_one=True)
    # print(location)
    return location.raw


def get_building_id_from_osm_id(place_id):
    # Define the Overpass query to retrieve the building ID based on osm ID
    overpass_query = f"""
    [out:json];
    (
      way(id:{place_id});
    );
    out ids;
    """

    # Send the Overpass query to the Overpass API
    response = requests.post(OVERPASS_URL, data=overpass_query)

    if response.status_code != 200:
        return "Error: Failed to retrieve building ID."

    data = response.json()
    # Extract the building ID from the response
    building_id = None
    for element in data["elements"]:
        if "id" in element:
            building_id = element["id"]
            break

    if building_id is None:
        return "Building ID not found for the given place ID."
    else:
        return building_id


def download_building(building_id):
    # Define the Overpass query to retrieve nodes of the specified building
    overpass_query = f"""
    [out:json];
    (
      way({building_id});
    );
    out center;
    """

    # Send the Overpass query to the Overpass API
    response = requests.post(OVERPASS_URL, data=overpass_query)

    if response.status_code != 200:
        print(f"Error: Failed to download building nodes for building ID {building_id}")
        return None

    data = response.json()

    return data["elements"][0]


def download_building_and_nodes_by_id(building_id):
    """Download the building from the OpenStreetMap API. The id is the id found in the this
    url: https://www.openstreetmap.org/way/55321750.

    Args:
        building_id (int): the OpenStreetMap building ID

    Returns:
        [dict, list]: The building id and nodes
    """
    # Define the Overpass query to retrieve nodes of the specified building
    overpass_query = f"""
    [out:json];
    (
      way({building_id});
    );
    out center;
    """

    # Send the Overpass query to the Overpass API
    response = requests.post(OVERPASS_URL, data=overpass_query)

    if response.status_code != 200:
        print(f"Error: Failed to download building nodes for building ID {building_id}")
        return None

    data = response.json()

    # Extract the nodes from the response
    nodes = []
    for element in data["elements"]:
        if "nodes" in element and len(element["nodes"]) > 0:
            nodes.extend(element["nodes"])

    return data, nodes


def get_node_coordinates(node_ids: list[int]):
    # Define an empty list to store the coordinates of all nodes
    node_coordinates = {}

    # Iterate over each node ID
    for node_id in node_ids:
        # Define the Overpass query for each node
        overpass_query = f"""
        [out:json];
        (
          node({node_id});
        );
        out;
        """

        # Send the Overpass query to the Overpass API
        response = requests.post(OVERPASS_URL, data=overpass_query)

        if response.status_code != 200:
            print(f"Error: Failed to retrieve coordinates for node ID {node_id}")
            return None

        data = response.json()

        # Extract the latitude and longitude coordinates of the node from the response
        for element in data["elements"]:
            if (
                "type" in element
                and element["type"] == "node"
                and "id" in element
                and "lat" in element
                and "lon" in element
            ):
                lat = float(element["lat"])
                lon = float(element["lon"])
                # Check if coordinates are within valid range
                if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    node_coordinates[node_id] = (lat, lon)
                else:
                    print(f"Invalid coordinates for node ID {node_id}: Latitude {lat}, Longitude {lon}")
                    continue

    polygon = [(x[1], x[0]) for x in node_coordinates.values()]
    if len(polygon) < 3:
        return None
    else:
        return Polygon(polygon)


def neighboring_buildings(location):
    """This doesn't appear to work, yet...."""
    geolocator = Nominatim(user_agent="CBL-neighbors")
    # Extract address information from the location
    address = location.get("address")

    # Extract street and city details (you can customize this based on your requirements)
    street = address.get("road", "")
    city = address.get("city", "")
    house_number = address.get("house_number", "")

    # Construct a query to find neighboring buildings
    query = f"{house_number} {street}, {city}"

    # Perform a search query to find neighboring buildings
    print(f"Searching for neighbors to {query}")
    search_results = geolocator.geocode(query, exactly_one=False)

    if not search_results:
        print("No neighboring buildings found.")

    # search by lat long
    query = f"{location.get('lat')},{location.get('lon')}"
    print(f"Searching by {query}")
    search_results = geolocator.reverse((), language="en", exactly_one=False)
    if not search_results:
        return "No neighboring buildings found based on lat/long."

    # Extract building names from the search results
    if not search_results:
        return "nothing found"
    else:
        # round new neighbors
        buildings = [result.address for result in search_results if "building" in result.raw.get("type", "")]
        return buildings


def find_nearest_building(lat, lon):
    """Return the nearest feature of type way and tags with building"""
    overpass_query = f"""
    [out:json];
    (
      way(around:50,{lat},{lon});  // radius (50 meters)
    );
    out;
    """

    # Send the Overpass query to the Overpass API
    response = requests.post(OVERPASS_URL, data=overpass_query)

    if response.status_code != 200:
        print(response.text)
        print("Error: Failed to retrieve data from Overpass API.")
        return

    data = response.json()

    # Check if any elements of the specified type were found
    if "elements" in data and len(data["elements"]) > 0:
        # this list is already sorted by closest
        for element in data["elements"]:
            # grab the first element that meets the criteria of
            #   type: way
            #   tags.buildings: [yes, retail]
            #   dcgis:dataset: "buildings", ??? <- not yet, this might be a DC specific thing

            if element["type"] != "way":
                continue

            if element.get("tags", {}).get("building", "") not in ["yes", "retail"]:
                continue

            return element

    else:
        print("Nothing found near the specified coordinates.")
        return None


def process_dataframe_for_osm_buildings(
    geodataframe: GeoDataFrame, method: str = "geometry_centroid"
) -> list[list, list]:
    """Process a dataframe that has a geometry column and return a list of nearest OSM buildings
    along with polygons of the building footprints.

    There are multiple paths through this code (and may warrant a bit of a rewrite), but the
    method enables 3 paths:
    1. 'geometry_centroid': Use the centroid of the geometry to find the nearest building. Data must be in the
       'geometry' column of the passed GeoDataFrame.
    2. 'osm_id': Use an already known building id to find the building in the OpenStreetMap database. Data must be in
       the 'osm_id' column of the passed GeoDataFrame.
    3. 'lat_long': Find the nearest building by a known latitude and longitude.  Data must be in
       the 'latitude', and 'longitude' column of the passed GeoDataFrame.

    Args:
        geodataframe (GeoDataFrame): Dataframe to process and add results to.
        method (str, optional): Which field contains the geo data. Defaults to 'geometry_centoid'.

    Returns:
        list[list, list]: The results in a dictionary format and a list of errors that occurred during processing.
    """

    # check that the method is valid
    if method not in ["geometry_centroid", "osm_id", "lat_long"]:
        raise ValueError(
            f"Invalid processing method: {method}, must be one of ['geometry_centroid', 'osm_id', 'lat_long']"
        )

    results = []
    error_processing = []
    for _index, row in geodataframe.iterrows():
        result = None
        if method in ["geometry_centroid", "lat_long"]:
            if method == "geometry_centroid":
                lat = row["geometry"].centroid.y
                lon = row["geometry"].centroid.x
            elif method == "lat_long":
                lat = row["latitude"]
                lon = row["longitude"]

            result = reverse_geocode(lat, lon)

            if result:
                # the info about the location is good, now check if the place/osm_id and see if it
                # is a way (building) or a node (point of interest), we only want buildings
                if result.get("osm_type") != "way":
                    # Find the nearest feature of the specified type from the specified coordinates
                    result_to_add = find_nearest_building(lat, lon)
                    if result_to_add is not None:
                        print(f"add: {result_to_add}")
                        result["osm_type"] = result_to_add["type"]
                        result["osm_id"] = result_to_add["id"]
                    else:
                        error_processing.append(f"No building found for row: {lat, lon}")

                # add in the originating row_id into the result so that we can match it up later
                result["orig_row_id"] = row["id"]

        elif method == "osm_id":
            result = {}
            result["osm_id"] = row["osm_id"]
            result["orig_row_id"] = row["id"]

        print(f"Looking for building id for row: {result['orig_row_id']}")
        building_id = get_building_id_from_osm_id(result["osm_id"])
        # save osm_building_id to the dataframe
        result["osm_building_id"] = building_id
        result["osm_building_id_url"] = f"https://www.openstreetmap.org/way/{building_id}"

        if isinstance(building_id, int):
            # get the nodes/coordinates for the building
            print("Downloading building nodes for building_id:", building_id)
            building, nodes = download_building_and_nodes_by_id(building_id)
            if nodes is not None:
                polygon = get_node_coordinates(nodes)

                if polygon is not None:
                    # convert to a polygon object
                    result["osm_polygon"] = polygon

            # save the other building information of interest, that lives in the tags elements
            if "tags" in building:
                for key in building["tags"]:
                    result[key] = building["tags"][key]

        # Save all the other fields in the dataframe to the result, if the fields are not
        # yet in the result.
        for key in row:
            if key not in result:
                result[key] = row[key]

        results.append(result)

    # pull out the columns in the results to useful fields
    for result in results:
        # convert boundingbox to polygon and save into results
        if "boundingbox" in result:
            bbox = [float(x) for x in result["boundingbox"]]
            bbox = Polygon([(bbox[2], bbox[0]), (bbox[3], bbox[0]), (bbox[3], bbox[1]), (bbox[2], bbox[1])])
            result["osm_buildingbox"] = bbox

            # delete the boundbox in result
            del result["boundingbox"]

        # convert address to fields
        address_keys = [
            "shop",
            "house_number",
            "road",
            "neighbourhood",
            "amenity",
            "building",
            "borough",
            "city",
            "county",
            "state",
            "postcode",
            "country",
            "country_code",
            "ISO3166-2-lvl4",
        ]
        if "address" in result:
            for key in address_keys:
                result[f"osm_{key}"] = result["address"].get(key, None)

            # check if any keys are not used in result['address'] not in address_keys
            for key in result["address"]:
                if key not in address_keys:
                    print(f"Address key was not converted to the result dataframe for {key}")

            del result["address"]

        # force osm_id to be an integer
        result["osm_id"] = int(result["osm_id"])

        # convert type to unknown if it is a 'yes' -- type is the "building type", sometimes
        if result.get("type", None) == "yes":
            result["type"] = "unknown"

        # ove the osm_polygon to the geometry
        if "osm_polygon" in result:
            result["geometry"] = result["osm_polygon"]
            del result["osm_polygon"]

        # calculate UBID
        result["ubid"] = encode_ubid(result["geometry"])
        result["ubid_bounding_box"] = bounding_box(result["ubid"])
        result["ubid_centroid"] = centroid(result["ubid"])

    return results, error_processing
