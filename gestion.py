import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import re # Importation du module re pour les expressions régulières/nettoyage

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Gestion Chauffagiste", page_icon="🔥", layout="wide")

# --- CONNEXION GOOGLE SHEETS (Compatible PC et Cloud) ---
# CHANGEMENT: Utiliser @st.cache_resource pour les connexions et ressources (Sheet, DB)
@st.cache_resource(ttl=3600) # Mise en cache de la CONNEXION pour 1h
def connexion_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # CAS 1 : On est sur le serveur (Streamlit Cloud)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        # CAS 2 : On est sur le PC en local (avec le fichier secrets.json)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
            
        client = gspread.authorize(creds)
        # Ouvre la feuille 
        sheet = client.open("Base Clients Chauffage").sheet1
        return sheet
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        st.stop()

# --- FONCTIONS ---
# CHANGEMENT: On retire le cache de cette fonction, car elle génère l'erreur d'hachage.
# La fonction est rapide car elle est appelée avec un objet 'sheet' mis en cache par @st.cache_resource.
def charger_donnees(sheet):
    # Récupère toutes les lignes du tableau
    lignes = sheet.get_all_records()
    db = {}
    for ligne in lignes:
        nom_complet = f"{ligne.get('Nom', '')} {ligne.get('Prenom', '')}".strip()
        if nom_complet: # S'assurer que le client a un nom
            try:
                # L'historique est stocké sous forme de texte codé (JSON), on le décode
                historique = json.loads(ligne.get('Historique', '')) if ligne.get('Historique') else []
            except:
                historique = []
            
            # Stockage de TOUS les champs
            client_data = {
                "nom": ligne.get('Nom', ''),
                "prenom": ligne.get('Prenom', ''),
                "adresse": ligne.get('Adresse', ''),
                "ville": ligne.get('Ville', ''),
                "code_postal": ligne.get('Code_Postal', ''),
                "telephone": ligne.get('Telephone', ''),
                "email": ligne.get('Email', ''),
                "equipement": ligne.get('Equipement', ''),
                "historique": historique
            }

            # NOUVEAU: Créer un index de recherche pour tous les champs pertinents
            index_fields = [
                client_data["nom"], client_data["prenom"], client_data["adresse"],
                client_data["ville"], client_data["code_postal"], client_data["telephone"],
                client_data["email"], client_data["equipement"]
            ]
            
            # Concaténation des champs, conversion en minuscules et nettoyage
            search_index = " ".join(str(f) for f in index_fields if f).lower()
            # Nettoyer l'index (enlever les caractères spéciaux qui ne facilitent pas la recherche)
            search_index = re.sub(r'[^a-z0-9\s]', '', search_index)
            client_data["recherche_index"] = search_index
            
            db[nom_complet] = client_data
            
    return db

def ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, tel, email, equipement):
    # On prépare la ligne à ajouter. 
    # L'ordre DOIT correspond à l'ordre de vos colonnes dans Google Sheet !
    nouvelle_ligne = [nom, prenom, adresse, ville, code_postal, tel, email, equipement, "[]"]
    sheet.append_row(nouvelle_ligne)
    # Après ajout, invalider le cache de la feuille pour que les données soient rechargées
    st.cache_resource.clear()
    st.cache_data.clear() # On garde cette ligne au cas où le décorateur est remis

def ajouter_inter_sheet(sheet, nom_client_cle, db, nouvelle_inter):
    historique = db[nom_client_cle]['historique']
    historique.append(nouvelle_inter)
    historique_txt = json.dumps(historique, ensure_ascii=False)
    
    # Pour la mise à jour, on a besoin du Nom ET du Prénom
    nom = db[nom_client_cle]['nom']
    # prenom = db[nom_client_cle]['prenom'] # Non utilisé ici, mais bien de le savoir
    
    try:
        # On cherche le client par son Nom (colonne 1)
        # ATTENTION: gspread.find ne peut chercher qu'un seul critère. On cherche le Nom.
        cellule = sheet.find(nom)
        # On cherche ensuite la cellule 'Historique' (qui est la 9ème colonne, index 9)
        # L'index 9 correspond à la 9ème colonne (A=1, B=2, ..., I=9)
        sheet.update_cell(cellule.row, 9, historique_txt) # Mise à jour de la colonne Historique (index 9)
    except:
        st.error("Impossible de retrouver la ligne du client pour la mise à jour de l'historique.")
        
    # Après ajout, invalider le cache de la feuille pour que les données soient rechargées
    st.cache_resource.clear()
    st.cache_data.clear() # On garde cette ligne au cas où le décorateur est remis


