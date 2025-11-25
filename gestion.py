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
APP_TITLE = "🔥 SEBApp le chauffagiste connecté"

# --- URLs des images (Non utilisées) ---
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

# --- UPLOAD (SIMULATION) ---
def handle_upload(uploaded_file):
    if uploaded_file is not None:
        placeholder_link = f"https://placeholder.cloud.storage/documents/{int(time.time())}/{uploaded_file.name.replace(' ', '_')}"
        st.toast(f"Fichier téléversé : {uploaded_file.name}. Lien généré.", icon="✅")
        return placeholder_link
    return None

# --- CHARGEMENT DONNÉES ---
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

# --- FONCTION AJOUT CLIENT (AVEC VIDAGE AUTOMATIQUE) ---
def ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, tel, email, equipement, fichiers_client):
    # Basé sur votre fichier : Fichiers en col 9, Historique en col 10
    nouvelle_ligne = [nom, prenom, adresse, ville, code_postal, tel, email, equipement, fichiers_client, "[]"]
    sheet.append_row(nouvelle_ligne)
    
    # 1. Message de succès
    st.session_state['success_message'] = f"✅ Client **{nom} {prenom}** ajouté avec succès !"

    # 2. VIDAGE AUTOMATIQUE DES CHAMPS
    # On remet à vide toutes les clés utilisées dans le formulaire "Nouveau Client"
    keys_to_clear = ['new_nom', 'new_prenom', 'new_adresse', 'new_ville', 'new_cp', 'new_tel', 'new_email', 'new_equip', 'text_client_add']
    for key in keys_to_clear:
        if key in st.session_state:
            st.session_state[key] = ""
    
    st.cache_resource.clear()
    st.rerun()

# --- FONCTION UPDATE CHAMP UNIQUE ---
def update_client_field(sheet, nom_client_principal, col_index, new_value):
    try:
        cellule = sheet.find(nom_client_principal) 
        sheet.update_cell(cellule.row, col_index, new_value)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du champ (col {col_index}) : {e}")
        return False
        
# --- FONCTION AJOUT INTERVENTION (AVEC VIDAGE AUTOMATIQUE) ---
def ajouter_inter_sheet(sheet, nom_client_cle, db, nouvelle_inter):
    historique = db[nom_client_cle]['historique']
    historique.append(nouvelle_inter)
    historique_txt = json.dumps(historique, ensure_ascii=False)
    
    nom = db[nom_client_cle]['nom']
    
    try:
        cellule = sheet.find(nom)
        # Basé sur votre fichier : Historique est en col 10 (J) ? 
        # Votre fichier original avait "Fichiers" en 9 et "Historique" en 10 dans 'nouvelle_ligne'.
        # Donc update_cell doit cibler la colonne 10 pour l'historique.
        sheet.update_cell(cellule.row, 10, historique_txt) 
        
        # 1. Message de succès
        st.session_state['success_message'] = f"✅ Intervention ajoutée pour **{nom}** !"

        # 2. VIDAGE AUTOMATIQUE DES CHAMPS
        st.session_state['new_inter_desc'] = ""
        st.session_state['new_inter_type_spec'] = ""
        st.session_state['text_inter_add'] = ""
        st.session_state['new_inter_prix'] = 0.0
        st.session_state['new_inter_techs'] = []
        st.session_state['new_inter_date'] = datetime.now()
        # On ne vide pas le sélecteur de client ou de type pour éviter des erreurs, ou on les laisse tels quels.

    except:
        st.error("Impossible de retrouver la ligne du client pour la mise à jour de l'historique.")
        
    st.cache_resource.clear()
    st.rerun()

# --- FONCTION SUPPRESSION ---
def supprimer_client_sheet(sheet, nom_client):
    try:
        cellule = sheet.find(nom_client)
        ligne_a_supprimer = cellule.row
        if ligne_a_supprimer > 1: 
            sheet.delete_rows(ligne_a_supprimer)
            st.session_state['success_message'] = f"🗑️ Client **{nom_client}** supprimé."
            return True
        else:
            st.error("Tentative de suppression de l'en-tête ou ligne non trouvée.")
            return False
    except Exception as e:
        st.error(f"Erreur lors de la suppression du client : {e}")
        return False

