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
    Parse le fichier CSV à 3 colonnes et convertit les coordonnées
    """
    data = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            print(f"Ligne lue: {line}")
            
            if line and ';' in line:
                # Séparer les trois parties: code, coordonnées, info
                parts = line.split(';')
                
                if len(parts) >= 3:
                    code = parts[0].strip()
                    coord_string = parts[1].strip('"')
                    info = parts[2].strip('"')
                    
                    print(f"Code: {code}")
                    print(f"Coordonnées: {coord_string}")
                    print(f"Info: {info}")
                    
                    # Séparer latitude et longitude
                    coords = coord_string.split(' ')
                    if len(coords) == 2:
                        lat_dms = coords[0]
                        lon_dms = coords[1]
                        print(f"Latitude DMS: {lat_dms}")
                        print(f"Longitude DMS: {lon_dms}")
                        
                        # Convertir en décimal
                        lat_decimal = dms_to_decimal(lat_dms)
                        lon_decimal = dms_to_decimal(lon_dms)
                        print(f"Latitude décimal: {lat_decimal}")
                        print(f"Longitude décimal: {lon_decimal}")
                        
                        if lat_decimal is not None and lon_decimal is not None:
                            data.append({
                                'code': code,
                                'latitude': round(lat_decimal, 6),
                                'longitude': round(lon_decimal, 6),
                            })
                            print(f"✓ Ajouté: {code}")
                        else:
                            print(f"✗ Erreur conversion: {code}")
                    else:
                        print(f"✗ Format coordonnées invalide: {coord_string}")
                elif len(parts) == 2:
                    # Cas où il n'y a que 2 colonnes (code et coordonnées)
                    code = parts[0].strip()
                    coord_string = parts[1].strip('"')
                    
                    coords = coord_string.split(' ')
                    if len(coords) == 2:
                        lat_dms = coords[0]
                        lon_dms = coords[1]
                        
                        lat_decimal = dms_to_decimal(lat_dms)
                        lon_decimal = dms_to_decimal(lon_dms)
                        
                        if lat_decimal is not None and lon_decimal is not None:
                            data.append({
                                'code': code,
                                'latitude': round(lat_decimal, 6),
                                'longitude': round(lon_decimal, 6),
                                'info': ''
                            })
                else:
                    print(f"✗ Format ligne invalide: {line}")
            print("-" * 50)
    
    return data

def convert_coordinates_file(input_file, output_json=None, output_csv=None):
    """
    Fonction principale pour convertir le fichier
    """
    print(f"Traitement du fichier: {input_file}")
    print("=" * 60)
    
    # Parser les données
    data = parse_coordinates_csv(input_file)
    
    print("=" * 60)
    print(f"Traité {len(data)} coordonnées")
    
    # Afficher un résumé
    if data:
        print("\nRésumé des conversions:")
        for item in data:
            print(f"{item['code']}: {item['latitude']}, {item['longitude']}")
    
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

# Test avec vos données d'exemple
test_data = '''ABB;"50°08'06.5""N 001°51'16.9""E";"60NM FL500"
AGN;"43°53'16.9""N 000°52'22.3""E";"120NM(315°..75°) 100NM FL500"
AJO;"41°46'13.9""N 008°46'28.8""E";"200NM(90°..270°) 100NM FL500"
AMB;"47°25'44.1""N 001°03'52.0""E";"80NM FL500"
ANG;"47°32'12.7""N 000°51'06.6""W";"150NM FL500"
CM;"43°54'29.8""N 004°54'19.4""E";"20NM"
AVN;"43°59'43.3""N 004°44'47.0""E";"60NM FL500"
AVD;"47°07'14.4""N 002°47'58.6""E";"50NM FL500"'''

# Créer un fichier de test
with open('test_3cols.csv', 'w', encoding='utf-8') as f:
    f.write(test_data)

# Tester la fonction
print("=== TEST AVEC VOS DONNÉES 3 COLONNES ===")
test_result = convert_coordinates_file(
    'test_3cols.csv',
    output_json='test_output.json',
    output_csv='test_output.csv'
)

# Exemple d'utilisation avec votre fichier
if __name__ == "__main__":
    print("\n" + "="*60)
    print("TRAITEMENT DE VOTRE FICHIER:")
    print("="*60)
    
    # Remplacez 'fichier_nettoye.csv' par le chemin de votre fichier
    input_file = 'radio_clean.csv'
    
    # Convertir et sauvegarder
    data = convert_coordinates_file(
        input_file, 
        output_json='coordinates_decimal.json',
        output_csv='coordinates_decimal.csv'
    )
    
    # Créer aussi un DataFrame pandas pour manipulation
    if data:
        df = pd.DataFrame(data)
        print(f"\nDataFrame créé avec {len(df)} lignes")
        print(df.head())
        
        # Afficher les statistiques
        print(f"\nStatistiques:")
        print(f"- Codes uniques: {df['code'].nunique()}")
        print(f"- Latitude min/max: {df['latitude'].min():.6f} / {df['latitude'].max():.6f}")
        print(f"- Longitude min/max: {df['longitude'].min():.6f} / {df['longitude'].max():.6f}")
