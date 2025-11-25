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

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource(ttl=3600)
def connexion_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # CAS 1 : On est sur le serveur (Streamlit Cloud)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        # CAS 2 : On est sur le PC en local
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
            
        client = gspread.authorize(creds)
        sheet = client.open("Base Clients Chauffage").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        st.stop()

# --- FONCTION SIMULATION UPLOAD ---
def handle_upload(uploaded_file):
    """
    Simule le téléversement et retourne un lien.
    """
    if uploaded_file is not None:
        placeholder_link = f"https://placeholder.cloud.storage/documents/{int(time.time())}/{uploaded_file.name.replace(' ', '_')}"
        st.toast(f"Fichier téléversé : {uploaded_file.name}. Lien généré.", icon="✅")
        return placeholder_link
    return None

# --- CHARGEMENT DES DONNÉES ---
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

# --- AJOUT NOUVEAU CLIENT AVEC RESET ---
def ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, tel, email, equipement, fichiers_client):
    # Colonne I (9) = Historique, Colonne J (10) = Fichiers_Client
    nouvelle_ligne = [
        nom, prenom, adresse, ville, code_postal, tel, email, equipement, 
        "[]", 
        fichiers_client
    ]
    sheet.append_row(nouvelle_ligne)
    
    # 1. Message de succès pour le prochain rechargement
    st.session_state['success_message'] = f"✅ Client **{nom} {prenom}** ajouté avec succès !"
    
    # 2. RESET des champs du formulaire Client
    # On vide les valeurs dans session_state correspondantes aux clefs (keys)
    keys_to_reset = ['nc_nom', 'nc_prenom', 'nc_adresse', 'nc_cp', 'nc_tel', 'nc_ville', 'nc_email', 'nc_equip', 'text_client_add']
    for key in keys_to_reset:
        if key in st.session_state:
            st.session_state[key] = ""
            
    st.cache_resource.clear()
    st.rerun()

# --- MISE A JOUR CHAMP UNIQUE ---
def update_client_field(sheet, nom_client_principal, col_index, new_value):
    try:
        cellule = sheet.find(nom_client_principal) 
        sheet.update_cell(cellule.row, col_index, new_value)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du champ (col {col_index}) : {e}")
        return False
        
# --- AJOUT INTERVENTION AVEC RESET ---
def ajouter_inter_sheet(sheet, nom_client_cle, db, nouvelle_inter):
    historique = db[nom_client_cle]['historique']
    historique.append(nouvelle_inter)
    historique_txt = json.dumps(historique, ensure_ascii=False)
    
    nom = db[nom_client_cle]['nom']
    
    try:
        cellule = sheet.find(nom)
        # Historique en colonne 9
        sheet.update_cell(cellule.row, 9, historique_txt) 
        
        # 1. Message de succès
        st.session_state['success_message'] = f"✅ Intervention ajoutée pour **{nom}** !"
        
        # 2. RESET des champs du formulaire Intervention
        st.session_state['inter_desc'] = ""
        st.session_state['inter_type_spec'] = ""
        st.session_state['text_inter_add'] = ""
        st.session_state['inter_prix'] = 0.0
        st.session_state['inter_techs'] = []
        st.session_state['inter_date'] = datetime.now()
        # Note: on ne reset pas le selectbox client ou type pour éviter des erreurs d'index, ou on les remet à défaut si besoin.
        
    except:
        st.error("Impossible de retrouver la ligne du client.")
        
    st.cache_resource.clear()
    st.rerun()

# --- SUPPRESSION CLIENT ---
def supprimer_client_sheet(sheet, nom_client):
    try:
        cellule = sheet.find(nom_client)
        ligne_a_supprimer = cellule.row
        
        if ligne_a_supprimer > 1: 
            sheet.delete_rows(ligne_a_supprimer)
            st.session_state['success_message'] = f"🗑️ Client **{nom_client}** supprimé définitivement."
            return True
        else:
            st.error("Impossible de supprimer cette ligne.")
            return False
    except Exception as e:
        st.error(f"Erreur suppression : {e}")
        return False