# --- INTERFACE ---

sheet = connexion_google_sheet()

menu = st.sidebar.radio(
    "Menu", 
    ("🔍 Rechercher", "➕ Nouveau Client", "🛠️ Nouvelle Intervention", "✍️ Mettre à jour (Modifier)", "🗑️ Supprimer Client/Intervention"),
    index=0 
)

db = charger_donnees(sheet)

st.title(APP_TITLE)
st.markdown("---")

# --- ZONE D'AFFICHAGE DU MESSAGE DE CONFIRMATION ---
if 'success_message' in st.session_state:
    st.success(st.session_state['success_message'])
    del st.session_state['success_message']

# ------------------------------------------------------------------

if menu == "🔍 Rechercher":
    st.header("Recherche de Clients Multi-critères")
    recherche = st.text_input("Entrez un terme (Nom, Prénom, Adresse, Ville, CP, Équipement...) :")
    
    resultats = []
    if recherche:
        search_term = recherche.lower()
        search_term = re.sub(r'[^a-z0-9\s]', '', search_term).strip()
        if search_term:
            for nom_complet, client_data in db.items():
                if search_term in client_data['recherche_index']:
                    resultats.append(nom_complet)
    else:
        resultats = sorted(db.keys())

    if resultats:
        st.subheader(f"Résultats ({len(resultats)})")
        selection = st.selectbox("Sélectionnez le client pour voir les détails", sorted(resultats))
        
        if selection:
            infos = db[selection]
            st.subheader(f"Informations de {infos['nom']} {infos['prenom']}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**📞 Téléphone :** {infos['telephone'] or 'N/A'}")
            with c2:
                st.markdown(f"**📧 Email :** {infos['email'] or 'N/A'}")
                
            st.markdown(f"**🏠 Adresse :** {infos['adresse'] or 'N/A'}, {infos['code_postal'] or 'N/A'} {infos['ville'] or 'N/A'}")
            st.markdown(f"**🔧 Équipement :** {infos['equipement'] or 'N/A'}")
            
            fichiers_client_str = infos.get('fichiers_client', 'N/A')
            st.markdown("---")
            st.markdown("**📂 Liens Fichiers Client :**")
            if fichiers_client_str and fichiers_client_str != 'N/A':
                links = re.split(r'[,\n]', fichiers_client_str)
                for link in [l.strip() for l in links if l.strip()]:
                    if link.startswith('http'):
                        st.markdown(f"- [Ouvrir le document]({link})")
                    else:
                         st.markdown(f"- {link} (Lien invalide ou incomplet)")
            else:
                st.write("Aucun fichier client joint.")
            st.markdown("---")
            
            st.subheader("Historique des Interventions")
            if infos['historique']:
                for h in sorted(infos['historique'], key=lambda x: x['date'], reverse=True):
                    techniciens_str = ", ".join(h.get('techniciens', ['N/A']))
                    type_str = h.get('type', 'N/A')
                    st.info(f"**{type_str}** par **{techniciens_str}** le 📅 **{h['date']}** : {h['desc']} ({h['prix']}€)")
                    
                    fichiers_inter_str = h.get('fichiers_inter', '')
                    if fichiers_inter_str:
                         st.markdown("**🔗 Pièces jointes :**")
                         links = re.split(r'[,\n]', fichiers_inter_str)
                         for link in [l.strip() for l in links if l.strip()]:
                            if link.startswith('http'):
                                st.markdown(f"  - [Ouvrir le fichier]({link})")
                            else:
                                st.markdown(f"  - {link} (Lien invalide ou incomplet)")
            else:
                st.write("Aucune intervention enregistrée pour ce client.")
    else:
        st.warning("Aucun client trouvé correspondant à la recherche.")


