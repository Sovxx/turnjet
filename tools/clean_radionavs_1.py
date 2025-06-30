import pandas as pd
import re

def clean_csv_coordinates(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern pour capturer les entrées complètes sur plusieurs lignes
    # Format: CODE;"LAT\nLON\nINFO_OPTIONNELLE"
    pattern = r'([A-Z]+);"([0-9]+°[0-9]+\'[0-9]+\.[0-9]+""[NS])\s*\n([0-9]+°[0-9]+\'[0-9]+\.[0-9]+""[EW])\s*\n([^"]*)"'
    
    def replace_multiline(match):
        code = match.group(1)
        lat = match.group(2)
        lon = match.group(3)
        info = match.group(4).strip()
        
        # Reconstruire la ligne avec coordonnées sur une seule ligne
        # Format final: CODE;"LAT LON";INFO (si info existe)
        if info:
            return f'{code};"{lat} {lon}";"{info}"'
        else:
            return f'{code};"{lat} {lon}"'
    
    # Appliquer le remplacement
    cleaned_content = re.sub(pattern, replace_multiline, content, flags=re.MULTILINE)
    
    # Pattern de fallback pour les cas simples (2 lignes seulement)
    pattern_simple = r'([A-Z]+);"([0-9]+°[0-9]+\'[0-9]+\.[0-9]+""[NS])\s*\n([0-9]+°[0-9]+\'[0-9]+\.[0-9]+""[EW])"'
    
    def replace_simple(match):
        code = match.group(1)
        lat = match.group(2)
        lon = match.group(3)
        return f'{code};"{lat} {lon}"'
    
    # Appliquer le pattern simple pour les entrées sans info supplémentaire
    cleaned_content = re.sub(pattern_simple, replace_simple, cleaned_content, flags=re.MULTILINE)
    
    return cleaned_content

def process_waypoints_file(input_file, output_file='fichier_nettoye.csv'):
    """
    Traite le fichier de waypoints et le nettoie
    """
    print(f"Lecture du fichier: {input_file}")
    
    # Nettoyer le fichier
    cleaned_csv = clean_csv_coordinates(input_file)
    
    # Sauvegarder le fichier nettoyé
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_csv)
    
    print(f"Fichier nettoyé sauvegardé: {output_file}")
    
    # Lire avec pandas
    try:
        # Essayer avec 2 colonnes d'abord
        df = pd.read_csv(output_file, sep=';', header=None, names=['Code', 'Coordinates'])
        print(f"Fichier lu avec 2 colonnes: {len(df)} lignes")
    except:
        # Si ça échoue, essayer avec 3 colonnes (pour les infos supplémentaires)
        try:
            df = pd.read_csv(output_file, sep=';', header=None, names=['Code', 'Coordinates', 'Info'])
            print(f"Fichier lu avec 3 colonnes: {len(df)} lignes")
        except Exception as e:
            print(f"Erreur lors de la lecture: {e}")
            return None
    
    # Afficher un aperçu
    print("\nAperçu des données:")
    print(df.head())
    
    return df



# Tester la fonction
print("=== TEST AVEC VOS DONNÉES ===")
df_test = process_waypoints_file('radionavs.csv', 'radio_clean.csv')

if df_test is not None:
    print("\n=== RÉSULTAT FINAL ===")
    for idx, row in df_test.iterrows():
        if 'Info' in df_test.columns:
            print(f"{row['Code']}: {row['Coordinates']} | {row['Info']}")
        else:
            print(f"{row['Code']}: {row['Coordinates']}")

# Pour utiliser avec votre fichier réel:
print("\n" + "="*50)
print("Pour traiter votre fichier 'waypoints.csv':")
print("df = process_waypoints_file('waypoints.csv')")