# --- DÉBUT DE L'INTERFACE ---

sheet = connexion_google_sheet()

# Menu latéral
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

# Chargement données
db = charger_donnees(sheet)

st.title(APP_TITLE)
st.markdown("---")

# --- ZONE DE MESSAGE DE CONFIRMATION ---
# C'est ici que le message s'affiche après le rechargement de la page
if 'success_message' in st.session_state:
    st.success(st.session_state['success_message'])
    # On supprime le message pour qu'il ne réapparaisse pas au prochain clic
    del st.session_state['success_message']


# --- PAGE: RECHERCHE ---
if menu == "🔍 Rechercher":
    st.header("Recherche de Clients")
    recherche = st.text_input("Entrez un terme (Nom, Prénom, Adresse, Ville...) :")
    
    resultats = []
    if recherche:
        search_term = re.sub(r'[^a-z0-9\s]', '', recherche.lower()).strip()
        if search_term:
            for nom_complet, client_data in db.items():
                if search_term in client_data['recherche_index']:
                    resultats.append(nom_complet)
    else:
        resultats = sorted(db.keys())

    if resultats:
        st.subheader(f"Résultats ({len(resultats)})")
        selection = st.selectbox("Sélectionnez le client", sorted(resultats))
        
        if selection:
            infos = db[selection]
            
            st.subheader(f"{infos['nom']} {infos['prenom']}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**📞 Tél:** {infos['telephone']}")
                st.write(f"**🏠 Adr:** {infos['adresse']}, {infos['code_postal']} {infos['ville']}")
            with c2:
                st.write(f"**📧 Email:** {infos['email']}")
                st.write(f"**🔧 Equip:** {infos['equipement']}")
                
            st.markdown("---")
            st.markdown("**📂 Fichiers Client :**")
            if infos['fichiers_client']:
                links = re.split(r'[,\n]', infos['fichiers_client'])
                for link in [l.strip() for l in links if l.strip()]:
                    if link.startswith('http'):
                        st.markdown(f"- [Ouvrir document]({link})")
                    else:
                        st.markdown(f"- {link}")
            else:
                st.write("Aucun fichier.")
                
            st.markdown("---")
            st.subheader("Historique Interventions")
            if infos['historique']:
                for h in sorted(infos['historique'], key=lambda x: x['date'], reverse=True):
                    techs = ", ".join(h.get('techniciens', []))
                    st.info(f"**{h['type']}** par {techs} le **{h['date']}** : {h['desc']} ({h['prix']}€)")
                    
                    if h.get('fichiers_inter'):
                        st.markdown("**Pièces jointes :**")
                        for l in h['fichiers_inter'].split('\n'):
                            if l.strip(): st.markdown(f"- {l}")
            else:
                st.write("Aucune intervention.")
    else:
        st.warning("Aucun résultat.")


# --- PAGE: NOUVEAU CLIENT ---
elif menu == "➕ Nouveau Client":
    st.header("Nouveau Client")
    with st.form("form_nouveau"):
        c1, c2 = st.columns(2)
        
        # AJOUT DES CLÉS (KEY) POUR PERMETTRE LE RESET
        with c1:
            nom = st.text_input("Nom", key="nc_nom")
            adresse = st.text_input("Adresse", key="nc_adresse")
            code_postal = st.text_input("Code Postal", key="nc_cp")
            telephone = st.text_input("Téléphone", key="nc_tel")
            
        with c2:
            prenom = st.text_input("Prénom", key="nc_prenom")
            ville = st.text_input("Ville", key="nc_ville")
            email = st.text_input("Email", key="nc_email")
            equipement = st.text_input("Équipement", key="nc_equip")
        
        st.markdown("---")
        st.subheader("Fichiers Client")
        
        # Upload
        uploaded_file_client = st.file_uploader("Document Client", key="file_nc")
        
        # Champ liens avec clé
        if 'text_client_add' not in st.session_state: st.session_state.text_client_add = ""
        fichiers_client = st.text_area("Liens Fichiers", key="text_client_add")
        
        # Bouton intermédiaire pour générer le lien (ne soumet pas le form principal)
        if uploaded_file_client:
            if st.form_submit_button("Générer le lien du fichier (Cliquer avant d'enregistrer)"):
                new_link = handle_upload(uploaded_file_client)
                if new_link:
                    st.session_state.text_client_add += f"\n{new_link}"
                    st.rerun()
            
        valider = st.form_submit_button("Enregistrer le client")
        
        if valider:
            if nom and prenom:
                nom_complet = f"{nom} {prenom}".strip()
                if nom_complet in db:
                    st.warning("Ce client existe déjà.")
                else:
                    ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, telephone, email, equipement, fichiers_client)
            else:
                st.error("Le Nom et Prénom sont obligatoires.")


