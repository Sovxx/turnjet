import pandas as pd
import re
import json

def dms_to_decimal(dms_string):
    """
    Convertit des coordonnées DMS (Degrés Minutes Secondes) en décimal
    Exemple: "45°39'21.0\"\"N" -> 45.6558333
    """
    # Pattern pour extraire degrés, minutes, secondes et direction
    pattern = r"(\d+)°(\d+)'([\d.]+)\"\"([NSEW])"
    match = re.match(pattern, dms_string.strip())
    
    if not match:
        return None
    
    degrees = float(match.group(1))
    minutes = float(match.group(2))
    seconds = float(match.group(3))
    direction = match.group(4)
    
    # Conversion en décimal
    decimal = degrees + minutes/60 + seconds/3600
    
    # Appliquer le signe négatif pour Sud et Ouest
    if direction in ['S', 'W']:
        decimal = -decimal
    
    return decimal

def parse_coordinates_csv(file_path):
    """
    Parse le fichier CSV et convertit les coordonnées
    """
    data = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            print(line)
            if line and ';' in line:
                # Séparer le code et les coordonnées
                parts = line.split(';')
                code = parts[0]
                coord_string = parts[1].strip('"')
                
                # Séparer latitude et longitude
                coords = coord_string.split(' ')
                if len(coords) == 2:
                    lat_dms = coords[0]
                    lon_dms = coords[1]
                    print(lat_dms, lon_dms)
                    
                    # Convertir en décimal
                    lat_decimal = dms_to_decimal(lat_dms)
                    lon_decimal = dms_to_decimal(lon_dms)
                    print(lat_decimal, lon_decimal)
                    
                    if lat_decimal is not None and lon_decimal is not None:
                        data.append({
                            'code': code,
                            'latitude': round(lat_decimal, 6),
                            'longitude': round(lon_decimal, 6),
                        })
    
    return data

def convert_coordinates_file(input_file, output_json=None, output_csv=None):
    """
    Fonction principale pour convertir le fichier
    """
    # Parser les données
    data = parse_coordinates_csv(input_file)
    
    print(f"Traité {len(data)} coordonnées")
    
    # Sauvegarder en JSON si demandé
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nJSON sauvegardé: {output_json}")
    
    # Sauvegarder en CSV si demandé
    if output_csv:
        df = pd.DataFrame(data)
        df.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"CSV sauvegardé: {output_csv}")
    
    return data

# Exemple d'utilisation
if __name__ == "__main__":
    # Remplacez 'votre_fichier.csv' par le chemin de votre fichier
    input_file = 'fichier_nettoye.csv'
    
    # Convertir et sauvegarder
    data = convert_coordinates_file(
        input_file, 
        output_json='coordinates_decimal.json',
        output_csv='coordinates_decimal.csv'
    )
    
    # Créer aussi un DataFrame pandas pour manipulation
    df = pd.DataFrame(data)
    print(f"\nDataFrame créé avec {len(df)} lignes")
    print(df.head())