# --- INTERFACE GRAPHIQUE ---
st.title("🔥 App Chauffagiste - Connectée")
st.markdown("---")

# 1. Connexion
sheet = connexion_google_sheet()

# 2. Menu
# CHANGEMENT: Ajout d'une option "Mise à jour client" au menu
menu = st.sidebar.radio("Menu", ("🔍 Rechercher", "➕ Nouveau Client", "🛠️ Nouvelle Intervention", "✍️ Mettre à jour Client"))

# 3. Chargement des données
db = charger_donnees(sheet)

if menu == "➕ Nouveau Client":
    st.header("Nouveau Client")
    with st.form("form_nouveau"):
        # Organisation en colonnes pour une meilleure interface mobile
        col1, col2 = st.columns(2)
        
        with col1:
            nom = st.text_input("Nom")
            adresse = st.text_input("Adresse")
            code_postal = st.text_input("Code Postal")
            telephone = st.text_input("Téléphone")
            
        with col2:
            prenom = st.text_input("Prénom")
            ville = st.text_input("Ville")
            email = st.text_input("Email")
            equipement = st.text_input("Équipement (Chaudière, PAC, etc.)")
            
        valider = st.form_submit_button("Enregistrer le client")
        
        if valider and nom and prenom: # Exiger au moins Nom et Prénom
            nom_complet = f"{nom} {prenom}".strip()
            if nom_complet in db:
                st.warning(f"Le client {nom_complet} existe déjà dans la base.")
            else:
                ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, telephone, email, equipement)
                st.success(f"Client {nom_complet} ajouté !")
                # Forcer le rechargement des données après l'ajout
                st.rerun()

elif menu == "🛠️ Nouvelle Intervention":
    st.header("Nouvelle Intervention")
    if db:
        # Triage de la liste des clients pour le selectbox
        choix = st.selectbox("Client", sorted(db.keys()))
        date = st.date_input("Date", datetime.now())
        desc = st.text_area("Description de l'intervention")
        prix = st.number_input("Prix (en €)", step=10)
        
        if st.button("Valider l'intervention"):
            inter = {"date": str(date), "desc": desc, "prix": prix}
            ajouter_inter_sheet(sheet, choix, db, inter)
            st.success("Intervention sauvegardée en ligne !")
            # Forcer le rechargement des données après l'ajout
            st.rerun()
    else:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")