# --- PAGE: NOUVELLE INTERVENTION ---
elif menu == "🛠️ Nouvelle Intervention":
    st.header("Nouvelle Intervention")
    if db:
        # Sélection client
        choix = st.selectbox("Client", sorted(db.keys()), key="inter_client_select")
        
        c1, c2 = st.columns(2)
        with c1:
            type_inter = st.selectbox(
                "Type d'intervention",
                ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique", "Autre"],
                key="inter_type_select"
            )
        with c2:
            techniciens = st.multiselect("Techniciens", ["Seb", "Colin"], key="inter_techs")
            
        # Logique Autre
        type_final = type_inter
        if type_inter == "Autre":
            type_spec = st.text_input("Précisez le type", key="inter_type_spec")
            type_final = type_spec
        
        # Champs avec clés pour reset
        date = st.date_input("Date", datetime.now(), key="inter_date")
        desc = st.text_area("Description", key="inter_desc")
        prix = st.number_input("Prix (€)", step=10.0, key="inter_prix")
        
        st.markdown("---")
        uploaded_file_inter = st.file_uploader("Document Intervention", key="file_inter")
        
        if 'text_inter_add' not in st.session_state: st.session_state.text_inter_add = ""
        fichiers_inter = st.text_area("Liens Fichiers", key="text_inter_add")
        
        if uploaded_file_inter:
            if st.button("Générer lien fichier"):
                link = handle_upload(uploaded_file_inter)
                if link:
                    st.session_state.text_inter_add += f"\n{link}"
                    st.rerun()

        if st.button("Valider l'intervention"):
            if type_inter == "Autre" and not type_final.strip():
                 st.warning("Précisez le type.")
            elif not techniciens:
                st.warning("Choisissez un technicien.")
            else:
                inter = {
                    "date": str(date), 
                    "type": type_final, 
                    "techniciens": techniciens,   
                    "desc": desc, 
                    "prix": prix,
                    "fichiers_inter": fichiers_inter 
                }
                ajouter_inter_sheet(sheet, choix, db, inter)
    else:
        st.info("Base vide.")


