import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Gestion Chauffagiste", page_icon="🔥", layout="wide")

# --- CONNEXION GOOGLE SHEETS ---
def connexion_google_sheet():
    # On définit les droits d'accès
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # On utilise le fichier secret pour se connecter
        creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
        client = gspread.authorize(creds)
        
        # Ouvre la feuille (Attention: le nom doit être EXACTEMENT celui de votre fichier Google Sheet)
        # Si votre fichier s'appelle "Base Clients Chauffage", laissez tel quel.
        sheet = client.open("Base Clients Chauffage").sheet1
        return sheet
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        st.stop()

# --- FONCTIONS ---
def charger_donnees(sheet):
    # Récupère toutes les lignes du tableau
    lignes = sheet.get_all_records()
    # On transforme la liste en dictionnaire pour faciliter la recherche par nom
    db = {}
    for ligne in lignes:
        nom = ligne['Nom']
        if nom: # Si le nom n'est pas vide
            try:
                # L'historique est stocké sous forme de texte codé (JSON), on le décode
                historique = json.loads(ligne['Historique']) if ligne['Historique'] else []
            except:
                historique = []
                
            db[nom] = {
                "telephone": ligne['Telephone'],
                "adresse": ligne['Adresse'],
                "equipement": ligne['Equipement'],
                "historique": historique,
                "row_id": ligne # On garde une trace pour savoir quelle ligne modifier (optionnel)
            }
    return db

def ajouter_nouveau_client_sheet(sheet, nom, tel, adresse, equipement):
    # On prépare la ligne à ajouter. L'historique est vide au début "[]"
    nouvelle_ligne = [nom, tel, adresse, equipement, "[]"]
    sheet.append_row(nouvelle_ligne)

def ajouter_inter_sheet(sheet, nom_client, db, nouvelle_inter):
    # 1. On récupère l'ancien historique du code
    historique = db[nom_client]['historique']
    # 2. On ajoute la nouvelle inter
    historique.append(nouvelle_inter)
    # 3. On re-transforme tout l'historique en texte pour le stocker
    historique_txt = json.dumps(historique, ensure_ascii=False)
    
    # 4. On cherche la ligne du client dans le tableau pour la mettre à jour
    cellule = sheet.find(nom_client)
    # On met à jour la colonne 5 (Historique)
    sheet.update_cell(cellule.row, 5, historique_txt)

# --- INTERFACE GRAPHIQUE ---
st.title("🔥 App Chauffagiste (Connectée Cloud)")
st.markdown("---")

# 1. Connexion
sheet = connexion_google_sheet()
# 2. Chargement
if "db" not in st.session_state:
    st.session_state["db"] = charger_donnees(sheet)

# On recharge les données à chaque action pour être sûr d'être à jour
db = charger_donnees(sheet)

# Menu
menu = st.sidebar.radio("Menu", ("🔍 Rechercher", "➕ Nouveau Client", "🛠️ Nouvelle Intervention"))

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
                st.success(f"Client {nom} ajouté au Google Sheet !")
                st.rerun()

elif menu == "🛠️ Nouvelle Intervention":
    st.header("Intervention")
    if db:
        choix = st.selectbox("Client", sorted(db.keys()))
        date = st.date_input("Date", datetime.now())
        desc = st.text_area("Description")
        prix = st.number_input("Prix", step=10)
        
        if st.button("Valider"):
            inter = {"date": str(date), "desc": desc, "prix": prix}
            ajouter_inter_sheet(sheet, choix, db, inter)
            st.success("Sauvegardé en ligne !")
            st.rerun()
    else:
        st.info("La base est vide.")

elif menu == "🔍 Rechercher":
    st.header("Fichier Clients")
    recherche = st.text_input("Chercher un nom :")
    
    # Filtrer
    resultats = [n for n in db.keys() if recherche.lower() in n.lower()]
    
    if resultats:
        selection = st.selectbox("Résultats", resultats)
        infos = db[selection]
        
        st.write(f"**🏠 Adresse :** {infos['adresse']}")
        st.write(f"**📞 Tél :** {infos['telephone']}")
        st.write(f"**🔧 Matos :** {infos['equipement']}")
        
        st.subheader("Historique")
        if infos['historique']:
            for h in infos['historique']:
                st.info(f"📅 {h['date']} : {h['desc']} ({h['prix']}€)")
        else:
            st.write("Rien à signaler.")
    else:
        st.warning("Aucun résultat.")