elif menu == "➕ Nouveau Client":
    st.header("Nouveau Client")
    with st.form("form_nouveau"):
        col1, col2 = st.columns(2)
        
        # AJOUT DES CLÉS (key) pour permettre le vidage
        with col1:
            nom = st.text_input("Nom", key="new_nom")
            adresse = st.text_input("Adresse", key="new_adresse")
            code_postal = st.text_input("Code Postal", key="new_cp")
            telephone = st.text_input("Téléphone", key="new_tel")
            
        with col2:
            prenom = st.text_input("Prénom", key="new_prenom")
            ville = st.text_input("Ville", key="new_ville")
            email = st.text_input("Email", key="new_email")
            equipement = st.text_input("Équipement (Chaudière, PAC, etc.)", key="new_equip")
        
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
            if st.form_submit_button("Générer lien fichier (Cliquer avant d'enregistrer)"):
                new_link = handle_upload(uploaded_file_client)
                if new_link:
                    st.session_state.text_client_add += f"\n{new_link}"
                    st.rerun() 
            
        valider = st.form_submit_button("Enregistrer le client")
        
        if valider and nom and prenom: 
            final_fichiers_client = st.session_state.get('text_client_add', '') 
            nom_complet = f"{nom} {prenom}".strip()
            
            if nom_complet in db:
                st.warning(f"Le client {nom_complet} existe déjà dans la base.")
            else:
                ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, telephone, email, equipement, final_fichiers_client)


elif menu == "🛠️ Nouvelle Intervention":
    st.header("Nouvelle Intervention")
    if db:
        choix = st.selectbox("Client", sorted(db.keys()), key="new_inter_client")
        
        col_type, col_tech = st.columns(2)
        with col_type:
            type_inter = st.selectbox(
                "Type d'intervention",
                ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique", "Autre"],
                index=0,
                key="new_inter_type"
            )

        with col_tech:
            techniciens = st.multiselect(
                "Technicien(s) assigné(s)",
                ["Seb", "Colin"],
                default=[],
                key="new_inter_techs"
            )
            
        type_a_enregistrer = type_inter
        if type_inter == "Autre":
            # Champ avec clé pour le vidage
            type_specifique = st.text_input("Spécifiez le type d'intervention (ex: Ramonage)", key="new_inter_type_spec")
            type_a_enregistrer = type_specifique
        
        # Champs avec clés pour le vidage
        date = st.date_input("Date", datetime.now(), key="new_inter_date")
        desc = st.text_area("Description de l'intervention", key="new_inter_desc")
        prix = st.number_input("Prix (en €)", step=10.0, key="new_inter_prix")
        
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
            if st.button("Générer lien fichier (Cliquer avant d'enregistrer)"): 
                new_link = handle_upload(uploaded_file_inter)
                if new_link:
                    st.session_state.text_inter_add += f"\n{new_link}"
                    st.rerun() 

        
        if st.button("Valider l'intervention"):
            if type_inter == "Autre" and not type_a_enregistrer.strip():
                 st.warning("Veuillez spécifier le type d'intervention 'Autre'.")
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
                ajouter_inter_sheet(sheet, choix, db, inter)
    else:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")