# --- PAGE: MISE A JOUR ---
elif menu == "✍️ Mettre à jour (Modifier)":
    st.header("Modifier Client / Intervention")
    if db:
        client_sel = st.selectbox("Client", sorted(db.keys()), key="mod_sel")
        if client_sel:
            infos = db[client_sel]
            
            st.subheader("Infos Générales")
            with st.form("mod_infos"):
                c1, c2 = st.columns(2)
                with c1:
                    n_addr = st.text_input("Adresse", infos['adresse'])
                    n_cp = st.text_input("CP", infos['code_postal'])
                    n_tel = st.text_input("Tél", infos['telephone'])
                with c2:
                    n_ville = st.text_input("Ville", infos['ville'])
                    n_mail = st.text_input("Email", infos['email'])
                    n_eq = st.text_input("Equipement", infos['equipement'])
                
                # Gestion fichiers
                k_files = f"f_mod_{client_sel}"
                if k_files not in st.session_state: st.session_state[k_files] = infos['fichiers_client']
                n_files = st.text_area("Liens Fichiers", st.session_state[k_files])
                
                # Upload dans la modif
                up_mod = st.file_uploader("Ajouter fichier", key="up_mod_client")
                if up_mod:
                    if st.form_submit_button("Générer lien (Ajout)"):
                         l = handle_upload(up_mod)
                         if l: 
                             st.session_state[k_files] += f"\n{l}"
                             st.rerun()

                if st.form_submit_button("Sauvegarder Infos Client"):
                    # Indices: 3=Addr, 4=Ville, 5=CP, 6=Tel, 7=Email, 8=Equip, 10=Fichiers
                    r = sheet.find(infos['nom']).row
                    sheet.update_cell(r, 3, n_addr)
                    sheet.update_cell(r, 4, n_ville)
                    sheet.update_cell(r, 5, n_cp)
                    sheet.update_cell(r, 6, n_tel)
                    sheet.update_cell(r, 7, n_mail)
                    sheet.update_cell(r, 8, n_eq)
                    sheet.update_cell(r, 10, n_files)
                    st.success("Infos mises à jour !")
                    st.cache_resource.clear()
                    st.rerun()

            st.markdown("---")
            st.subheader("Modifier une Intervention")
            hist = infos['historique']
            if hist:
                opts = [f"{h['date']} - {h['type']}" for h in hist]
                sel_int = st.selectbox("Choisir l'intervention", opts)
                idx = opts.index(sel_int)
                h_item = hist[idx]
                
                with st.form(f"mod_int_{idx}"):
                    d_obj = datetime.strptime(h_item['date'], '%Y-%m-%d').date()
                    nd = st.date_input("Date", d_obj)
                    np = st.number_input("Prix", value=h_item['prix'])
                    ntype = st.selectbox("Type", ["Entretien annuel", "Dépannage", "Installation", "Autre"], index=0) # Simplifié
                    ndesc = st.text_area("Desc", h_item['desc'])
                    
                    # Fichiers inter
                    k_fi = f"fi_mod_{client_sel}_{idx}"
                    if k_fi not in st.session_state: st.session_state[k_fi] = h_item.get('fichiers_inter', '')
                    nfi = st.text_area("Liens Fichiers Inter", st.session_state[k_fi])

                    if st.form_submit_button("Sauvegarder Intervention"):
                        hist[idx]['date'] = str(nd)
                        hist[idx]['prix'] = np
                        hist[idx]['type'] = ntype
                        hist[idx]['desc'] = ndesc
                        hist[idx]['fichiers_inter'] = nfi
                        
                        sheet.update_cell(sheet.find(infos['nom']).row, 9, json.dumps(hist, ensure_ascii=False))
                        st.success("Intervention mise à jour !")
                        st.cache_resource.clear()
                        st.rerun()
            else:
                st.write("Pas d'historique.")


# --- PAGE: SUPPRESSION ---
elif menu == "🗑️ Supprimer Client/Intervention":
    st.header("Zone de Suppression")
    if db:
        del_client = st.selectbox("Client à supprimer", sorted(db.keys()), key="del_c")
        
        st.subheader("Supprimer le client entier")
        if st.button("SUPPRIMER LE CLIENT"):
            if supprimer_client_sheet(sheet, db[del_client]['nom']):
                st.rerun()
        
        st.markdown("---")
        st.subheader("Supprimer une intervention seulement")
        h_del = db[del_client]['historique']
        if h_del:
            opts_del = [f"{h['date']} - {h['type']}" for h in h_del]
            sel_int_del = st.selectbox("Intervention", opts_del)
            
            if st.button("Supprimer l'intervention"):
                idx_del = opts_del.index(sel_int_del)
                del h_del[idx_del]
                # Save
                sheet.update_cell(sheet.find(db[del_client]['nom']).row, 9, json.dumps(h_del, ensure_ascii=False))
                st.success("Intervention supprimée.")
                st.cache_resource.clear()
                st.rerun()
        else:
            st.write("Rien à supprimer.")