# AJOUT : Section pour mettre à jour les informations d'un client
elif menu == "✍️ Mettre à jour Client":
    st.header("Mettre à jour les informations d'un client")
    if not db:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")
    else:
        client_selectionne = st.selectbox("Sélectionnez le client à modifier", sorted(db.keys()))
        
        if client_selectionne:
            infos_actuelles = db[client_selectionne]
            
            st.subheader(f"Modification de {client_selectionne}")
            
            with st.form("form_update_client"):
                # Prérremplir avec les valeurs actuelles
                col1_up, col2_up = st.columns(2)
                
                with col1_up:
                    # Les champs Nom et Prénom ne sont pas modifiables directement car ils sont la clé de recherche.
                    # On les affiche en lecture seule.
                    st.text_input("Nom (Clé)", value=infos_actuelles['nom'], disabled=True)
                    nouvelle_adresse = st.text_input("Adresse", value=infos_actuelles['adresse'])
                    nouveau_code_postal = st.text_input("Code Postal", value=infos_actuelles['code_postal'])
                    nouveau_telephone = st.text_input("Téléphone", value=infos_actuelles['telephone'])
                    
                with col2_up:
                    st.text_input("Prénom (Clé)", value=infos_actuelles['prenom'], disabled=True)
                    nouvelle_ville = st.text_input("Ville", value=infos_actuelles['ville'])
                    nouvel_email = st.text_input("Email", value=infos_actuelles['email'])
                    nouvel_equipement = st.text_input("Équipement", value=infos_actuelles['equipement'])
                
                update_valider = st.form_submit_button("Sauvegarder les modifications")
                
                if update_valider:
                    # Les colonnes de la feuille sont (A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8, I=9)
                    
                    try:
                        # 1. On cherche la ligne du client (par son Nom)
                        cellule = sheet.find(infos_actuelles['nom'])
                        ligne_a_modifier = cellule.row
                        
                        # 2. On met à jour les champs (sauf Nom, Prénom et Historique)
                        # Adresse (C=3)
                        sheet.update_cell(ligne_a_modifier, 3, nouvelle_adresse)
                        # Ville (D=4)
                        sheet.update_cell(ligne_a_modifier, 4, nouvelle_ville)
                        # Code Postal (E=5)
                        sheet.update_cell(ligne_a_modifier, 5, nouveau_code_postal)
                        # Téléphone (F=6)
                        sheet.update_cell(ligne_a_modifier, 6, nouveau_telephone)
                        # Email (G=7)
                        sheet.update_cell(ligne_a_modifier, 7, nouvel_email)
                        # Equipement (H=8)
                        sheet.update_cell(ligne_a_modifier, 8, nouvel_equipement)
                        
                        st.success(f"Informations du client {client_selectionne} mises à jour !")
                        
                        # 3. Forcer le rechargement des données
                        st.cache_resource.clear()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Erreur lors de la mise à jour : Impossible de trouver la ligne du client. {e}")
                        

elif menu == "🔍 Rechercher":
    st.header("Recherche de Clients Multi-critères")
    # NOUVEAU: Le champ de recherche est utilisé pour chercher dans l'index complet
    recherche = st.text_input("Entrez un terme (Nom, Prénom, Adresse, Ville, CP, Équipement...) :")
    
    # -----------------------------------------------------
    # LOGIQUE DE FILTRAGE
    # -----------------------------------------------------
    resultats = []
    if recherche:
        search_term = recherche.lower()
        # Nettoyage du terme de recherche pour correspondre au format de l'index
        search_term = re.sub(r'[^a-z0-9\s]', '', search_term).strip()
        
        if search_term:
            # On cherche si le terme de recherche se trouve n'importe où dans l'index_recherche
            for nom_complet, client_data in db.items():
                if search_term in client_data['recherche_index']:
                    resultats.append(nom_complet)
        
    else:
        # Si le champ de recherche est vide, on affiche tous les clients (par ordre alphabétique)
        resultats = sorted(db.keys())

    if resultats:
        st.subheader(f"Résultats ({len(resultats)})")
        
        # Le selectbox affiche uniquement les clients trouvés
        selection = st.selectbox("Sélectionnez le client pour voir les détails", sorted(resultats))
        
        if selection:
            infos = db[selection]
            
            st.subheader(f"Informations de {infos['nom']} {infos['prenom']}")
            
            col_tel, col_mail = st.columns(2)
            with col_tel:
                st.markdown(f"**📞 Téléphone :** {infos['telephone'] or 'N/A'}")
            with col_mail:
                st.markdown(f"**📧 Email :** {infos['email'] or 'N/A'}")
                
            st.markdown(f"**🏠 Adresse :** {infos['adresse'] or 'N/A'}, {infos['code_postal'] or 'N/A'} {infos['ville'] or 'N/A'}")
            st.markdown(f"**🔧 Équipement :** {infos['equipement'] or 'N/A'}")
            
            st.subheader("Historique des Interventions")
            if infos['historique']:
                # Afficher la dernière intervention en haut
                for h in sorted(infos['historique'], key=lambda x: x['date'], reverse=True): # Trie par date
                    st.info(f"📅 **{h['date']}** : {h['desc']} ({h['prix']}€)")
            else:
                st.write("Aucune intervention enregistrée pour ce client.")
    else:
        st.warning("Aucun client trouvé correspondant à la recherche.")