elif menu == "✍️ Mettre à jour (Modifier)":
    st.header("Mettre à jour les informations Client et Interventions")
    if not db:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")
    else:
        client_selectionne = st.selectbox("Sélectionnez le client à modifier", sorted(db.keys()), key="select_modif_client")
        
        if client_selectionne:
            infos_actuelles = db[client_selectionne]
            
            st.subheader(f"1. Informations Générales de {client_selectionne}")
            
            with st.form("form_update_client_general"): 
                col1_up, col2_up = st.columns(2)
                
                with col1_up:
                    st.text_input("Nom (Clé)", value=infos_actuelles['nom'], disabled=True)
                    nouvelle_adresse = st.text_input("Adresse", value=infos_actuelles['adresse'], key="addr_upd")
                    nouveau_code_postal = st.text_input("Code Postal", value=infos_actuelles['code_postal'], key="cp_upd")
                    nouveau_telephone = st.text_input("Téléphone", value=infos_actuelles['telephone'], key="tel_upd")
                    
                with col2_up:
                    st.text_input("Prénom (Clé)", value=infos_actuelles['prenom'], disabled=True)
                    nouvelle_ville = st.text_input("Ville", value=infos_actuelles['ville'], key="ville_upd")
                    nouvel_email = st.text_input("Email", value=infos_actuelles['email'], key="email_upd")
                    nouvel_equipement = st.text_input("Équipement", value=infos_actuelles['equipement'], key="eq_upd")
                
                st.markdown("---")
                st.subheader("Fichiers Client")
                
                uploaded_file_client_update = st.file_uploader(
                    "Téléverser un nouveau document client (max 5 Mo)", 
                    key="file_client_update_general",
                    accept_multiple_files=False,
                    type=['pdf', 'jpg', 'jpeg', 'png']
                )

                key_client_files = f'text_client_update_{client_selectionne}_general'
                if key_client_files not in st.session_state:
                     st.session_state[key_client_files] = infos_actuelles.get('fichiers_client', '')

                nouveaux_fichiers_client = st.text_area(
                    "Liens Fichiers Client (Modifiez ici ou ajoutez après téléversement)", 
                    value=st.session_state[key_client_files],
                    height=100,
                    key=key_client_files
                )
                
                if uploaded_file_client_update:
                    if st.form_submit_button("Générer lien fichier (Modif)"):
                        new_link = handle_upload(uploaded_file_client_update)
                        if new_link:
                            st.session_state[key_client_files] += f"\n{new_link}"
                            st.rerun() 
                
                update_valider = st.form_submit_button("Sauvegarder les modifications Client")
                
                if update_valider:
                    final_fichiers_client = st.session_state.get(key_client_files, '')
                    try:
                        cellule = sheet.find(infos_actuelles['nom'])
                        ligne_a_modifier = cellule.row
                        # Indices basés sur votre fichier
                        sheet.update_cell(ligne_a_modifier, 3, nouvelle_adresse)  
                        sheet.update_cell(ligne_a_modifier, 4, nouvelle_ville)    
                        sheet.update_cell(ligne_a_modifier, 5, nouveau_code_postal) 
                        sheet.update_cell(ligne_a_modifier, 6, nouveau_telephone)  
                        sheet.update_cell(ligne_a_modifier, 7, nouvel_email)     
                        sheet.update_cell(ligne_a_modifier, 8, nouvel_equipement)
                        sheet.update_cell(ligne_a_modifier, 9, final_fichiers_client) 
                        st.success(f"Informations mises à jour !")
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur : {e}")
                        
            st.markdown("---")
            
            st.subheader("2. Modification des Interventions Passées")
            historique = infos_actuelles.get('historique', [])
            
            if not historique:
                st.info("Ce client n'a pas encore d'intervention enregistrée.")
            else:
                options_interventions = [f"[{h['date']}] {h.get('type', 'Intervention')} - {h.get('desc', '')[:40]}..." for h in historique]
                inter_selectionnee_titre = st.selectbox("Sélectionnez l'intervention à modifier", options_interventions)
                inter_index = options_interventions.index(inter_selectionnee_titre)
                inter_a_modifier = historique[inter_index]
                
                with st.form(f"form_modifier_inter_{inter_index}"):
                    col_edit_date, col_edit_prix = st.columns(2)
                    with col_edit_date:
                        date_obj = datetime.strptime(inter_a_modifier['date'], '%Y-%m-%d').date()
                        nouvelle_date = st.date_input("Date", value=date_obj, key=f"date_{inter_index}_mod")
                    with col_edit_prix:
                        nouveau_prix = st.number_input("Prix (€)", value=inter_a_modifier['prix'], step=10, key=f"prix_{inter_index}_mod")

                    col_edit_type, col_edit_tech = st.columns(2)
                    with col_edit_type:
                        standard_types = ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique"]
                        current_type = inter_a_modifier.get('type', "Entretien annuel")
                        idx_type = standard_types.index(current_type) if current_type in standard_types else 0
                        nouveau_type = st.selectbox("Type", standard_types + ["Autre"], index=idx_type, key=f"type_{inter_index}_mod")
                    
                    with col_edit_tech:
                        nouveaux_techniciens = st.multiselect("Technicien(s)", ["Seb", "Colin"], default=inter_a_modifier.get('techniciens', []), key=f"tech_{inter_index}_mod")

                    nouvelle_desc = st.text_area("Description", value=inter_a_modifier['desc'], key=f"desc_{inter_index}_mod")
                    
                    st.markdown("---")
                    uploaded_file_inter_update = st.file_uploader("Nouveau document intervention", key=f"file_inter_update_{inter_index}_mod")
                    
                    key_inter_files = f'text_inter_update_{inter_index}_mod'
                    if key_inter_files not in st.session_state:
                        st.session_state[key_inter_files] = inter_a_modifier.get('fichiers_inter', '')

                    nouveaux_fichiers_inter = st.text_area("Liens Fichiers", value=st.session_state[key_inter_files], height=80, key=key_inter_files)
                    
                    if uploaded_file_inter_update:
                        if st.form_submit_button("Générer lien (Modif Inter)"):
                            new_link = handle_upload(uploaded_file_inter_update)
                            if new_link:
                                st.session_state[key_inter_files] += f"\n{new_link}"
                                st.rerun() 

                    if st.form_submit_button("Sauvegarder l'intervention modifiée"):
                        final_fichiers_inter = st.session_state.get(key_inter_files, '')
                        historique[inter_index] = {
                            "date": str(nouvelle_date),
                            "type": nouveau_type,
                            "techniciens": nouveaux_techniciens,
                            "desc": nouvelle_desc,
                            "prix": nouveau_prix,
                            "fichiers_inter": final_fichiers_inter
                        }
                        historique_txt = json.dumps(historique, ensure_ascii=False)
                        if update_client_field(sheet, infos_actuelles['nom'], 10, historique_txt): # Historique en 10
                            st.success(f"Intervention mise à jour.")
                            st.cache_resource.clear()
                            st.rerun()

