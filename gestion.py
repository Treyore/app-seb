import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

# --- INJECTION CSS PERSONNALISÉ (Image de fond) ---
def set_background_image():
    # C'EST L'URL BRUTE (RAW) DE VOTRE IMAGE. 
    # Elle est longue, mais elle est la seule à fonctionner pour le fond.
    image_url = "https://raw.githubusercontent.com/Treyore/app-seb/8a1a983ffac5e52fee08e4c5e710898c4cefcafc/WhatsApp%20Image%202025-11-24%20at%2015.08.58.jpeg" 
    
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("{image_url}");
            background-size: cover;          /* L'image couvre tout l'écran */
            background-attachment: fixed;    /* L'image ne bouge pas en scrollant */
            background-position: center;     /* Centre l'image */
            opacity: 0.9;                    /* Rend l'image 10% transparente pour la lisibilité */
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
set_background_image() 

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Gestion Chauffagiste", page_icon="🔥", layout="wide")

# --- CONNEXION GOOGLE SHEETS (Compatible PC et Cloud) ---
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
def charger_donnees(sheet):
    lignes = sheet.get_all_records()
    db = {}
    for ligne in lignes:
        nom = ligne['Nom']
        if nom:
            try:
                historique = json.loads(ligne['Historique']) if ligne['Historique'] else []
            except:
                historique = []
            
            # On gère les majuscules/minuscules des colonnes pour éviter les erreurs
            tel = ligne.get('Telephone', ligne.get('telephone', ''))
            adresse = ligne.get('Adresse', ligne.get('adresse', ''))
            equip = ligne.get('Equipement', ligne.get('equipement', ''))
            
            db[nom] = {
                "telephone": tel,
                "adresse": adresse,
                "equipement": equip,
                "historique": historique
            }
    return db

def ajouter_nouveau_client_sheet(sheet, nom, tel, adresse, equipement):
    nouvelle_ligne = [nom, tel, adresse, equipement, "[]"]
    sheet.append_row(nouvelle_ligne)

def ajouter_inter_sheet(sheet, nom_client, db, nouvelle_inter):
    historique = db[nom_client]['historique']
    historique.append(nouvelle_inter)
    historique_txt = json.dumps(historique, ensure_ascii=False)
    
    try:
        cellule = sheet.find(nom_client)
        sheet.update_cell(cellule.row, 5, historique_txt)
    except:
        st.error("Impossible de retrouver la ligne du client pour la mise à jour.")

# --- INTERFACE GRAPHIQUE ---
st.title("🔥 App Chauffagiste - Connectée")
st.markdown("---")

# 1. Connexion
sheet = connexion_google_sheet()

# 2. Menu
menu = st.sidebar.radio("Menu", ("🔍 Rechercher", "➕ Nouveau Client", "🛠️ Nouvelle Intervention"))

# 3. Chargement des données
# On recharge à chaque action pour être sûr d'avoir les infos à jour
db = charger_donnees(sheet)

if menu == "➕ Nouveau Client":
    st.header("Nouveau Client")
    with st.form("form_nouveau"):
        nom = st.text_input("Nom")
        tel = st.text_input("Tél")
        adresse = st.text_input("Adresse")
        equipement = st.text_input("Équipement")
        valider = st.form_submit_button("Enregistrer")
        
        if valider and nom:
            if nom in db:
                st.warning("Ce client existe déjà.")
            else:
                ajouter_nouveau_client_sheet(sheet, nom, tel, adresse, equipement)
                st.success(f"Client {nom} ajouté !")
                st.rerun()

elif menu == "🛠️ Nouvelle Intervention":
    st.header("Intervention")
    if db:
        choix = st.selectbox("Client", sorted(db.keys()))
        date = st.date_input("Date", datetime.now())
        desc = st.text_area("Description")
        prix = st.number_input("Prix", step=10.0)
        
        if st.button("Valider l'intervention"):
            inter = {"date": str(date), "desc": desc, "prix": prix}
            ajouter_inter_sheet(sheet, choix, db, inter)
            st.success("Sauvegardé !")
            st.rerun()
    else:
        st.info("La base est vide.")

elif menu == "🔍 Rechercher":
    st.header("Fichier Clients")
    recherche = st.text_input("Chercher un nom :")
    
    resultats = [n for n in db.keys() if recherche.lower() in n.lower()]
    
    if resultats:
        selection = st.selectbox("Résultats", resultats)
        infos = db[selection]
        
        st.markdown(f"**🏠 Adresse :** {infos['adresse']}")
        st.markdown(f"**📞 Tél :** {infos['telephone']}")
        st.markdown(f"**🔧 Matos :** {infos['equipement']}")
        
        st.subheader("Historique")
        if infos['historique']:
            for h in infos['historique']:
                st.info(f"📅 {h['date']} : {h['desc']} ({h['prix']}€)")
        else:
            st.write("Aucune intervention passée.")
    else:
        st.warning("Aucun résultat.")
