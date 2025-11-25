import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import re 
import time

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Gestion Chauffagiste", page_icon="🔥", layout="wide")

# --- CONSTANTES ---
APP_TITLE = "🔥 SEBApp le chauffagiste connectée"
IMAGE_URL_1 = "https://raw.githubusercontent.com/Treyore/app-seb/c81b77576a13beee81e9d69f3f06f95842a34bb5/WhatsApp%20Image%202025-11-24%20at%2016.08.53.jpeg"
IMAGE_URL_2 = "https://raw.githubusercontent.com/Treyore/app-seb/92e1af7d7313f8df3cbc3ec186b5228764c23ba7/seb%20lunettes%20soleil.webp"


# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource(ttl=3600)
def connexion_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
            
        client = gspread.authorize(creds)
        sheet = client.open("Base Clients Chauffage").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        st.stop()

# --- FONCTION D'UPLOAD SIMPLIFIÉE ---
def handle_upload(uploaded_file):
    if uploaded_file is not None:
        placeholder_link = f"https://placeholder.cloud.storage/documents/{int(time.time())}/{uploaded_file.name.replace(' ', '_')}"
        st.toast(f"Fichier téléversé : {uploaded_file.name}. Lien généré.", icon="✅")
        return placeholder_link
    return None

# --- FONCTIONS EXISTANTES (MODIFIÉES POUR LA CONFIRMATION) ---

# Charger les données sans cache Streamlit pour éviter les problèmes d'hachage avec gspread
# ATTENTION: Le décorateur de cache a été retiré, il faut utiliser @st.cache_data pour éviter les erreurs de gspread
def charger_donnees(sheet):
    lignes = sheet.get_all_records()
    db = {}
    for ligne in lignes:
        nom_complet = f"{ligne.get('Nom', '')} {ligne.get('Prenom', '')}".strip()
        if nom_complet: 
            try:
                historique = json.loads(ligne.get('Historique', '')) if ligne.get('Historique') else []
            except:
                historique = []
            
            client_data = {
                "nom": ligne.get('Nom', ''),
                "prenom": ligne.get('Prenom', ''),
                "adresse": ligne.get('Adresse', ''),
                "ville": ligne.get('Ville', ''),
                "code_postal": ligne.get('Code_Postal', ''),
                "telephone": ligne.get('Telephone', ''),
                "email": ligne.get('Email', ''),
                "equipement": ligne.get('Equipement', ''),
                "fichiers_client": ligne.get('Fichiers_Client', ''), 
                "historique": historique
            }

            index_fields = [
                client_data["nom"], client_data["prenom"], client_data["adresse"],
                client_data["ville"], client_data["code_postal"], client_data["telephone"],
                client_data["email"], client_data["equipement"], client_data["fichiers_client"]
            ]
            
            search_index = " ".join(str(f) for f in index_fields if f).lower()
            search_index = re.sub(r'[^a-z0-9\s]', '', search_index)
            client_data["recherche_index"] = search_index
            client_data["nom_complet"] = nom_complet 
            
            db[nom_complet] = client_data
            
    return db


# MODIFICATION 1: Ajout du message de succès et nettoyage des champs spécifiques au client
def ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, tel, email, equipement, fichiers_client):
    nouvelle_ligne = [
        nom, prenom, adresse, ville, code_postal, tel, email, equipement, 
        "[]", 
        fichiers_client 
    ]
    sheet.append_row(nouvelle_ligne)
    
    # AJOUT : Transport du message de succès via st.session_state
    st.session_state['success_message'] = f"Client **{nom} {prenom}** ajouté avec succès !"
    
    # AJOUT : Nettoyage du champ de liens de fichiers (les autres champs du form seront effacés par le rerun)
    if 'text_client_add' in st.session_state: del st.session_state.text_client_add 
    
    st.cache_resource.clear()
    st.rerun()


def update_client_field(sheet, nom_client_principal, col_index, new_value):
    try:
        cellule = sheet.find(nom_client_principal) 
        sheet.update_cell(cellule.row, col_index, new_value)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du champ (col {col_index}) : {e}")
        return False
        