elif menu == "🗑️ Supprimer Client/Intervention":
    st.header("🗑️ Suppression Définitive")
    if not db:
        st.info("La base est vide.")
    else:
        st.markdown("---")
        st.subheader("1. Supprimer un Client")
        if 'suppression_confirmee_client' not in st.session_state: st.session_state.suppression_confirmee_client = False
        client_del = st.selectbox("Client à SUPPRIMER", sorted(db.keys()), key="select_del_client")
        
        if st.button(f"Initier suppression de {client_del}", type="secondary"):
            st.session_state.suppression_confirmee_client = True
                
        if st.session_state.suppression_confirmee_client:
            st.warning(f"Confirmer la suppression de {client_del} ?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("OUI, SUPPRIMER", type="primary"):
                    if supprimer_client_sheet(sheet, db[client_del]['nom']):
                        st.session_state.suppression_confirmee_client = False
                        st.cache_resource.clear()
                        st.rerun()
            with c2:
                if st.button("Annuler"):
                    st.session_state.suppression_confirmee_client = False
                    st.rerun()
                        
        st.markdown("---")
        st.subheader("2. Supprimer une Intervention")
        client_inter_del = st.selectbox("Client concerné", sorted(db.keys()), key="select_del_inter")
        hist_del = db[client_inter_del].get('historique', [])
        
        if not hist_del:
            st.info("Pas d'historique.")
        else:
            opts_del = [f"[{h['date']}] {h.get('type', 'Intervention')} - {h.get('desc', '')[:50]}..." for h in hist_del]
            inter_titre = st.selectbox("Intervention à supprimer", opts_del)
            idx_del = opts_del.index(inter_titre)
            
            if st.button(f"SUPPRIMER l'intervention", type="primary"):
                del hist_del[idx_del]
                historique_txt_del = json.dumps(hist_del, ensure_ascii=False)
                if update_client_field(sheet, db[client_inter_del]['nom'], 10, historique_txt_del): # Historique en 10
                    st.success("Intervention supprimée.")
                    st.cache_resource.clear()
                    st.rerun()
