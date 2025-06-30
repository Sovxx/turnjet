#https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_12_JUN_2025/FRANCE/AIRAC-2025-06-12/html/index-fr-FR.html

import configparser
import requests
import csv
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import logging

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
    raise ValueError("Longitude must be between 0 and 250 NM")

MIN_ALT = int(config["altitude"]["min_alt"])
MAX_ALT = int(config["altitude"]["max_alt"])

CSV_FILE = "records.csv"

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

def save_csv(row):
    with open(CSV_FILE, "a", newline="") as f:
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
            track = (
                None if (ac.get("track") is None) else int(round(ac.get("track")))
            )  # aircraft own track in degrees
            
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
            save_csv(row)

            print("🛬 Aircraft detected :", row)

    except Exception as e:
        logging.error("API error: %s", e)
        return False



def process_aircraft_turns(records_file='records.csv', turns_file='turns.csv'):
    """
    Analyse les données de tracking d'avions pour détecter les changements de direction
    et nettoyer les données anciennes.
    
    Args:
        records_file (str): Chemin vers le fichier records.csv
        turns_file (str): Chemin vers le fichier turns.csv de sortie
    """
    
    # Headers des fichiers
    records_header = ["timestamp", "callsign", "regis", "hex", "alt", "lat", "lon", "track"]
    turns_header = ["timestamp", "callsign", "regis", "hex", "lat", "lon"]
    
    # Lire le fichier records.csv
    try:
        df = pd.read_csv(records_file, names=records_header)
    except FileNotFoundError:
        print(f"Erreur: Le fichier {records_file} n'existe pas.")
        return
    
    # Convertir les timestamps en datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')

    # Calculer la limite de temps (il y a 1 heure)
    current_time = datetime.now()
    one_hour_ago = current_time - timedelta(hours=1)
    
    # Identifier les avions détectés il y a plus d'une heure
    old_aircraft_mask = df['timestamp'] < one_hour_ago
    old_aircraft_hex = df[old_aircraft_mask]['hex'].unique()
    
    print(f"Nombre d'avions détectés il y a plus d'une heure: {len(old_aircraft_hex)}")
    
    # Liste pour stocker les virages détectés
    turns_data = []
    
    # Analyser chaque avion ancien
    for hex_code in old_aircraft_hex:
        aircraft_data = df[df['hex'] == hex_code].sort_values('timestamp').reset_index(drop=True)
        
        if len(aircraft_data) < 6:  # Besoin d'au moins 6 points pour détecter un virage
            continue
            
        turns = detect_turns(aircraft_data)
        turns_data.extend(turns)
    
    # Écrire les virages dans turns.csv
    if turns_data:
        with open(turns_file, 'w', newline='') as f:
            writer = csv.writer(f)
            for turn in turns_data:
                writer.writerow(turn)
        print(f"Nombre de virages détectés: {len(turns_data)}")
    else:
        print("Aucun virage détecté.")
    
    # Supprimer les lignes des avions anciens du DataFrame
    df_cleaned = df[~df['hex'].isin(old_aircraft_hex)]
    
    # Réécrire le fichier records.csv sans les avions anciens
    df_cleaned.to_csv(records_file, header=False, index=False)
    
    print(f"Nombre de lignes supprimées: {len(df) - len(df_cleaned)}")
    print(f"Nombre de lignes restantes: {len(df_cleaned)}")

def detect_turns(aircraft_data):
    """
    Détecte les changements de direction pour un avion donné.
    
    Args:
        aircraft_data (DataFrame): Données d'un avion spécifique triées par timestamp
        
    Returns:
        list: Liste des virages détectés
    """
    turns = []
    
    # Parcourir les données pour détecter les virages
    for i in range(len(aircraft_data) - 5):  # -5 car on a besoin de 6 points consécutifs
        
        # Prendre 6 points consécutifs
        segment = aircraft_data.iloc[i:i+6]
        
        # Diviser en deux groupes de 3
        group1 = segment.iloc[0:3]
        group2 = segment.iloc[3:6]
        
        # Vérifier la cohérence du track dans chaque groupe (écart max 3°)
        if is_track_consistent(group1['track'].values, 3) and is_track_consistent(group2['track'].values, 3):
            
            # Calculer les moyennes des tracks
            avg_track1 = np.mean(group1['track'].values)
            avg_track2 = np.mean(group2['track'].values)
            
            # Calculer l'écart angulaire (en tenant compte de la nature circulaire des angles)
            angle_diff = angular_difference(avg_track1, avg_track2)
            
            # Si l'écart est supérieur à 6°, c'est un virage
            if angle_diff > 6:
                
                # Estimer le point de virage (point entre les deux segments)
                turn_point = estimate_turn_point(group1, group2)
                
                # Créer l'entrée pour le fichier turns.csv
                turn_entry = [
                    turn_point['timestamp'].strftime('%Y-%m-%dT%H:%M:%S'),
                    turn_point['callsign'],
                    turn_point['regis'],
                    turn_point['hex'],
                    turn_point['lat'],
                    turn_point['lon']
                ]
                
                turns.append(turn_entry)
    
    return turns

def is_track_consistent(tracks, max_deviation):
    """
    Vérifie si les tracks dans un groupe sont cohérents (écart max spécifié).
    
    Args:
        tracks (array): Tableau des valeurs de track
        max_deviation (float): Écart maximum autorisé en degrés
        
    Returns:
        bool: True si cohérent, False sinon
    """
    if len(tracks) < 2:
        return True
    
    # Calculer tous les écarts angulaires par rapport à la moyenne
    mean_track = np.mean(tracks)
    deviations = [angular_difference(track, mean_track) for track in tracks]
    
    return all(dev <= max_deviation for dev in deviations)

def angular_difference(angle1, angle2):
    """
    Calcule la différence angulaire minimale entre deux angles (0-360°).
    
    Args:
        angle1, angle2 (float): Angles en degrés
        
    Returns:
        float: Différence angulaire minimale
    """
    diff = abs(angle1 - angle2)
    return min(diff, 360 - diff)

def estimate_turn_point(group1, group2):
    """
    Estime le point de virage entre deux segments.
    
    Args:
        group1, group2 (DataFrame): Les deux groupes de 3 points
        
    Returns:
        dict: Point estimé du virage
    """
    # Prendre le dernier point du premier groupe et le premier du second
    last_point_g1 = group1.iloc[-1]
    first_point_g2 = group2.iloc[0]
    
    # Interpoler entre ces deux points
    turn_point = {
        'timestamp': last_point_g1['timestamp'] + (first_point_g2['timestamp'] - last_point_g1['timestamp']) / 2,
        'callsign': last_point_g1['callsign'],
        'regis': last_point_g1['regis'],
        'hex': last_point_g1['hex'],
        'lat': (last_point_g1['lat'] + first_point_g2['lat']) / 2,
        'lon': (last_point_g1['lon'] + first_point_g2['lon']) / 2
    }
    
    return turn_point


if __name__ == "__main__":

    header = [
        "timestamp",
        "callsign",
        "regis",
        "hex",
        "alt",
        "lat",
        "lon",
        "track",
    ]

    # Create csv header line if csv file does not exist
    try:
        with open(CSV_FILE, "x", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
    except FileExistsError:
        pass

    print(
        f"📡 Monitoring airspace within {RADIUS} NM from https://www.openstreetmap.org/#map=9/{LAT}/{LON} between {MIN_ALT} and {MAX_ALT} ft"
    )
    print(f"Format: {header}")

    while True:
        check_aircraft()
        process_aircraft_turns()
        delay = 60
        time.sleep(delay)