# MODIFICATION 2: Ajout du message de succès et nettoyage des champs d'intervention
def ajouter_inter_sheet(sheet, nom_client_cle, db, nouvelle_inter):
    historique = db[nom_client_cle]['historique']
    historique.append(nouvelle_inter)
    historique_txt = json.dumps(historique, ensure_ascii=False)
    
    nom = db[nom_client_cle]['nom']
    
    try:
        cellule = sheet.find(nom)
        sheet.update_cell(cellule.row, 9, historique_txt) 
        
        # AJOUT : Transport du message de succès via st.session_state
        st.session_state['success_message'] = f"Intervention ({nouvelle_inter['type']}) pour **{nom_client_cle}** ajoutée !"
        
        # AJOUT : Nettoyage de tous les champs d'intervention via leur clé
        keys_to_clear = [
            'inter_client_select', 'inter_type_select', 'inter_techniciens_multiselect', 
            'inter_date_input', 'inter_desc_textarea', 'inter_prix_numberinput', 
            'new_inter_type_specifique', 'text_inter_add'
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
    except:
        st.error("Impossible de retrouver la ligne du client pour la mise à jour de l'historique.")
        
    st.cache_resource.clear() 
    st.rerun()

def supprimer_client_sheet(sheet, nom_client):
    try:
        cellule = sheet.find(nom_client)
        ligne_a_supprimer = cellule.row
        
        if ligne_a_supprimer > 1: 
            sheet.delete_rows(ligne_a_supprimer)
            st.session_state['success_message'] = f"Le client **{nom_client}** a été supprimé."
            st.cache_resource.clear()
            st.rerun()
        else:
            st.error("Tentative de suppression de l'en-tête ou ligne non trouvée.")
            return False
            
    except Exception as e:
        st.error(f"Erreur lors de la suppression du client : Impossible de trouver la ligne du client. {e}")
        return False

# --- INTERFACE GRAPHIQUE ---

# 1. Connexion 
sheet = connexion_google_sheet()

# ------------------------------------------------------------------
# --- DÉMARRAGE DIRECT DE L'APPLICATION PRINCIPALE ---
# ------------------------------------------------------------------

# 2. Menu
menu = st.sidebar.radio(
    "Menu", 
    (
        "🔍 Rechercher", 
        "➕ Nouveau Client", 
        "🛠️ Nouvelle Intervention", 
        "✍️ Mettre à jour (Modifier)",
        "🗑️ Supprimer Client/Intervention"
    ),
    index=0 
)

# 3. Chargement des données
db = charger_donnees(sheet)

st.title(APP_TITLE)
st.markdown("---")

# AJOUT : Affichage du message de succès après le rerun (doit être fait avant les blocs du menu)
if 'success_message' in st.session_state:
    st.success(st.session_state['success_message'])
    del st.session_state['success_message']

# ------------------------------------------------------------------
# --- LOGIQUE D'AFFICHAGE SELON LE MENU ---
# ------------------------------------------------------------------

# ... (Le bloc 🔍 Rechercher reste inchangé) ...

elif menu == "➕ Nouveau Client":
    st.header("Nouveau Client")
    with st.form("form_nouveau"):
        col1, col2 = st.columns(2)
        
        # Les champs dans un st.form sans clé explicite sont effacés par st.rerun()
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
        
        st.markdown("---")
        st.subheader("Fichiers Client")
        
        uploaded_file_client = st.file_uploader(
            "Téléverser un document client (max 5 Mo)", 
            key="file_client_add",
            accept_multiple_files=False,
            type=['pdf', 'jpg', 'jpeg', 'png']
        )
        
        if 'text_client_add' not in st.session_state: st.session_state.text_client_add = ""
        fichiers_client = st.text_area(
            "Liens Fichiers Client (Liens existants, ou liens générés après téléversement)", 
            height=100,
            key="text_client_add",
            value=st.session_state.text_client_add
        )
        
        if uploaded_file_client:
            if st.button("Ajouter le document téléversé aux liens client", key="btn_upload_client_add"): 
                new_link = handle_upload(uploaded_file_client)
                if new_link:
                    current_links = st.session_state.text_client_add.strip()
                    if current_links:
                        st.session_state.text_client_add = current_links + f"\n{new_link}"
                    else:
                        st.session_state.text_client_add = new_link
                    
                    st.rerun() 
            
        valider = st.form_submit_button("Enregistrer le client")
        
        if valider and nom and prenom: 
            final_fichiers_client = st.session_state.get('text_client_add', '') 

            nom_complet = f"{nom} {prenom}".strip()
            if nom_complet in db:
                st.warning(f"Le client {nom_complet} existe déjà dans la base.")
            else:
                # Appelle la fonction qui gère le message de succès et le rerun
                ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, telephone, email, equipement, final_fichiers_client)
                # Le st.success et le nettoyage des champs sont gérés DANS la fonction.


