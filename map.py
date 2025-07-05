import json
import csv
import folium
from folium import plugins
from pathlib import Path

def load_csv_data(file_path):
    """Charge les données depuis un fichier CSV"""
    try:
        turns = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
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
        print(f"Erreur : Le fichier {file_path} n'a pas été trouvé.")
        return []
    except (ValueError, IndexError):
        print(f"Erreur : Format de données invalide dans {file_path}.")
        return []

def load_json_data(file_path):
    """Charge les données depuis un fichier JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Erreur : Le fichier {file_path} n'a pas été trouvé.")
        return []
    except json.JSONDecodeError:
        print(f"Erreur : Le fichier {file_path} n'est pas un JSON valide.")
        return []

def create_map_with_points():
    """Crée une carte Leaflet avec des points rouges et bleus"""
    
    # Charger les données
    radionavs = load_json_data('ressources/radionavs.json')
    waypoints = load_json_data('ressources/waypoints.json')
    turns = load_csv_data('turns.csv')
    
    if not radionavs and not waypoints:
        print("Aucune donnée à afficher sur la carte.")
        return
    
    # Calculer le centre de la carte basé sur tous les points
    all_points = radionavs + waypoints + turns
    if all_points:
        center_lat = sum(point['latitude'] for point in all_points) / len(all_points)
        center_lon = sum(point['longitude'] for point in all_points) / len(all_points)
    else:
        center_lat, center_lon = 46.2276, 2.2137  # Centre de la France par défaut
    
    # Créer la carte
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles='OpenStreetMap'
    )

    # Ajouter une échelle
    plugins.MeasureControl().add_to(m)
    
    # Ajouter les points bleus pour les radionavs
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
    
    # Ajouter les points verts pour les waypoints
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
    
    # Ajouter les points jaunes pour les avions (turns)
    for turn in turns:
        folium.CircleMarker(
            location=[turn['latitude'], turn['longitude']],
            radius=6,
            popup=f"Avion: {turn['callsign']}<br>Immat: <a href=\"https://www.flightradar24.com/data/aircraft/{turn['registration']}\" target=\"_blank\" >{turn['registration']}</a><br>Heure: {turn['timestamp']}",
            tooltip=f"Avion: {turn['callsign']}",
            color='red',
        ).add_to(m)

    # Ajouter une légende
    legend_html = '''
    <div style="position: fixed; 
                bottom: 30px; left: 30px; width: 130px; height: 110px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><span style="color:red;">●</span> Virages</p>
    <p><span style="color:blue;">●</span> Radionavs</p>
    <p><span style="color:green;">●</span> Waypoints</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Sauvegarder la carte
    output_file = 'carte_navigation.html'
    m.save(output_file)
    
    print(f"Carte générée avec succès !")
    print(f"- {len(radionavs)} radionavs ajoutés (points bleus)")
    print(f"- {len(waypoints)} waypoints ajoutés (points verts)")
    print(f"- {len(turns)} avions ajoutés (points rouges)")
    print(f"- Fichier sauvegardé : {output_file}")
    
    return m

def main():
    """Fonction principale"""
    print("Génération de la carte de navigation...")
    
    # Vérifier que les dossiers existent
    ressources_dir = Path('ressources')
    if not ressources_dir.exists():
        print("Erreur : Le dossier 'ressources' n'existe pas.")
        print("Veuillez créer le dossier et y placer les fichiers radionavs.json et waypoints.json")
        return
    
    # Créer la carte
    carte = create_map_with_points()
    
    if carte:
        print("\nPour visualiser la carte, ouvrez le fichier 'carte_navigation.html' dans votre navigateur.")

if __name__ == "__main__":
    main()