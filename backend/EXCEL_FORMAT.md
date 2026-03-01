# Format Excel pour l'Import d'Emploi du Temps

## Structure du fichier

Le fichier Excel doit avoir la structure suivante :

### Colonnes
- **Heure** : Format "HH:MM-HH:MM" (ex: "08:00-10:00")
- **Lundi** : Contenu du cours
- **Mardi** : Contenu du cours
- **Mercredi** : Contenu du cours
- **Jeudi** : Contenu du cours
- **Vendredi** : Contenu du cours
- **Samedi** : Contenu du cours (optionnel)

### Format du contenu de chaque cellule

Chaque cellule de cours doit contenir les informations suivantes, séparées par des retours à la ligne :

```
MATIERE
Professeur
Salle
Groupe (optionnel)
```

## Exemple

| Heure | Lundi | Mardi | Mercredi | Jeudi | Vendredi |
|-------|-------|-------|----------|-------|----------|
| 08:00-10:00 | TRAIT IMAGES<br>Mr BEN SLIMA<br>C14 | ALGO AVANCEE<br>Mme JEMAL I.<br>LAB 11<br>P1 | | BASES DE DONNEES<br>Mr AHMED<br>C12 | |
| 10:00-12:00 | | RESEAUX<br>Mme KARIM<br>LAB 5<br>P2 | PROGRAMMATION<br>Mr HASSAN<br>C14 | | PROJET<br>Mr BEN SLIMA<br>LAB 11 |

## Notes importantes

1. **Format des heures** : Toujours au format 24h avec deux chiffres (08:00, 14:30, etc.)
2. **Noms des professeurs** : Inclure le titre (Mr, Mme, Dr, Prof)
3. **Salles** : Utiliser les codes officiels (C14, LAB 11, etc.)
4. **Groupes** : Optionnel, utiliser P1, P2, etc. pour les travaux pratiques
5. **Cellules vides** : Laisser vide s'il n'y a pas de cours

## Création du fichier

1. Ouvrir Excel
2. Créer les colonnes comme indiqué ci-dessus
3. Remplir les données
4. Sauvegarder au format .xlsx
5. Uploader via l'interface admin

## Informations requises lors de l'upload

- **Nom de la classe** : Ex: "2 ING GII 3", "L3 INFO", "M1 MATH"
- **Date de version** : Date de création/modification de l'emploi du temps
