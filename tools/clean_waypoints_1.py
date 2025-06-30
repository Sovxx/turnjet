import pandas as pd
import re

def clean_csv_coordinates(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remplacer les retours à la ligne entre les coordonnées par un espace
    # Pattern: trouve les coordonnées Nord suivies d'un retour à la ligne et des coordonnées Est/Ouest
    pattern = r'([0-9]+°[0-9]+\'[0-9]+\.[0-9]+""[NS])\s*\n\s*([0-9]+°[0-9]+\'[0-9]+\.[0-9]+""[EW])'
    cleaned_content = re.sub(pattern, r'\1 \2', content)
    
    return cleaned_content

# Nettoyer et lire le fichier
cleaned_csv = clean_csv_coordinates('waypoints.csv')

# Sauvegarder le fichier nettoyé
with open('fichier_nettoye.csv', 'w', encoding='utf-8') as f:
    f.write(cleaned_csv)

# Maintenant lire avec pandas
df = pd.read_csv('fichier_nettoye.csv', sep=';', header=None, names=['Code', 'Coordinates'])
