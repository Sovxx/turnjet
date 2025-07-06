import json
import csv
import folium
from folium import plugins
from pathlib import Path

TURNS_FILE = 'turns.csv'
RADIONAVS_FILE = 'resources/radionavs.json'
WAYPOINTS_FILE = 'resources/waypoints.json'

OUTPUT_FILE = 'navigation_map.html'

def load_csv_data(file_path):
    """Load data from a CSV file"""
    try:
        turns = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip the header
            for row in reader:
                if len(row) >= 6:
                    turns.append({
                        'timestamp': row[0],
                        'callsign': row[1].strip(),
                        'registration': row[2],
                        'icao24': row[3],
                        'latitude': float(row[4]),
                        'longitude': float(row[5])
                    })
        return turns
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return []
    except (ValueError, IndexError):
        print(f"Error: Invalid data format in {file_path}.")
        return []

def load_json_data(file_path):
    """Load data from a JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: The file {file_path} is not a valid JSON.")
        return []

def create_map_with_points():
    """Create a Leaflet map with colored points"""
    
    # Load data
    turns = load_csv_data(TURNS_FILE)
    radionavs = load_json_data(RADIONAVS_FILE)
    waypoints = load_json_data(WAYPOINTS_FILE)
    
    if not radionavs and not waypoints:
        print("No data to display on the map.")
        return
    
    # Calculate map center based on turns points
    if turns:
        center_lat = sum(point['latitude'] for point in turns) / len(turns)
        center_lon = sum(point['longitude'] for point in turns) / len(turns)
    else:
        center_lat, center_lon = 46.2276, 2.2137  # Center of France by default
    
    # Create the map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles='OpenStreetMap'
    )

    # Add red points for aircraft (turns)
    for turn in turns:
        folium.CircleMarker(
            location=[turn['latitude'], turn['longitude']],
            radius=6,
            popup=f"Aircraft: {turn['callsign']}<br>Registration: <a href=\"https://www.flightradar24.com/data/aircraft/{turn['registration']}\" target=\"_blank\" >{turn['registration']}</a><br>Time: {turn['timestamp']}",
            tooltip=f"Aircraft: {turn['callsign']}",
            color='red',
        ).add_to(m)

    # Add blue points for radionavs
    for radionav in radionavs:
        folium.CircleMarker(
            location=[radionav['latitude'], radionav['longitude']],
            radius=3,
            popup=f"Radionav: {radionav['code']}",
            tooltip=f"Radionav: {radionav['code']}",
            color='blue',
            fill=True,
            fillColor='blue',
            fillOpacity=0.7
        ).add_to(m)
    
    # Add green points for waypoints
    for waypoint in waypoints:
        folium.CircleMarker(
            location=[waypoint['latitude'], waypoint['longitude']],
            radius=3,
            popup=f"Waypoint: {waypoint['code']}",
            tooltip=f"Waypoint: {waypoint['code']}",
            color='green',
            fill=True,
            fillColor='green',
            fillOpacity=0.7
        ).add_to(m)

    # Add a legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 30px; left: 30px; width: 130px; height: 110px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><span style="color:red;">●</span> Turns ('''+str(len(turns))+''')</p>
    <p><span style="color:blue;">●</span> Radionavs</p>
    <p><span style="color:green;">●</span> Waypoints</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add a scale
    plugins.MeasureControl().add_to(m)

    # Save the map
    m.save(OUTPUT_FILE)
    
    return m

def main():
    print("Generating navigation map...")
    
    map_obj = create_map_with_points()
    
    if map_obj:
        print(f"Map generated successfully in '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()