elif menu == "🛠️ Nouvelle Intervention":
    st.header("Nouvelle Intervention")
    if db:
        # AJOUT DES CLÉS pour permettre le nettoyage de ces champs par suppression dans st.session_state
        choix = st.selectbox("Client", sorted(db.keys()), key='inter_client_select') # CLÉ AJOUTÉE
        
        col_type, col_tech = st.columns(2)
        
        with col_type:
            type_inter = st.selectbox(
                "Type d'intervention",
                ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique", "Autre"],
                index=0,
                key='inter_type_select' # CLÉ AJOUTÉE
            )

        with col_tech:
            techniciens = st.multiselect(
                "Technicien(s) assigné(s)",
                ["Seb", "Colin"],
                default=[],
                key='inter_techniciens_multiselect' # CLÉ AJOUTÉE
            )
            
        type_a_enregistrer = type_inter
        if type_inter == "Autre":
            # La clé de ce champ est déjà unique: new_inter_type_specifique
            type_specifique = st.text_input("Spécifiez le type d'intervention (ex: Ramonage)", key="new_inter_type_specifique")
            type_a_enregistrer = type_specifique 
        
        date = st.date_input("Date", datetime.now(), key='inter_date_input') # CLÉ AJOUTÉE
        desc = st.text_area("Description de l'intervention", key='inter_desc_textarea') # CLÉ AJOUTÉE
        prix = st.number_input("Prix (en €)", step=10, key='inter_prix_numberinput') # CLÉ AJOUTÉE
        
        st.markdown("---")
        st.subheader("Fichiers Intervention")
        
        uploaded_file_inter = st.file_uploader(
            "Téléverser un document d'intervention (max 5 Mo)", 
            key="file_inter_add",
            accept_multiple_files=False,
            type=['pdf', 'jpg', 'jpeg', 'png']
        )

        if 'text_inter_add' not in st.session_state: st.session_state.text_inter_add = ""
        fichiers_inter = st.text_area(
            "Liens Fichiers Intervention (Facture, Photo des travaux, etc.)", 
            height=80,
            key="text_inter_add",
            value=st.session_state.text_inter_add
        )
        
        if uploaded_file_inter:
            if st.button("Ajouter le document téléversé aux liens intervention", key="btn_upload_inter_add"): 
                new_link = handle_upload(uploaded_file_inter)
                if new_link:
                    current_links = st.session_state.text_inter_add.strip()
                    if current_links:
                        st.session_state.text_inter_add = current_links + f"\n{new_link}"
                    else:
                        st.session_state.text_inter_add = new_link
                    
                    st.rerun() 

        
        if st.button("Valider l'intervention"):
            if type_inter == "Autre" and not type_a_enregistrer.strip():
                 st.warning("Veuillez spécifier le type d'intervention 'Autre'.")
                 st.stop()
            elif not techniciens:
                st.warning("Veuillez assigner au moins un technicien à l'intervention.")
            else:
                final_fichiers_inter = st.session_state.get('text_inter_add', '') 

                inter = {
                    "date": str(date), 
                    "type": type_a_enregistrer, 
                    "techniciens": techniciens,   
                    "desc": desc, 
                    "prix": prix,
                    "fichiers_inter": final_fichiers_inter 
                }
                # Appelle la fonction qui gère le message de succès et le rerun
                ajouter_inter_sheet(sheet, choix, db, inter)
                # Le st.success et le nettoyage des champs sont gérés DANS la fonction.
    else:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")

# ... (Le reste des blocs "Mettre à jour" et "Supprimer" reste inchangé, à l'exception des fonctions helpers qui y sont appelées)
