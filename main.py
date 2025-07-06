import configparser
import requests
import csv
import pandas as pd
import numpy as np
from shapely.geometry import LineString, Point
import math
import time
from datetime import datetime, timedelta
import logging
import matplotlib.pyplot as plt
import os

config = configparser.ConfigParser()
config.read("config.ini")

LAT = float(config["location"]["lat"])
if not (-90 <= LAT <= 90):
    raise ValueError("Latitude must be between -90 and 90°")
LON = float(config["location"]["lon"])
if not (-180 <= LON <= 180):
    raise ValueError("Longitude must be between -180 and 180°")
RADIUS = float(config["location"]["radius"])
if not (0 < RADIUS <= 250):
    raise ValueError("Radius must be between 0 and 250 NM")

MIN_ALT = int(config["altitude"]["min_alt"])
MAX_ALT = int(config["altitude"]["max_alt"])

DELAY = 20  # seconds

RECORDS_FILE = "records.csv"
TURNS_FILE = "turns.csv"
PLOTS_DIR = "aircraft_plots"

# Create directory for plots if it doesn't exist
os.makedirs(PLOTS_DIR, exist_ok=True)

API_URL = f"https://api.adsb.lol/v2/lat/{LAT}/lon/{LON}/dist/{RADIUS}"
"""
documentation :
https://api.adsb.lol/docs#/v2/v2_point_v2_lat__lat__lon__lon__dist__radius__get
example :
curl -X 'GET' 'https://api.adsb.lol/v2/lat/48.6058/lon/2.6717/dist/5' -H 'accept: application/json'
"""

logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("error.log"),  # File handler
        logging.StreamHandler()            # Stream handler for console output
    ]
)

