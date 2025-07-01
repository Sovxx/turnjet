#https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_12_JUN_2025/FRANCE/AIRAC-2025-06-12/html/index-fr-FR.html

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
    raise ValueError("Longitude must be between 0 and 250 NM")

MIN_ALT = int(config["altitude"]["min_alt"])
MAX_ALT = int(config["altitude"]["max_alt"])

CSV_FILE = "records.csv"
PLOTS_DIR = "aircraft_plots"

# Créer le dossier pour les graphiques s'il n'existe pas
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
                None if (ac.get("track") is None) else ac.get("track")
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

            #print("🛬 Aircraft detected :", row)

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
        with open(turns_file, 'a', newline='') as f:
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
    
    #print(f"Nombre de lignes supprimées: {len(df) - len(df_cleaned)}")
    #print(f"Nombre de lignes restantes: {len(df_cleaned)}")




def detect_turns(aircraft_data):
    """
    Détecte les changements de direction pour un avion donné en utilisant detect_paliers_avec_tuples.
    
    Args:
        aircraft_data (DataFrame): Données d'un avion spécifique triées par timestamp
        
    Returns:
        list: Liste des virages détectés
    """
    turns = []
    
    # Vérifier qu'on a assez de données
    if len(aircraft_data) < 6:
        return turns
    
    # Filtrer les données avec des valeurs de track valides
    valid_track_data = aircraft_data.dropna(subset=['track']).reset_index(drop=True)
    
    if len(valid_track_data) < 6:
        return turns
    
    # Extraire les valeurs de track
    tracks = valid_track_data['track'].values
    
    # Gérer la discontinuité des angles (0°/360°)
    # Unwrapper les angles pour éviter les sauts de 360° à 0°
    tracks_unwrapped = np.unwrap(np.radians(tracks))
    tracks_unwrapped_degrees = np.degrees(tracks_unwrapped)
    
    # Détecter les paliers avec ruptures
    try:
        # Utiliser detect_paliers_avec_tuples sur les données de track unwrappées
        # Réduire la pénalité pour être plus sensible aux changements
        # Réduire la taille minimale des segments

        print("#####################################")

        print(f"{tracks=}")
        print(f"{tracks_unwrapped_degrees=}")

        segments = detect_segments_fourchette(
            tracks_unwrapped_degrees.tolist(),
            largeur_fourchette=2.0,
            min_size=2
        )

        print_segments_simple(segments)
        

        transitions = extract_transitions(segments)

        print(f"{transitions=}")

        # Générer le graphique pour cet avion
        hex_code = valid_track_data['hex'].iloc[0]
        plot_aircraft_tracks(hex_code, tracks, tracks_unwrapped_degrees, transitions, valid_track_data)
        
        
        # Traiter les transitions 
        for i, j in transitions:
            
            # Estimer le point de virage (interpolation entre i et j)
            turn_point = estimate_turn_point_from_indices(valid_track_data, i, j)
            
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
    
    except Exception as e:
        print(f"Erreur lors de la détection des paliers: {e}")
    
    return turns


def detect_segments_fourchette(table, largeur_fourchette=2, min_size=2):
    """
    Détecte les segments composés d'au moins min_size valeurs qui tiennent 
    dans une fourchette de largeur donnée.
    
    Args:
        table (list of float): Les données à analyser.
        largeur_fourchette (float): Largeur maximale de la fourchette (max - min).
        min_size (int): Taille minimale d'un segment.
    
    Returns:
        list of dict: Chaque dictionnaire contient:
                     - 'debut': index de début du segment
                     - 'fin': index de fin du segment (inclus)
                     - 'valeurs': liste des valeurs du segment
                     - 'min': valeur minimale du segment
                     - 'max': valeur maximale du segment
                     - 'fourchette': largeur de la fourchette (max - min)
    """
    if len(table) < min_size:
        return []
    
    segments = []
    i = 0
    
    while i < len(table):
        # Commencer un nouveau segment potentiel
        segment_debut = i
        segment_fin = i
        
        # Étendre le segment tant que la fourchette reste acceptable
        while segment_fin < len(table):
            # Calculer la fourchette du segment actuel
            segment_values = table[segment_debut:segment_fin + 1]
            min_val = min(segment_values)
            max_val = max(segment_values)
            fourchette_actuelle = max_val - min_val
            
            # Si la fourchette dépasse la limite, arrêter l'extension
            if fourchette_actuelle > largeur_fourchette:
                segment_fin -= 1  # Revenir au dernier point valide
                break
            
            segment_fin += 1
        
        # Ajuster segment_fin si on a atteint la fin du tableau
        if segment_fin >= len(table):
            segment_fin = len(table) - 1
        
        # Vérifier si le segment a la taille minimale requise
        taille_segment = segment_fin - segment_debut + 1
        if taille_segment >= min_size:
            segment_values = table[segment_debut:segment_fin + 1]
            min_val = min(segment_values)
            max_val = max(segment_values)
            
            segments.append({
                'debut': segment_debut,
                'fin': segment_fin,
                'valeurs': segment_values,
                'min': min_val,
                'max': max_val,
                'fourchette': max_val - min_val
            })
        
        # Passer au point suivant
        i = segment_fin + 1
    
    return segments


