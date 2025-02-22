import folium
import random
import networkx as nx
from shapely.geometry import LineString, Polygon
import numpy as np
from queue import PriorityQueue
import time
import numpy as np
from scipy.spatial.distance import euclidean
import matplotlib.pyplot as plt
import cv2
import os
from selenium import webdriver
import re


# Coordinates for the corners of the main square
corner1 = (33.257833, -97.178783)  # 33°15'40.2"N 97°10'43.7"W
corner2 = (33.257583, -97.090917)  # 33°15'39.3"N 97°05'27.3"W
corner3 = (33.184682, -97.090917)
corner4 = (33.184682, -97.178783)

# Define latitude and longitude ranges based on the corners of the main square
min_lat = min(corner1[0], corner2[0], corner3[0], corner4[0])
max_lat = max(corner1[0], corner2[0], corner3[0], corner4[0])
min_lon = min(corner1[1], corner2[1], corner3[1], corner4[1])
max_lon = max(corner1[1], corner2[1], corner3[1], corner4[1])


# Create a map centered around Denton
denton_map = folium.Map(location=[33.2148, -97.1331], zoom_start=12)

# Define the coordinates for the main square
main_square_coordinates = [corner1, corner2, corner3, corner4]

# Create a polygon using the main square coordinates
main_square = Polygon(main_square_coordinates)

def find_low_battery_drones(drones):
    """
    Checks the battery levels of all drones and returns the names of drones with less than 40% battery.

    Args:
        drones (list of dict): A list of dictionaries, where each dictionary contains 'name' and 'battery' keys.

    Returns:
        list of str: Names of drones with less than 40% battery.
    """
    low_battery_drones = [drone['name'] for drone in drones if drone['battery'] < 40]
    return low_battery_drones


def lat_lon_to_grid(lat, lon):
    """
    Convert latitude and longitude to grid coordinates.

    Args:
        lat (float): Latitude.
        lon (float): Longitude.

    Returns:
        tuple: A tuple of grid coordinates (x, y).
    """
    grid_x = int((lat - min_lat) / (max_lat - min_lat) * grid_size)
    grid_y = int((lon - min_lon) / (max_lon - min_lon) * grid_size)
    return (grid_x, grid_y)


def find_nearest_store(end_cell, store_locations):
      # Calculate distances between end_cell and each store location
      distances = [euclidean(end_cell, store) for store in store_locations]

      # Find the index of the nearest store
      nearest_store_index = np.argmin(distances)

      # Return the coordinates of the nearest store
      return store_locations[nearest_store_index]


def find_nearest_station(drone_location, station_locations):
    """
    Finds the nearest charging station to a given drone location on the grid using Euclidean distance.

    Args:
        drone_location (tuple): The drone's current grid coordinates (x, y).
        station_locations (list of dicts): List of dictionaries containing station types and locations.

    Returns:
        tuple: The grid coordinates of the nearest charging station.
    """
    # Convert all station locations from lat/lon to grid coordinates
    grid_station_locations = [lat_lon_to_grid(station['location'][0], station['location'][1]) for station in station_locations]

    # Calculate distances using grid coordinates
    distances = [np.linalg.norm(np.array(drone_location) - np.array(loc)) for loc in grid_station_locations]

    # Find the index of the nearest station
    nearest_station_index = np.argmin(distances)

    # Return the grid coordinates of the nearest station
    return grid_station_locations[nearest_station_index]

def simulate_drone_movement(drone, station_locations):
    """
    Simulates moving a drone to the nearest charging station and back.

    Args:
        drone (dict): Drone information, including grid coordinates.
        station_locations (list of tuples): Latitudes and longitudes of charging stations.
    """
    with open('print_outputs.txt', 'w') as f:
      original_location = drone['location']  # Assume these are already grid coordinates
      f.write(f"{drone['name']} at grid location {original_location}. Searching for nearest charging station...\n")

      nearest_station = find_nearest_station(original_location, station_locations)

      f.write(f"{drone['name']} moving to nearest charging station at grid location {nearest_station}.\n")
      drone['location'] = nearest_station
      time.sleep(1)  # Simulate travel time

      f.write(f"{drone['name']} charging at the station...\n")
      x = drone['battery']
      drone['battery'] = 100
      f.write(f"battery charged: {100-x}'%\n")
      time.sleep(1)  # Simulate charging time
      drone['status'] = 'active'

      f.write(f"{drone['name']} returning to original location at grid location {original_location}.\n")
      drone['location'] = original_location
      time.sleep(1)  # Simulate return time

      f.write(f"{drone['name']} is back at location and fully charged.\n")

