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
            try:
                next(reader)  # Skip the header
            except StopIteration:
                raise ValueError(f"The file {file_path} is empty.")
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
        if not turns:
            raise ValueError(f"The file {file_path} contains no valid data.")
        return turns
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {file_path} was not found.")
    except ValueError as e:
        if "is empty" in str(e) or "contains no valid data" in str(e):
            raise e
        else:
            raise ValueError(f"Invalid data format in {file_path}.")
    except IndexError:
        raise ValueError(f"Invalid data format in {file_path}.")

def load_json_data(file_path):
    """Load data from a JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def create_map_with_points():
    """Create a Leaflet map with colored points"""
    
    # Load data
    turns = load_csv_data(TURNS_FILE)
    radionavs = load_json_data(RADIONAVS_FILE)
    waypoints = load_json_data(WAYPOINTS_FILE)
    
    # Calculate map center based on turns points
    center_lat = sum(point['latitude'] for point in turns) / len(turns)
    center_lon = sum(point['longitude'] for point in turns) / len(turns)
    
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
                bottom: 30px; left: 30px; width: 170px; height: 106px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><span style="color:red;">●</span> Turns ('''+str(len(turns))+''')</p>
    <p><span style="color:blue;">●</span> Radionavs ('''+str(len(radionavs))+''')</p>
    <p><span style="color:green;">●</span> Waypoints ('''+str(len(waypoints))+''')</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add a scale
    plugins.MeasureControl().add_to(m)

    # Save the map
    try:
        m.save(OUTPUT_FILE)
        return m
    except Exception as e:
        raise Exception(f"Error saving map: {e}")
    
def main():
    print("Generating navigation map...")
    
    try:
        map_obj = create_map_with_points()
        
        if map_obj:
            print(f"Map generated successfully in '{OUTPUT_FILE}'.")
        else:
            print("Failed to generate map.")
            
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)

if __name__ == "__main__":
    main()