def print_segments_simple(segments):
    """
    Affiche les segments de manière concise avec leurs indices.
    
    Args:
        segments (list): Liste des segments retournée par detect_segments_fourchette
    """
    if not segments:
        print("Aucun segment trouvé")
        return
    
    print(f"{len(segments)} segment(s) trouvé(s):")
    for i, seg in enumerate(segments):
        print(f"  Segment {i+1}: indices {seg['debut']}-{seg['fin']}")


def extract_transitions(segments):
    """
    Extrait les transitions entre segments consécutifs.
    
    Args:
        segments (list): Liste des segments retournée par detect_segments_fourchette
    
    Returns:
        list of tuples: Chaque tuple (i, j) représente une transition où:
                       i = index de fin du segment précédent
                       j = index de début du segment suivant
    """
    if len(segments) < 2:
        return []
    
    transitions = []
    
    for i in range(len(segments) - 1):
        segment_actuel = segments[i]
        segment_suivant = segments[i + 1]
        
        fin_actuel = segment_actuel['fin']
        debut_suivant = segment_suivant['debut']
        
        transitions.append((fin_actuel, debut_suivant))
    
    return transitions


def estimate_turn_point_from_indices(aircraft_data, i, j):
    """
    Estime le point de virage comme le point d'intersection entre :
    - La demi-droite issue du point i dans la direction du track au point i
    - La demi-droite issue du point j dans la direction opposée du track au point j
    
    Approximation plane (2D), avec Shapely.
    """
    point_i = aircraft_data.iloc[i]
    point_j = aircraft_data.iloc[j]

    lat1, lon1, track1 = point_i['lat'], point_i['lon'], point_i['track']
    lat2, lon2, track2 = point_j['lat'], point_j['lon'], (point_j['track'] + 180) % 360

    # Longueur arbitraire pour prolonger les demi-droites (en km)
    extension_km = 100

    def extend(lat, lon, track_deg, extension_km):
        """
        Prolonge un point (lat, lon) dans la direction `track_deg` sur `extension_km` kilomètres.
        Corrige la latitude pour le facteur de conversion en longitude.
        """
        angle_rad = math.radians(track_deg)

        # Conversion : 1° lat ≈ 111 km ; 1° lon ≈ 111 * cos(lat)
        delta_lat = (extension_km / 111.0) * math.cos(angle_rad)
        delta_lon = (extension_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(angle_rad)

        new_lat = lat + delta_lat
        new_lon = lon + delta_lon
        return (new_lon, new_lat)

    # Construire deux segments (demi-droites)
    p1 = (lon1, lat1)
    p2 = extend(lat1, lon1, track1, extension_km)

    q1 = (lon2, lat2)
    q2 = extend(lat2, lon2, track2, extension_km)

    line1 = LineString([p1, p2])
    line2 = LineString([q1, q2])

    intersection = line1.intersection(line2)

    if intersection.is_empty or not isinstance(intersection, Point):
        # Fallback : milieu simple
        print(f"[Fallback] i={i}, j={j}")
        print(f"  Point i: lat={lat1}, lon={lon1}, track={track1}")
        print(f"  Point j: lat={lat2}, lon={lon2}, track(opposite)={track2}")
        print(f"  Line1: {p1} -> {p2}")
        print(f"  Line2: {q1} -> {q2}")
        plot_debug(p1, p2, q1, q2)

        lat_mid = (lat1 + lat2) / 2
        lon_mid = (lon1 + lon2) / 2
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
    Affiche les deux lignes avec matplotlib, pour diagnostiquer visuellement une absence d'intersection.
    """
    plt.figure(figsize=(8, 8))
    plt.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', label='Ligne i (track)')
    plt.plot([q1[0], q2[0]], [q1[1], q2[1]], 'b-', label='Ligne j (track opposé)')

    if intersection and not intersection.is_empty:
        plt.plot(intersection.x, intersection.y, 'go', label='Intersection')

    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Visualisation des lignes de croisement")
    plt.legend()
    plt.grid(True)
    plt.axis('equal')
    plt.savefig("debug_intersection.png")




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


def plot_aircraft_tracks(hex_code, tracks, tracks_unwrapped_degrees, transitions, aircraft_data):
    """
    Génère un graphique PNG pour un avion donné montrant les tracks originaux,
    les tracks unwrappés et les points de transition détectés.
    
    Args:
        hex_code (str): Code hexadécimal de l'avion
        tracks (array): Valeurs de track originales
        tracks_unwrapped_degrees (array): Valeurs de track unwrappées
        transitions (list): Liste des tuples (i, j) de transitions
        aircraft_data (DataFrame): Données complètes de l'avion
    """
    # Créer une figure avec 2 sous-graphiques
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Graphique 1: Tracks originaux
    ax1.plot(range(len(tracks)), tracks, 'b-o', markersize=4, linewidth=1, label='Track original')
    ax1.set_title(f'Aircraft {hex_code} - Track Original (0-360°)')
    ax1.set_xlabel('Point index')
    ax1.set_ylabel('Track (degrees)')
    ax1.set_ylim(0, 360)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Marquer les transitions sur le graphique original
    for i, j in transitions:
        if i < len(tracks) and j < len(tracks):
            ax1.axvline(x=i, color='red', linestyle='--', alpha=0.7, label='Transition' if (i, j) == transitions[0] else "")
            ax1.axvline(x=j, color='red', linestyle='--', alpha=0.7)
    
    # Graphique 2: Tracks unwrappés
    ax2.plot(range(len(tracks_unwrapped_degrees)), tracks_unwrapped_degrees, 'g-o', markersize=4, linewidth=1, label='Track unwrapped')
    ax2.set_title(f'Aircraft {hex_code} - Track Unwrapped')
    ax2.set_xlabel('Point index')
    ax2.set_ylabel('Track unwrapped (degrees)')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Marquer les transitions sur le graphique unwrappé
    for i, j in transitions:
        if i < len(tracks_unwrapped_degrees) and j < len(tracks_unwrapped_degrees):
            ax2.axvline(x=i, color='red', linestyle='--', alpha=0.7, label='Transition' if (i, j) == transitions[0] else "")
            ax2.axvline(x=j, color='red', linestyle='--', alpha=0.7)
            
            # Ajouter une annotation pour chaque transition
            angle_diff = abs(tracks_unwrapped_degrees[j] - tracks_unwrapped_degrees[i])
            mid_point = (i + j) / 2
            ax2.annotate(f'Δ={angle_diff:.1f}°', 
                        xy=(mid_point, tracks_unwrapped_degrees[int(mid_point)] if int(mid_point) < len(tracks_unwrapped_degrees) else tracks_unwrapped_degrees[-1]),
                        xytext=(10, 10), textcoords='offset points',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                        arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    # Ajouter des informations générales
    callsign = aircraft_data['callsign'].iloc[0] if not aircraft_data['callsign'].isnull().all() else 'N/A'
    regis = aircraft_data['regis'].iloc[0] if not aircraft_data['regis'].isnull().all() else 'N/A'
    
    fig.suptitle(f'Aircraft Analysis - {hex_code}\nCallsign: {callsign} | Registration: {regis}\nTransitions detected: {len(transitions)}', 
                 fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    # Obtenir le timestamp du premier point de l'avion
    first_timestamp = aircraft_data['timestamp'].iloc[0]
    # Formater le timestamp pour le nom de fichier (remplacer les caractères non autorisés)
    timestamp_str = first_timestamp.strftime('%Y%m%d_%H%M%S')
    
    # Créer le nom de fichier: timestamp-hex_code.png
    filename = os.path.join(PLOTS_DIR, f'{timestamp_str}-{hex_code}.png')
    
    # Sauvegarder le graphique
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()  # Fermer la figure pour libérer la mémoire
    
    print(f"📊 Graphique sauvegardé: {filename}")

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
    print(f"📊 Graphiques sauvegardés dans le dossier: {PLOTS_DIR}")

    while True:
        check_aircraft()
        process_aircraft_turns()
        delay = 60
        time.sleep(delay)