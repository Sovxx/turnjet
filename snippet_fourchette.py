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


def afficher_segments(segments):
    """Affiche les segments de manière lisible."""
    print(f"Nombre de segments trouvés: {len(segments)}")
    for i, seg in enumerate(segments):
        print(f"\nSegment {i+1}:")
        print(f"  Indices: {seg['debut']} à {seg['fin']}")
        print(f"  Valeurs: {seg['valeurs']}")
        print(f"  Min: {seg['min']:.2f}, Max: {seg['max']:.2f}")
        print(f"  Fourchette: {seg['fourchette']:.2f}")


# Exemples d'utilisation
if __name__ == "__main__":
    
    # =================================================================
    # EXEMPLE 1: Vos données d'origine
    # =================================================================
    print("EXEMPLE 1: Données d'origine")
    data1 = [205.08, 201.42, 201.26, 200.96, 200.72, 200.6, 200.6]
    print(f"Données: {data1}")
    
    segments = detect_segments_fourchette(data1, largeur_fourchette=2, min_size=2)
    afficher_segments(segments)
    
    # =================================================================
    # EXEMPLE 2: Signal avec plusieurs paliers distincts
    # =================================================================
    print("\n" + "="*70)
    print("EXEMPLE 2: Signal avec plusieurs paliers")
    data2 = [10.1, 10.3, 10.2, 10.4,   # Palier 1 (autour de 10.2)
             15.8, 15.9, 16.1, 15.7,   # Palier 2 (autour de 15.9)
             20.0, 20.2, 19.8, 20.1,   # Palier 3 (autour de 20.0)
             8.9, 9.1, 8.8]            # Palier 4 (autour de 9.0)
    print(f"Données: {data2}")
    
    segments = detect_segments_fourchette(data2, largeur_fourchette=0.6, min_size=3)
    afficher_segments(segments)
    
    # =================================================================
    # EXEMPLE 3: Signal avec transition graduelle
    # =================================================================
    print("\n" + "="*70)
    print("EXEMPLE 3: Transition graduelle")
    data3 = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 85]
    print(f"Données: {data3}")
    
    # Avec fourchette large
    print("\nAvec fourchette large (largeur=5):")
    segments = detect_segments_fourchette(data3, largeur_fourchette=5, min_size=4)
    afficher_segments(segments)
    
    # Avec fourchette stricte
    print("\nAvec fourchette stricte (largeur=2):")
    segments = detect_segments_fourchette(data3, largeur_fourchette=2, min_size=3)
    afficher_segments(segments)
    
    # =================================================================
    # EXEMPLE 4: Signal bruité avec paliers
    # =================================================================
    print("\n" + "="*70)
    print("EXEMPLE 4: Signal bruité")
    data4 = [50.1, 50.3, 49.8, 50.2, 50.4, 49.9,  # Palier 1 (bruit autour de 50)
             45.1, 44.8, 45.3, 44.9, 45.0,         # Palier 2 (bruit autour de 45)
             60.2, 59.8, 60.1, 59.9, 60.3, 60.0]   # Palier 3 (bruit autour de 60)
    print(f"Données: {data4}")
    
    segments = detect_segments_fourchette(data4, largeur_fourchette=0.8, min_size=4)
    afficher_segments(segments)
    
    # =================================================================
    # EXEMPLE 5: Températures avec différents paramètres
    # =================================================================
    print("\n" + "="*70)
    print("EXEMPLE 5: Données de température")
    temp_data = [22.1, 22.3, 22.0, 22.2,          # Stable autour de 22°C
                 25.8, 26.1, 25.9, 26.0, 25.7,    # Montée vers 26°C
                 18.2, 18.4, 18.1, 18.3, 18.0,    # Chute vers 18°C
                 30.1, 30.5, 30.3, 30.2, 30.4]    # Pic vers 30°C
    print(f"Températures: {temp_data}")
    
    print("\nDétection avec fourchette 0.5°C:")
    segments = detect_segments_fourchette(temp_data, largeur_fourchette=0.5, min_size=3)
    afficher_segments(segments)
    
    print("\nDétection avec fourchette 1.0°C:")
    segments = detect_segments_fourchette(temp_data, largeur_fourchette=1.0, min_size=3)
    afficher_segments(segments)
    
    # =================================================================
    # EXEMPLE 6: Cas particuliers
    # =================================================================
    print("\n" + "="*70)
    print("EXEMPLE 6: Cas particuliers")
    
    # Signal constant
    print("\nSignal parfaitement constant:")
    data_constant = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
    segments = detect_segments_fourchette(data_constant, largeur_fourchette=0.1, min_size=2)
    afficher_segments(segments)
    
    # Signal très variable
    print("\nSignal très variable (pas de segments):")
    data_variable = [1, 10, 2, 15, 3, 20, 4, 25]
    segments = detect_segments_fourchette(data_variable, largeur_fourchette=2, min_size=2)
    afficher_segments(segments)
    
    # Signal court
    print("\nSignal trop court:")
    data_court = [1.0, 1.1]
    segments = detect_segments_fourchette(data_court, largeur_fourchette=1, min_size=3)
    afficher_segments(segments)