def heuristic(a, b):
    """Calculate the Manhattan distance between two points, adjusted for diagonal movement"""
    dx = abs(b[0] - a[0])
    dy = abs(b[1] - a[1])
    return dx + dy - min(dx, dy)


def least_cost_path_with_diagonals_and_cost(grid, start, end):
    """
    Perform A* search to find the least cost path in a grid, including diagonal movement,
    and return the path and its total cost.
    """
    neighbors = [(0, 1), (1, 0), (0, -1), (-1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    close_set = set()
    came_from = {}
    gscore = {start: 0}
    fscore = {start: heuristic(start, end)}
    oheap = PriorityQueue()
    oheap.put((fscore[start], start))

    # Initialize path and total_cost to default values
    path = []
    total_cost = 0

    while not oheap.empty():
        current = oheap.get()[1]

        if current == end:
            path = []
            total_cost = 0
            while current in came_from:
                path.append(current)
                current = came_from[current]
                if path:
                    total_cost += grid[path[-1][0]][path[-1][1]]
            path.reverse()
            path.insert(0, start)
            # Add the start cell cost since it's not included in the loop
            total_cost += grid[start[0]][start[1]]
            return path, total_cost

        close_set.add(current)
        for i, j in neighbors:
            neighbor = current[0] + i, current[1] + j
            if 0 <= neighbor[0] < grid.shape[0] and 0 <= neighbor[1] < grid.shape[1]:
                if i == 0 or j == 0:
                    # Horizontal or vertical movement
                    movement_cost = grid[neighbor[0]][neighbor[1]]
                else:
                    # Diagonal movement
                    movement_cost = grid[neighbor[0]][neighbor[1]] + 1

                tentative_g_score = gscore[current] + movement_cost

                if neighbor in close_set and tentative_g_score >= gscore.get(neighbor, float('inf')):
                    continue

                if tentative_g_score < gscore.get(neighbor, float('inf')) or neighbor not in [i[1] for i in oheap.queue]:
                    came_from[neighbor] = current
                    gscore[neighbor] = tentative_g_score
                    fscore[neighbor] = tentative_g_score + heuristic(neighbor, end)
                    oheap.put((fscore[neighbor], neighbor))

    # Return default values if no path is found
    return path, total_cost

import folium
import random

# Define the grid size
grid_size = 5

# Define the number of each type of cell
num_stores = 2
num_customers = 1
num_nfzs = 3
num_stations = 1

# Create a Folium map object centered on the main square
denton_map = folium.Map(location=[(max_lat + min_lat) / 2, (max_lon + min_lon) / 2], zoom_start=14)

# Calculate the step size for each grid cell
lat_step = (max_lat - min_lat) / grid_size
lon_step = (max_lon - min_lon) / grid_size

# Draw the grid on the map by adding lines
for i in range(grid_size + 1):
    folium.PolyLine([(min_lat + i * lat_step, min_lon), (min_lat + i * lat_step, max_lon)], color='grey', weight=1).add_to(denton_map)
    folium.PolyLine([(min_lat, min_lon + i * lon_step), (max_lat, min_lon + i * lon_step)], color='grey', weight=1).add_to(denton_map)

# Initialize the grid with +1 for all cells
grid = [[1 for _ in range(grid_size)] for _ in range(grid_size)]

# Generate all possible grid cell center points
all_grid_cells = [(min_lat + i * lat_step + lat_step / 2, min_lon + j * lon_step + lon_step / 2)
                  for i in range(grid_size) for j in range(grid_size)]

# Shuffle the list of grid cells and then take the first N cells for each type
random.shuffle(all_grid_cells)
store_cells = all_grid_cells[:num_stores]
customer_cells = all_grid_cells[num_stores:num_stores+num_customers]
nfz_cells = all_grid_cells[num_stores+num_customers:num_stores+num_customers+num_nfzs]
station_cells = all_grid_cells[num_stores+num_customers+num_nfzs:num_stores+num_customers+num_nfzs+num_stations]

# Convert grid indices back to latitude and longitude (placeholders for actual conversion)
store_locations = [{'type': 'store', 'location': (index[0], index[1])} for index in store_cells]
customer_locations = [{'type': 'customer', 'location': (index[0], index[1])} for index in customer_cells]
station_locations = [{'type': 'station', 'location': (index[0], index[1])} for index in station_cells]

# Initialize the grid with 'o' for all cells
char_grid = [['.' for _ in range(grid_size)] for _ in range(grid_size)]

# Update the char_grid with 's' for store cells
for cell in store_cells:
    i = int((cell[0] - min_lat) / lat_step)
    j = int((cell[1] - min_lon) / lon_step)
    char_grid[i][j] = 's'

# Update the char_grid with 'c' for customer cells
for cell in customer_cells:
    i = int((cell[0] - min_lat) / lat_step)
    j = int((cell[1] - min_lon) / lon_step)
    char_grid[i][j] = 'c'

for cell in station_cells:
    i = int((cell[0] - min_lat) / lat_step)
    j = int((cell[1] - min_lon) / lon_step)
    char_grid[i][j] = 'st'

# Print or use the char_grid as needed
for row in char_grid:
    print(' '.join(row))

# Update the grid with +10 for no-fly zones
for cell in nfz_cells:
    i = int((cell[0] - min_lat) / lat_step)
    j = int((cell[1] - min_lon) / lon_step)
    grid[i][j] = 10

# Place the stores, customers,stations and no-fly zones on the map
# Stores will be green markers
for cell in store_cells:
    folium.Marker(location=cell, icon=folium.Icon(color='green'), tooltip='Store').add_to(denton_map)

# Customers will be blue markers
for cell in customer_cells:
    folium.Marker(location=cell, icon=folium.Icon(color='blue'), tooltip='Customer').add_to(denton_map)

# Customers will be blue markers
for cell in station_cells:
    folium.Marker(location=cell, icon=folium.Icon(color='red'), tooltip='station').add_to(denton_map)


# No-fly zones will be red squares
for cell in nfz_cells:
    nfz_corner_lat = cell[0] - lat_step / 2
    nfz_corner_lon = cell[1] - lon_step / 2
    folium.Rectangle(
        bounds=[(nfz_corner_lat, nfz_corner_lon),
                (nfz_corner_lat + lat_step, nfz_corner_lon + lon_step)],
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.5
    ).add_to(denton_map)

# Initialize drones at store locations with grid coordinates
drones = []
for idx, cell in enumerate(store_cells):
    grid_i = int((cell[0] - min_lat) / lat_step)  # Row index in the grid
    grid_j = int((cell[1] - min_lon) / lon_step)  # Column index in the grid
    drones.append({
        'name': f'Drone_{idx + 1}',
        'location': (grid_i, grid_j),
        'battery': 100,  # Initial battery percentage
        'status' : 'active'
    })

# Print drone information using grid coordinates
for drone in drones:
    print(f"{drone['name']} : grid position {drone['location']} : {drone['battery']}% battery : status {drone['status']}")
     

# Battery tracking dictionary
battery_tracking = {drone['name']: [] for drone in drones}
profits = []

with open('print_outputs.txt', 'w') as f:
  x = 0
  for i in range(70):
    # Randomly select start and end positions from 's' and 'c' cells
    start_cell = random.choice([(i, j) for i in range(grid_size) for j in range(grid_size) if char_grid[i][j] == 's'])
    end_cell = random.choice([(i, j) for i in range(grid_size) for j in range(grid_size) if char_grid[i][j] == 'c'])
    grid = np.array(grid)
    # Find least cost path including diagonal movement and calculate total cost
    path, total_cost = least_cost_path_with_diagonals_and_cost(grid, start_cell, end_cell)
    f.write(f"Start position: {start_cell}\n")
    f.write(f"End position: {end_cell}\n")
    f.write(f"Least cost path with diagonals: {path}\n")
    f.write(f"Total cost of the path: {total_cost}\n")
    profits.append(total_cost)
    # Update drone based on path cost
    for drone in drones:
        battery_tracking[drone['name']].append(drone['battery'])
        if drone['location'] == start_cell:
            drone['location'] = end_cell
            drone['battery'] -= total_cost /2
            battery_tracking[drone['name']].append(drone['battery'])
            break

    #CHANGING TO INACTIVE
    for drone in drones:
      if(drone['battery']<40):
        drone['status'] = 'inactive'
    for drone in drones:
      f.write(f"{drone}\n")

    # Calculate the latitude and longitude step size for each grid cell
    lat_step_size = (max_lat - min_lat) / grid_size
    lon_step_size = (max_lon - min_lon) / grid_size

    # Convert grid cell indices in the path to latitude and longitude coordinates
    path_coordinates = [(min_lat + cell[0] * lat_step_size + lat_step_size / 2,
                        min_lon + cell[1] * lon_step_size + lon_step_size / 2) for cell in path]

    # Draw the path on the map with tooltips and random color (excluding red)
    import random

    # Draw the path on the map with tooltips and random dark color (excluding red)
    for i in range(len(path_coordinates) - 1):
        start_point = path_coordinates[i]
        end_point = path_coordinates[i + 1]
        path_info = f"From: {start_point}\nTo: {end_point} ......Total Cost {total_cost}....Fuel Consumption : {total_cost/2}%"  # Customize the tooltip content as needed

        # Generate random dark RGB values for the color (excluding red)
        color = "#{:02x}{:02x}{:02x}".format(random.randint(0, 127), random.randint(0, 127), random.randint(0, 127))
        folium.PolyLine([start_point, end_point], color=color, weight=2, tooltip=path_info).add_to(denton_map)


    # Assuming you have the store locations stored in a list called 'store_locations'
    store_locations = [(i, j) for i in range(grid_size) for j in range(grid_size) if char_grid[i][j] == 's']

    # Example usage
    nearest_store = find_nearest_store(end_cell, store_locations)
    f.write(f"Nearest store from end position: {nearest_store}\n")
    path_return, total_cost = least_cost_path_with_diagonals_and_cost(grid, end_cell, nearest_store)
    f.write(f"Start position: {end_cell}\n")
    f.write(f"nearest_store position: {nearest_store}\n")
    f.write(f"Least cost path with diagonals: {path}\n")
    f.write(f"Total cost of the path: {total_cost}\n")
    profits.append(total_cost)
    for drone in drones:
        if drone['location'] == end_cell:
            drone['location'] = nearest_store
            drone['battery'] -= total_cost / 2
            break

    # Calculate the latitude and longitude step size for each grid cell
    lat_step_size = (max_lat - min_lat) / grid_size
    lon_step_size = (max_lon - min_lon) / grid_size

    # Convert grid cell indices in the path to latitude and longitude coordinates
    path_coordinates = [(min_lat + cell[0] * lat_step_size + lat_step_size / 2,
                        min_lon + cell[1] * lon_step_size + lon_step_size / 2) for cell in path_return]

    for drone in drones:
      if drone['battery'] < 40:
          f.write(f"{drone['name']}\n")
          simulate_drone_movement(drone, station_locations)

    # Draw the path on the map with tooltips
    for i in range(len(path_coordinates) - 1):
        start_point = path_coordinates[i]
        end_point = path_coordinates[i + 1]
        path_info = f"From: {start_point}\nTo: {end_point}"  # Customize the tooltip content as needed
        folium.PolyLine([start_point, end_point], color='red', weight=2, tooltip=path_info).add_to(denton_map)

    denton_map.save(f'snapshots/map_snapshot_{x}.html')
    x = x +1
print("Print outputs saved to 'print_outputs.txt'.")




import seaborn as sns

# Using Seaborn to plot a KDE plot
plt.figure(figsize=(12, 6))
sns.kdeplot(profits, bw_adjust=0.5, fill=True)  # 'bw_adjust' controls the smoothness of the curve
plt.title('Density Plot of Profits')
plt.xlabel('Profits')
plt.ylabel('Density')
plt.show()


import matplotlib.pyplot as plt

# Assuming 'battery_tracking' is a dictionary with drone names as keys and lists of battery levels as values
for drone, batteries in battery_tracking.items():
    plt.plot(batteries, label=drone)

plt.title('Battery Levels Over Time for Each Drone')
plt.xlabel('Operation Index')
plt.ylabel('Battery Level (%)')
plt.legend()
plt.grid(True)
plt.show()



import seaborn as sns
import pandas as pd

# Convert the battery_tracking dictionary into a DataFrame for easier plotting
df = pd.DataFrame.from_dict(battery_tracking, orient='index').transpose()
sns.heatmap(df, annot=False, cmap='viridis', linewidths=.5)
plt.title('Heatmap of Battery Levels Across Operations')
plt.xlabel('Drones')
plt.ylabel('Operation Index')
plt.show()