def save_to_records(row):
    with open(RECORDS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def check_aircraft():
    """
    Add a record in the csv file if aircraft(s) found

    Returns:
        bool: True if aircraft(s) found
    """
    now = datetime.now()
    timestamp = now.replace(microsecond=0).isoformat()

    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        for ac in data.get("ac", []):
            callsign = ac.get("flight")  # ex: JAL924
            regis = ac.get("r")  # ex: F-GSEX
            hex = ac.get("hex")
            alt = ac.get("alt_baro")  # ft
            lat = ac.get("lat")
            lon = ac.get("lon")
            track = ac.get("track")  # aircraft own track in degrees
            
            if alt:
                if type(alt) is not int:  # ex "ground"
                    continue  # skip this aircraft
                # Filter aircraft by alt
                if not (MIN_ALT <= alt <= MAX_ALT):
                    continue  # skip this aircraft
        
            row = [
                timestamp,
                callsign,
                regis,
                hex,
                alt,
                lat,
                lon,
                track,
            ]
            save_to_records(row)

    except Exception as e:
        logging.error("API error: %s", e)
        return False

def process_aircraft_turns():
    """
    Analyze aircraft tracking data to detect direction changes
    and clean old data.
    """
    
    # Read RECORDS_FILE
    try:
        df = pd.read_csv(RECORDS_FILE)
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {RECORDS_FILE} was not found.")
    
    # Convert timestamps to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')

    # Calculate time limit (1 hour ago)
    current_time = datetime.now()
    one_hour_ago = current_time - timedelta(hours=1)
    
    # Identify aircraft detected more than an hour ago
    old_aircraft_mask = df['timestamp'] < one_hour_ago
    old_aircraft_hex = df[old_aircraft_mask]['hex'].unique()
    
    print(f"Number of aircraft detected more than an hour ago: {len(old_aircraft_hex)}")
    
    # List to store detected turns
    turns_data = []
    
    # Analyze each old aircraft
    for hex_code in old_aircraft_hex:
        aircraft_data = df[df['hex'] == hex_code].sort_values('timestamp').reset_index(drop=True)
        
        if len(aircraft_data) < 6:  # Need at least 6 points to detect a turn
            continue
            
        turns = detect_turns(aircraft_data)
        turns_data.extend(turns)
    
    # Write turns to TURNS_FILE
    if turns_data:
        with open(TURNS_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            for turn in turns_data:
                writer.writerow(turn)
        print(f"Number of turns detected: {len(turns_data)}")
    else:
        print("No turns detected.")
    
    # Remove old aircraft lines from DataFrame
    df_cleaned = df[~df['hex'].isin(old_aircraft_hex)]
    
    # Rewrite RECORDS_FILE without old aircraft
    df_cleaned.to_csv(RECORDS_FILE, header=True, index=False)

def detect_turns(aircraft_data):
    """
    Detects direction changes for a given aircraft using detect_segments_range.
    
    Args:
        aircraft_data (DataFrame): Specific aircraft data sorted by timestamp
        
    Returns:
        list: List of detected turns
    """
    turns = []
    
    # Check that we have enough data
    if len(aircraft_data) < 6:
        return turns
    
    # Filter data with valid track values
    valid_track_data = aircraft_data.dropna(subset=['track']).reset_index(drop=True)
    
    if len(valid_track_data) < 6:
        return turns
    
    # Extract track values
    tracks = valid_track_data['track'].values
    
    # Handle angle discontinuity (0°/360°)
    # Unwrap angles to avoid jumps from 360° to 0°
    tracks_unwrapped = np.unwrap(np.radians(tracks))
    tracks_unwrapped_degrees = np.degrees(tracks_unwrapped)
    
    try:
        print("#####################################")

        print(f"{tracks=}")
        print(f"{tracks_unwrapped_degrees=}")

        segments = detect_segments_range(
            tracks_unwrapped_degrees.tolist(),
            range_width=1.0,
            min_size=3
        )

        print_segments_simple(segments)
        
        transitions = extract_transitions(segments)

        print(f"{transitions=}")

        transitions = filter_transitions(
            transitions,
            tracks_unwrapped_degrees,
            min_angle=3.0
        )

        print(f"{transitions=}")

        # Generate plot for this aircraft
        hex_code = valid_track_data['hex'].iloc[0]
        plot_aircraft_tracks(hex_code, tracks, tracks_unwrapped_degrees, transitions, valid_track_data)
        
        # Process transitions 
        for i, j in transitions:
            
            # Estimate turn point (interpolation between i and j)
            turn_point = estimate_turn_point_from_indices(valid_track_data, i, j)
            
            if turn_point:
                # Create entry for TURNS_FILE
                turn_entry = [
                    turn_point['timestamp'].strftime('%Y-%m-%dT%H:%M:%S'),
                    turn_point['callsign'],
                    turn_point['regis'],
                    turn_point['hex'],
                    turn_point['lat'],
                    turn_point['lon']
                ]
            
                turns.append(turn_entry)
    
    except Exception as e:
        print(f"Error during turn detection: {e}")
    
    return turns


def detect_segments_range(table, range_width=2, min_size=2):
    """
    Detects segments composed of at least min_size values that fit 
    within a given range width.
    
    Args:
        table (list of float): The data to analyze.
        range_width (float): Maximum range width (max - min).
        min_size (int): Minimum size of a segment.
    
    Returns:
        list of dict: Each dictionary contains:
                     - 'start': start index of segment
                     - 'end': end index of segment (inclusive)
                     - 'values': list of segment values
                     - 'min': minimum value of segment
                     - 'max': maximum value of segment
                     - 'range': range width (max - min)
    """
    if len(table) < min_size:
        return []
    
    segments = []
    i = 0
    
    while i < len(table):
        # Start a new potential segment
        segment_start = i
        segment_end = i
        
        # Extend segment as long as range remains acceptable
        while segment_end < len(table):
            # Calculate range of current segment
            segment_values = table[segment_start:segment_end + 1]
            min_val = min(segment_values)
            max_val = max(segment_values)
            current_range = max_val - min_val
            
            # If range exceeds limit, stop extension
            if current_range > range_width:
                segment_end -= 1  # Return to last valid point
                break
            
            segment_end += 1
        
        # Adjust segment_end if we reached end of table
        if segment_end >= len(table):
            segment_end = len(table) - 1
        
        # Check if segment has minimum required size
        segment_size = segment_end - segment_start + 1
        if segment_size >= min_size:
            segment_values = table[segment_start:segment_end + 1]
            min_val = min(segment_values)
            max_val = max(segment_values)
            
            segments.append({
                'start': segment_start,
                'end': segment_end,
                'values': segment_values,
                'min': min_val,
                'max': max_val,
                'range': max_val - min_val
            })
        
        # Move to next point
        i = segment_end + 1
    
    return segments

def print_segments_simple(segments):
    """
    Displays segments concisely with their indices.
    
    Args:
        segments (list): List of segments returned by detect_segments_range
    """
    if not segments:
        print("No segments found")
        return
    
    print(f"{len(segments)} segment(s) found:")
    for i, seg in enumerate(segments):
        print(f"  Segment {i+1}: indices {seg['start']}-{seg['end']}")

def extract_transitions(segments):
    """
    Extracts transitions between consecutive segments.
    
    Args:
        segments (list): List of segments returned by detect_segments_range
    
    Returns:
        list of tuples: Each tuple (i, j) represents a transition where:
                       i = end index of previous segment
                       j = start index of following segment
    """
    if len(segments) < 2:
        return []
    
    transitions = []
    
    for i in range(len(segments) - 1):
        current_segment = segments[i]
        next_segment = segments[i + 1]
        
        current_end = current_segment['end']
        next_start = next_segment['start']
        
        transitions.append((current_end, next_start))
    
    return transitions

def filter_transitions(transitions, tracks_unwrapped_degrees, min_angle=3.0):
    """
    Eliminates transitions with angle less than min_angle
    """
    filtered_transitions = []

    for i, j in transitions:
        angle_diff = abs(tracks_unwrapped_degrees[j] - tracks_unwrapped_degrees[i])
        if angle_diff >= min_angle:
            filtered_transitions.append((i, j))

    return filtered_transitions

def estimate_turn_point_from_indices(aircraft_data, i, j):
    """
    Estimates turn point as intersection point between:
    - Half-line from point i in direction of track at point i
    - Half-line from point j in opposite direction of track at point j
    
    Plane approximation (2D), with Shapely.
    """
    point_i = aircraft_data.iloc[i]
    point_j = aircraft_data.iloc[j]

    lat1, lon1, track1 = point_i['lat'], point_i['lon'], point_i['track']
    lat2, lon2, track2 = point_j['lat'], point_j['lon'], (point_j['track'] + 180) % 360

    # Arbitrary length to extend half-lines (in km)
    extension_km = 100

    def extend(lat, lon, track_deg, extension_km):
        """
        Extends a point (lat, lon) in direction `track_deg` over `extension_km` kilometers.
        Corrects latitude for longitude conversion factor.
        """
        angle_rad = math.radians(track_deg)

        # Conversion: 1° lat ≈ 111 km ; 1° lon ≈ 111 * cos(lat)
        delta_lat = (extension_km / 111.0) * math.cos(angle_rad)
        delta_lon = (extension_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(angle_rad)

        new_lat = lat + delta_lat
        new_lon = lon + delta_lon
        return (new_lon, new_lat)

    # Build two segments (half-lines)
    p1 = (lon1, lat1)
    p2 = extend(lat1, lon1, track1, extension_km)

    q1 = (lon2, lat2)
    q2 = extend(lat2, lon2, track2, extension_km)

    line1 = LineString([p1, p2])
    line2 = LineString([q1, q2])

    intersection = line1.intersection(line2)

    if intersection.is_empty or not isinstance(intersection, Point):
        # Fallback: we'll ignore this intersection
        print(f"[Fallback] i={i}, j={j}")
        print(f"  Point i: lat={lat1}, lon={lon1}, track={track1}")
        print(f"  Point j: lat={lat2}, lon={lon2}, track(opposite)={track2}")
        print(f"  Line1: {p1} -> {p2}")
        print(f"  Line2: {q1} -> {q2}")
        plot_debug(p1, p2, q1, q2)
        return False
    
    else:
        lon_mid, lat_mid = intersection.x, intersection.y

    turn_point = {
        'timestamp': point_i['timestamp'] + (point_j['timestamp'] - point_i['timestamp']) / 2,
        'callsign': point_i['callsign'],
        'regis': point_i['regis'],
        'hex': point_i['hex'],
        'lat': lat_mid,
        'lon': lon_mid
    }

    return turn_point

def plot_debug(p1, p2, q1, q2, intersection=None):
    """
    Displays the two lines with matplotlib, to visually diagnose absence of intersection.
    """
    plt.figure(figsize=(8, 8))
    plt.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', label='Line i (track)')
    plt.plot([q1[0], q2[0]], [q1[1], q2[1]], 'b-', label='Line j (opposite track)')

    if intersection and not intersection.is_empty:
        plt.plot(intersection.x, intersection.y, 'go', label='Intersection')

    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Visualization of crossing lines")
    plt.legend()
    plt.grid(True)
    plt.axis('equal')
    plt.savefig("debug_intersection.png")

def angular_difference(angle1, angle2):
    """
    Calculates minimum angular difference between two angles (0-360°).
    
    Args:
        angle1, angle2 (float): Angles in degrees
        
    Returns:
        float: Minimum angular difference
    """
    diff = abs(angle1 - angle2)
    return min(diff, 360 - diff)

def plot_aircraft_tracks(hex_code, tracks, tracks_unwrapped_degrees, transitions, aircraft_data):
    """
    Generates a PNG plot for a given aircraft showing original tracks,
    unwrapped tracks and detected transition points.
    
    Args:
        hex_code (str): Aircraft hexadecimal code
        tracks (array): Original track values
        tracks_unwrapped_degrees (array): Unwrapped track values
        transitions (list): List of (i, j) transition tuples
        aircraft_data (DataFrame): Complete aircraft data
    """
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot 1: Original tracks
    ax1.plot(range(len(tracks)), tracks, 'b-o', markersize=4, linewidth=1, label='Original track')
    ax1.set_title(f'Aircraft {hex_code} - Original Track (0-360°)')
    ax1.set_xlabel('Point index')
    ax1.set_ylabel('Track (degrees)')
    ax1.set_ylim(0, 360)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Mark transitions on original plot
    for i, j in transitions:
        if i < len(tracks) and j < len(tracks):
            ax1.axvline(x=i, color='red', linestyle='--', alpha=0.7, label='Transition' if (i, j) == transitions[0] else "")
            ax1.axvline(x=j, color='red', linestyle='--', alpha=0.7)
    
    # Plot 2: Unwrapped tracks
    ax2.plot(range(len(tracks_unwrapped_degrees)), tracks_unwrapped_degrees, 'g-o', markersize=4, linewidth=1, label='Unwrapped track')
    ax2.set_title(f'Aircraft {hex_code} - Unwrapped Track')
    ax2.set_xlabel('Point index')
    ax2.set_ylabel('Unwrapped track (degrees)')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Mark transitions on unwrapped plot
    for i, j in transitions:
        if i < len(tracks_unwrapped_degrees) and j < len(tracks_unwrapped_degrees):
            ax2.axvline(x=i, color='red', linestyle='--', alpha=0.7, label='Transition' if (i, j) == transitions[0] else "")
            ax2.axvline(x=j, color='red', linestyle='--', alpha=0.7)
            
            # Add annotation for each transition
            angle_diff = abs(tracks_unwrapped_degrees[j] - tracks_unwrapped_degrees[i])
            mid_point = (i + j) / 2
            ax2.annotate(f'Δ={angle_diff:.1f}°', 
                        xy=(mid_point, tracks_unwrapped_degrees[int(mid_point)] if int(mid_point) < len(tracks_unwrapped_degrees) else tracks_unwrapped_degrees[-1]),
                        xytext=(10, 10), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    # Add general information
    callsign = aircraft_data['callsign'].iloc[0] if not aircraft_data['callsign'].isnull().all() else 'N/A'
    regis = aircraft_data['regis'].iloc[0] if not aircraft_data['regis'].isnull().all() else 'N/A'
    
    fig.suptitle(f'Aircraft Analysis - {hex_code}\nCallsign: {callsign} | Registration: {regis}\nTransitions detected: {len(transitions)}', 
                 fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    # Get timestamp of aircraft's first point
    first_timestamp = aircraft_data['timestamp'].iloc[0]
    # Format timestamp for filename (replace non-allowed characters)
    timestamp_str = first_timestamp.strftime('%Y%m%d_%H%M%S')
    
    # Create filename: timestamp-hex_code.png
    filename = os.path.join(PLOTS_DIR, f'{timestamp_str}-{hex_code}.png')
    
    # Save plot
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()  # Close figure to free memory
    
    print(f"📊 Plot saved: {filename}")

def setup_csv_files():
    records_header = [
        "timestamp",
        "callsign",
        "regis",
        "hex",
        "alt",
        "lat",
        "lon",
        "track",
    ]

    with open(RECORDS_FILE, "w", newline="") as f:
        # w mode will overwrite the RECORDS_FILE on purpose
        # This is to avoid discontinuities in tracking
        #   that would generate fake turns
        writer = csv.writer(f)
        writer.writerow(records_header)

    turns_header = [
        "timestamp",
        "callsign",
        "regis",
        "hex",
        "lat",
        "lon",
    ]

    if not os.path.exists(TURNS_FILE) or os.path.getsize(TURNS_FILE) == 0:
        # TURNS_FILE is kept to avoid losing data
        with open(TURNS_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(turns_header)

if __name__ == "__main__":

    setup_csv_files()

    print(
        f"📡 Monitoring airspace within {RADIUS} NM from https://www.openstreetmap.org/#map=9/{LAT}/{LON} between {MIN_ALT} and {MAX_ALT} ft"
    )
    print("Leave this code running at least one hour to detect turns.")

    while True:
        check_aircraft()
        process_aircraft_turns()
        time.sleep(DELAY)