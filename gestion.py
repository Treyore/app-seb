import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import re # Importation du module re pour les expressions régulières/nettoyage
import time

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Gestion Chauffagiste", page_icon="🔥", layout="wide")

# --- CONSTANTES ---
# NOUVEAU TITRE de l'application
APP_TITLE = "🔥 SEBApp le chauffagiste connectée"

# --- URLs des images pour la page d'accueil (Non utilisées, mais conservées dans le code) ---
IMAGE_URL_1 = "https://raw.githubusercontent.com/Treyore/app-seb/c81b77576a13beee81e9d69f3f06f95842a34bb5/WhatsApp%20Image%202025-11-24%20at%2016.08.53.jpeg"
IMAGE_URL_2 = "https://raw.githubusercontent.com/Treyore/app-seb/92e1af7d7313f8df3cbc3ec186b5228764c23ba7/seb%20lunettes%20soleil.webp"


# --- CONNEXION GOOGLE SHEETS (Compatible PC et Cloud) ---
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
            # Assurez-vous d'avoir votre fichier 'secrets.json' dans le répertoire
            creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
            
        client = gspread.authorize(creds)
        # Ouvre la feuille (assurez-vous que le nom correspond à votre feuille)
        sheet = client.open("Base Clients Chauffage").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        st.stop()

# --- NOUVELLE FONCTION POUR GÉRER L'UPLOAD DE FICHIER ---
# ATTENTION : Ceci est une implémentation SIMPLIFIÉE. 
# En production, vous devez enregistrer le fichier sur un stockage permanent (Google Drive, S3, etc.)
def handle_upload(uploaded_file):
    """
    Simule le téléversement d'un fichier et retourne un lien d'accès.
    EN PRODUCTION : Remplacez ceci par l'API d'un service de stockage Cloud.
    """
    if uploaded_file is not None:
        # Simule le processus de stockage et génère un lien de placeholder
        placeholder_link = f"https://placeholder.cloud.storage/documents/{int(time.time())}/{uploaded_file.name.replace(' ', '_')}"
        st.toast(f"Fichier téléversé : {uploaded_file.name}. Lien généré.", icon="✅")
        return placeholder_link
    return None

# --- FONCTIONS EXISTANTES ---

# Charger les données sans cache Streamlit pour éviter les problèmes d'hachage avec gspread
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
            
            # Stockage de TOUS les champs (AJOUT du champ fichiers_client)
            client_data = {
                "nom": ligne.get('Nom', ''),
                "prenom": ligne.get('Prenom', ''),
                "adresse": ligne.get('Adresse', ''),
                "ville": ligne.get('Ville', ''),
                "code_postal": ligne.get('Code_Postal', ''),
                "telephone": ligne.get('Telephone', ''),
                "email": ligne.get('Email', ''),
                "equipement": ligne.get('Equipement', ''),
                "fichiers_client": ligne.get('Fichiers_Client', ''), # NOUVEAU : Doit exister dans l'en-tête de votre Google Sheet
                "historique": historique
            }

            # Créer un index de recherche pour tous les champs pertinents
            index_fields = [
                client_data["nom"], client_data["prenom"], client_data["adresse"],
                client_data["ville"], client_data["code_postal"], client_data["telephone"],
                client_data["email"], client_data["equipement"], client_data["fichiers_client"]
            ]
            
            # Concaténation des champs, conversion en minuscules et nettoyage
            search_index = " ".join(str(f) for f in index_fields if f).lower()
            # Nettoyer l'index (enlever les caractères spéciaux qui ne facilitent pas la recherche)
            search_index = re.sub(r'[^a-z0-9\s]', '', search_index)
            client_data["recherche_index"] = search_index
            
            db[nom_complet] = client_data
            
            # Stocker aussi le nom complet (clé d'accès au dictionnaire) pour l'utiliser dans les fonctions de mise à jour
            client_data["nom_complet"] = nom_complet 
            
    return db

def ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, tel, email, equipement, fichiers_client):
    # L'ordre DOIT correspond à l'ordre de vos colonnes dans Google Sheet !
    # Colonne I (9) = Historique, Colonne J (10) = Fichiers_Client
    nouvelle_ligne = [
        nom, prenom, adresse, ville, code_postal, tel, email, equipement, 
        "[]", # Historique (Colonne 9 / I)
        fichiers_client # Fichiers_Client (Colonne 10 / J)
    ]
    sheet.append_row(nouvelle_ligne)
    # Après ajout, invalider le cache de la feuille pour que les données soient rechargées
    st.cache_resource.clear()
    st.rerun()

# Fonction générique pour mettre à jour un champ unique dans la ligne d'un client
def update_client_field(sheet, nom_client_principal, col_index, new_value):
    try:
        # On cherche le client par son Nom (colonne 1)
        cellule = sheet.find(nom_client_principal) 
        sheet.update_cell(cellule.row, col_index, new_value)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du champ (col {col_index}) : {e}")
        return False
        
def ajouter_inter_sheet(sheet, nom_client_cle, db, nouvelle_inter):
    historique = db[nom_client_cle]['historique']
    historique.append(nouvelle_inter)
    historique_txt = json.dumps(historique, ensure_ascii=False)
    
    nom = db[nom_client_cle]['nom']
    
    try:
        # On cherche le client par son Nom (colonne 1)
        cellule = sheet.find(nom)
        # Historique est en COLONNE 9 (I)
        sheet.update_cell(cellule.row, 9, historique_txt) 
    except:
        st.error("Impossible de retrouver la ligne du client pour la mise à jour de l'historique.")
        
    # Après ajout, invalider le cache de la feuille pour que les données soient rechargées
    st.cache_resource.clear()
    st.rerun()

# FONCTION POUR SUPPRIMER UN CLIENT
def supprimer_client_sheet(sheet, nom_client):
    """Supprime la ligne du client dans Google Sheets en se basant sur le Nom."""
    try:
        # 1. Trouver la cellule contenant le Nom du client
        cellule = sheet.find(nom_client)
        ligne_a_supprimer = cellule.row
        
        # 2. Supprimer la ligne (l'index de ligne est basé sur 1)
        if ligne_a_supprimer > 1: # S'assurer qu'on ne supprime pas l'en-tête
            sheet.delete_rows(ligne_a_supprimer)
            return True
        else:
            st.error("Tentative de suppression de l'en-tête ou ligne non trouvée.")
            return False
            
    except Exception as e:
        st.error(f"Erreur lors de la suppression du client : Impossible de trouver la ligne du client. {e}")
        return False

# --- INTERFACE GRAPHIQUE ---

# 1. Connexion (doit être en dehors de la boucle du menu)
sheet = connexion_google_sheet()

# ------------------------------------------------------------------
# --- DÉMARRAGE DIRECT DE L'APPLICATION PRINCIPALE ---
# ------------------------------------------------------------------

# 2. Menu (maintenant visible dans la sidebar)
menu = st.sidebar.radio(
    "Menu", 
    (
        "🔍 Rechercher", # Page par défaut (index=0)
        "➕ Nouveau Client", 
        "🛠️ Nouvelle Intervention", 
        "✍️ Mettre à jour (Modifier)",
        "🗑️ Supprimer Client/Intervention"
    ),
    # Index par défaut est 0, ce qui correspond à "🔍 Rechercher"
    index=0 
)

# 3. Chargement des données (Doit toujours charger les données)
db = charger_donnees(sheet)

st.title(APP_TITLE)
st.markdown("---")

# ------------------------------------------------------------------
# --- LOGIQUE D'AFFICHAGE SELON LE MENU ---
# ------------------------------------------------------------------

# --- RECHERCHE (Page par défaut) ---
if menu == "🔍 Rechercher":
    st.header("Recherche de Clients Multi-critères")
    recherche = st.text_input("Entrez un terme (Nom, Prénom, Adresse, Ville, CP, Équipement...) :")
    
    # -----------------------------------------------------
    # LOGIQUE DE FILTRAGE
    # -----------------------------------------------------
    resultats = []
    if recherche:
        search_term = recherche.lower()
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
            
            # AFFICHAGE des FICHIERS CLIENT
            fichiers_client_str = infos.get('fichiers_client', 'N/A')
            st.markdown("---")
            st.markdown("**📂 Liens Fichiers Client :**")
            if fichiers_client_str and fichiers_client_str != 'N/A':
                # Afficher les liens sous forme de liste cliquable
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
                # Afficher la dernière intervention en haut
                for h in sorted(infos['historique'], key=lambda x: x['date'], reverse=True): # Trie par date
                    techniciens_str = ", ".join(h.get('techniciens', ['N/A']))
                    type_str = h.get('type', 'N/A')
                    
                    st.info(
                        f"**{type_str}** par **{techniciens_str}** le 📅 **{h['date']}** : "
                        f"{h['desc']} ({h['prix']}€)"
                    )
                    
                    # AFFICHAGE des FICHIERS INTERVENTION
                    fichiers_inter_str = h.get('fichiers_inter', '')
                    if fichiers_inter_str:
                         st.markdown("**🔗 Pièces jointes :**")
                         # Afficher les liens sous forme de liste cliquable
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
        # Organisation en colonnes
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
        
        st.markdown("---")
        st.subheader("Fichiers Client")
        
        # NOUVEAU: Champ de téléversement pour le client
        uploaded_file_client = st.file_uploader(
            "Téléverser un document client (max 5 Mo)", 
            key="file_client_add",
            accept_multiple_files=False,
            type=['pdf', 'jpg', 'jpeg', 'png']
        )
        
        # Champ texte pour les liens (mis à jour après upload)
        fichiers_client = st.text_area(
            "Liens Fichiers Client (Liens existants, ou liens générés après téléversement)", 
            height=100,
            key="text_client_add",
            value="" # Assurez-vous que la valeur initiale est vide
        )
        
        # Logique de gestion de l'upload pour le client (doit être lié à un bouton ou à un événement)
        if uploaded_file_client:
            # S'il y a un fichier uploadé, traiter l'upload
            if st.button("Ajouter le document téléversé aux liens client", key="btn_upload_client_add"): # Clé unique
                new_link = handle_upload(uploaded_file_client)
                if new_link:
                    # Ajouter le nouveau lien au champ texte existant
                    current_links = st.session_state.text_client_add.strip()
                    if current_links:
                        st.session_state.text_client_add = current_links + f"\n{new_link}"
                    else:
                        st.session_state.text_client_add = new_link
                    
                    # Force le champ à se mettre à jour visuellement
                    # Le champ "fichiers_client" dans le formulaire utilise st.session_state.text_client_add comme key.
                    # Il se mettra à jour lors du rerun.
                    st.rerun() 
            
        valider = st.form_submit_button("Enregistrer le client")
        
        if valider and nom and prenom: # Exiger au moins Nom et Prénom
            # Utiliser la valeur finale du champ de liens
            final_fichiers_client = st.session_state.get('text_client_add', '') # Utiliser get() avec une valeur par défaut

            nom_complet = f"{nom} {prenom}".strip()
            if nom_complet in db:
                st.warning(f"Le client {nom_complet} existe déjà dans la base.")
            else:
                ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, telephone, email, equipement, final_fichiers_client)
                st.success(f"Client {nom_complet} ajouté !")
                # Nettoyer l'état de session après l'ajout
                if 'text_client_add' in st.session_state: del st.session_state.text_client_add


elif menu == "🛠️ Nouvelle Intervention":
    st.header("Nouvelle Intervention")
    if db:
        # Triage de la liste des clients pour le selectbox
        choix = st.selectbox("Client", sorted(db.keys()))
        
        # CHAMPS
        col_type, col_tech = st.columns(2)
        
        with col_type:
            # MODIFICATION : Ajout de l'option "Autre"
            type_inter = st.selectbox(
                "Type d'intervention",
                ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique", "Autre"],
                index=0
            )

        with col_tech:
            techniciens = st.multiselect(
                "Technicien(s) assigné(s)",
                ["Seb", "Colin"],
                default=[]
            )
            
        # NOUVEAU : Champ de spécification si "Autre" est sélectionné
        type_a_enregistrer = type_inter
        if type_inter == "Autre":
            type_specifique = st.text_input("Spécifiez le type d'intervention (ex: Ramonage)", key="new_inter_type_specifique")
            type_a_enregistrer = type_specifique # C'est cette valeur qui sera enregistrée
        
        date = st.date_input("Date", datetime.now())
        desc = st.text_area("Description de l'intervention")
        prix = st.number_input("Prix (en €)", step=10)
        
        st.markdown("---")
        st.subheader("Fichiers Intervention")
        
        # NOUVEAU: Champ de téléversement pour l'intervention
        uploaded_file_inter = st.file_uploader(
            "Téléverser un document d'intervention (max 5 Mo)", 
            key="file_inter_add",
            accept_multiple_files=False,
            type=['pdf', 'jpg', 'jpeg', 'png']
        )

        # CHAMP FICHIER INTERVENTION
        fichiers_inter = st.text_area(
            "Liens Fichiers Intervention (Facture, Photo des travaux, etc.)", 
            height=80,
            key="text_inter_add",
            value="" # Assurez-vous que la valeur initiale est vide
        )
        
        # Logique de gestion de l'upload pour l'intervention
        if uploaded_file_inter:
            if st.button("Ajouter le document téléversé aux liens intervention", key="btn_upload_inter_add"): # Clé unique
                new_link = handle_upload(uploaded_file_inter)
                if new_link:
                    current_links = st.session_state.text_inter_add.strip()
                    if current_links:
                        st.session_state.text_inter_add = current_links + f"\n{new_link}"
                    else:
                        st.session_state.text_inter_add = new_link
                    
                    # Force le champ à se mettre à jour visuellement
                    st.rerun() 

        
        if st.button("Valider l'intervention"):
            # Vérification de la spécification si "Autre" est choisi
            if type_inter == "Autre" and not type_a_enregistrer.strip():
                 st.warning("Veuillez spécifier le type d'intervention 'Autre'.")
                 st.stop()
            elif not techniciens:
                st.warning("Veuillez assigner au moins un technicien à l'intervention.")
            else:
                # Utiliser la valeur finale du champ de liens
                final_fichiers_inter = st.session_state.get('text_inter_add', '') # Utiliser get() avec une valeur par défaut

                # MISE À JOUR : Ajout des nouvelles informations dans le dictionnaire
                inter = {
                    "date": str(date), 
                    "type": type_a_enregistrer, # Utilisation de la valeur spécifiée si "Autre"
                    "techniciens": techniciens,   
                    "desc": desc, 
                    "prix": prix,
                    "fichiers_inter": final_fichiers_inter # Nouveau champ
                }
                ajouter_inter_sheet(sheet, choix, db, inter)
                st.success("Intervention sauvegardée en ligne !")
                # Nettoyer l'état de session après l'ajout
                if 'text_inter_add' in st.session_state: del st.session_state.text_inter_add
    else:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")

# ------------------------------------------------------------------
# --- BLOC : MISE À JOUR (MODIFIER) ---
# ------------------------------------------------------------------
elif menu == "✍️ Mettre à jour (Modifier)":
    st.header("Mettre à jour les informations Client et Interventions")
    if not db:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")
    else:
        # Sélection du client
        client_selectionne = st.selectbox("Sélectionnez le client à modifier", sorted(db.keys()), key="select_modif_client")
        
        if client_selectionne:
            infos_actuelles = db[client_selectionne]
            
            # --- BLOC 1 : Modification des Informations Client ---
            st.subheader(f"1. Informations Générales de {client_selectionne}")
            
            # Utilisation de form_update_client_general pour éviter les conflits de clés
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
                
                # NOUVEAU: Champ de téléversement pour la modification client
                uploaded_file_client_update = st.file_uploader(
                    "Téléverser un nouveau document client (max 5 Mo)", 
                    key="file_client_update_general", # Clé générique pour ce menu
                    accept_multiple_files=False,
                    type=['pdf', 'jpg', 'jpeg', 'png']
                )

                # NOUVEAU CHAMP DE FICHIERS CLIENT
                # Utilisation d'une clé session pour la mise à jour dynamique
                key_client_files = f'text_client_update_{client_selectionne}_general'
                if key_client_files not in st.session_state:
                     st.session_state[key_client_files] = infos_actuelles.get('fichiers_client', '')

                nouveaux_fichiers_client = st.text_area(
                    "Liens Fichiers Client (Modifiez ici ou ajoutez après téléversement)", 
                    value=st.session_state[key_client_files],
                    height=100,
                    key=key_client_files # Clé dynamique
                )
                
                # Logique de gestion de l'upload pour la modification client
                if uploaded_file_client_update:
                    if st.button("Ajouter le document téléversé aux liens client (Modif)", key="btn_upload_client_update_general"):
                        new_link = handle_upload(uploaded_file_client_update)
                        if new_link:
                            current_links = st.session_state[key_client_files].strip()
                            if current_links:
                                st.session_state[key_client_files] = current_links + f"\n{new_link}"
                            else:
                                st.session_state[key_client_files] = new_link
                            
                            st.rerun() 

                
                update_valider = st.form_submit_button("Sauvegarder les modifications Client")
                
                if update_valider:
                    final_fichiers_client = st.session_state.get(key_client_files, '')
                    
                    try:
                        # 1. On cherche la ligne du client (par son Nom)
                        cellule = sheet.find(infos_actuelles['nom'])
                        ligne_a_modifier = cellule.row
                        
                        # 2. On met à jour les champs (ATTENTION aux INDEX de COLONNES)
                        sheet.update_cell(ligne_a_modifier, 3, nouvelle_adresse)  
                        sheet.update_cell(ligne_a_modifier, 4, nouvelle_ville)    
                        sheet.update_cell(ligne_a_modifier, 5, nouveau_code_postal) 
                        sheet.update_cell(ligne_a_modifier, 6, nouveau_telephone)  
                        sheet.update_cell(ligne_a_modifier, 7, nouvel_email)     
                        sheet.update_cell(ligne_a_modifier, 8, nouvel_equipement)
                        # Fichiers Client est en COLONNE 10 (J)
                        sheet.update_cell(ligne_a_modifier, 10, final_fichiers_client) 
                        
                        st.success(f"Informations générales du client {client_selectionne} mises à jour !")
                        
                        st.cache_resource.clear()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Erreur lors de la mise à jour : Impossible de trouver la ligne du client. {e}")
                        
            st.markdown("---")
            
            # --- BLOC 2 : Modification des Interventions ---
            st.subheader("2. Modification des Interventions Passées")
            
            historique = infos_actuelles.get('historique', [])
            
            if not historique:
                st.info("Ce client n'a pas encore d'intervention enregistrée.")
            else:
                # Créer des clés pour l'édition
                options_interventions = [
                    f"[{h['date']}] {h.get('type', 'Intervention')} - {h.get('desc', '')[:40]}..." 
                    for h in historique
                ]
                
                inter_selectionnee_titre = st.selectbox(
                    "Sélectionnez l'intervention à modifier",
                    options_interventions
                )
                
                # Trouver l'index de l'intervention sélectionnée dans la liste historique
                inter_index = options_interventions.index(inter_selectionnee_titre)
                inter_a_modifier = historique[inter_index]
                
                # --- LOGIQUE POUR GÉRER L'OPTION "AUTRE" EXISTANTE ---
                standard_types = ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique"]
                all_options = standard_types + ["Autre"]

                stored_type = inter_a_modifier.get('type', 'Entretien annuel')
                is_standard = stored_type in standard_types
                
                # Détermine la valeur par défaut pour le selectbox et le champ texte custom
                default_selectbox_value = stored_type if is_standard else "Autre"
                custom_type_value = stored_type if not is_standard else "" # Si non standard, stocker la valeur comme type personnalisé
                
                # Calcule l'index par défaut dans la liste 'all_options'
                default_index = all_options.index(default_selectbox_value)
                
                with st.form(f"form_modifier_inter_{inter_index}"):
                    
                    col_edit_date, col_edit_prix = st.columns(2)
                    with col_edit_date:
                        date_obj = datetime.strptime(inter_a_modifier['date'], '%Y-%m-%d').date()
                        nouvelle_date = st.date_input("Date", value=date_obj, key=f"date_{inter_index}_mod")
                    
                    with col_edit_prix:
                        nouveau_prix = st.number_input("Prix (€)", value=inter_a_modifier['prix'], step=10, key=f"prix_{inter_index}_mod")

                    col_edit_type, col_edit_tech = st.columns(2)
                    with col_edit_type:
                        # MODIFICATION : Utilisation de la liste complète et de l'index par défaut calculé
                        nouveau_type = st.selectbox(
                            "Type d'intervention",
                            all_options,
                            index=default_index, 
                            key=f"type_{inter_index}_mod"
                        )
                    with col_edit_tech:
                        nouveaux_techniciens = st.multiselect(
                            "Technicien(s) assigné(s)",
                            ["Seb", "Colin"],
                            default=inter_a_modifier.get('techniciens', []),
                            key=f"tech_{inter_index}_mod"
                        )
                    
                    # NOUVEAU : Champ de spécification si "Autre" est sélectionné
                    type_specifique_mod = ""
                    if nouveau_type == "Autre":
                        type_specifique_mod = st.text_input(
                            "Spécifiez le type d'intervention", 
                            value=custom_type_value, # Pré-rempli avec l'ancien type si c'était "Autre"
                            key=f"type_specifique_{inter_index}_mod"
                        )

                    nouvelle_desc = st.text_area(
                        "Description de l'intervention", 
                        value=inter_a_modifier['desc'], 
                        key=f"desc_{inter_index}_mod"
                    )
                    
                    st.markdown("---")
                    st.subheader("Fichiers Intervention")
                    
                    uploaded_file_inter_update = st.file_uploader(
                        "Téléverser un nouveau document d'intervention (max 5 Mo)", 
                        key=f"file_inter_update_{inter_index}_mod",
                        accept_multiple_files=False,
                        type=['pdf', 'jpg', 'jpeg', 'png']
                    )
                    
                    # Clé de session dynamique pour les liens
                    key_inter_files = f'text_inter_update_{inter_index}_mod'
                    if key_inter_files not in st.session_state:
                        st.session_state[key_inter_files] = inter_a_modifier.get('fichiers_inter', '')

                    nouveaux_fichiers_inter = st.text_area(
                        "Liens Fichiers Intervention (Modifiez ici ou ajoutez après téléversement)", 
                        value=st.session_state[key_inter_files], 
                        height=80,
                        key=key_inter_files
                    )
                    
                    # Logique de gestion de l'upload pour la modification d'intervention
                    if uploaded_file_inter_update:
                        if st.button("Ajouter le document téléversé aux liens intervention (Modif)", key=f"btn_upload_inter_update_{inter_index}_mod"):
                            new_link = handle_upload(uploaded_file_inter_update)
                            if new_link:
                                current_links = st.session_state[key_inter_files].strip()
                                if current_links:
                                    st.session_state[key_inter_files] = current_links + f"\n{new_link}"
                                else:
                                    st.session_state[key_inter_files] = new_link
                                
                                st.rerun() 

                    sauvegarder_inter = st.form_submit_button("Sauvegarder l'intervention modifiée")
                    
                    if sauvegarder_inter:
                        
                        # Déterminer la valeur finale du type d'intervention
                        type_a_enregistrer = nouveau_type
                        if nouveau_type == "Autre":
                            if not type_specifique_mod.strip():
                                st.warning("Veuillez spécifier le type d'intervention 'Autre'.")
                                st.stop() # Stop execution if the field is empty
                            type_a_enregistrer = type_specifique_mod.strip()

                        # Utiliser la valeur finale du champ de liens
                        final_fichiers_inter = st.session_state.get(key_inter_files, '')

                        # Mettre à jour l'objet dans la liste historique
                        historique[inter_index] = {
                            "date": str(nouvelle_date),
                            "type": type_a_enregistrer, # Utilisation de la valeur finale
                            "techniciens": nouveaux_techniciens,
                            "desc": nouvelle_desc,
                            "prix": nouveau_prix,
                            "fichiers_inter": final_fichiers_inter
                        }
                        
                        # Convertir l'historique mis à jour en JSON
                        historique_txt = json.dumps(historique, ensure_ascii=False)
                        
                        # Enregistrer le nouvel historique dans Google Sheets (Colonne 9 / I)
                        if update_client_field(sheet, infos_actuelles['nom'], 9, historique_txt):
                            st.success(f"Intervention du {nouvelle_date} mise à jour avec succès.")
                            st.cache_resource.clear()
                            st.rerun()

# ------------------------------------------------------------------
# --- BLOC : SUPPRESSION ---
# ------------------------------------------------------------------
elif menu == "🗑️ Supprimer Client/Intervention":
    st.header("🗑️ Suppression Définitive")
    st.error("Cette zone permet de supprimer définitivement des clients ou des interventions de la base de données.")
    
    if not db:
        st.info("La base est vide. Aucune suppression possible.")
    else:
        # --- Suppression Client ---
        st.markdown("---")
        st.subheader("1. Supprimer un Client Définitivement")
        st.warning("⚠️ ATTENTION : Cette action supprime le client, ses informations et tout son historique d'interventions.")

        # Initialiser ou réinitialiser l'état de confirmation
        if 'suppression_confirmee_client' not in st.session_state:
            st.session_state.suppression_confirmee_client = False
            
        client_selectionne_del = st.selectbox("Sélectionnez le client à SUPPRIMER", sorted(db.keys()), key="select_del_client")
        
        if client_selectionne_del:
            infos_actuelles_del = db[client_selectionne_del]
            
            # Étape 1: Bouton pour initier la suppression
            if st.button(f"Initier la suppression de {client_selectionne_del}", key="btn_confirm_del_init", type="secondary"):
                st.session_state.suppression_confirmee_client = True
                
            # Étape 2: Afficher les boutons de confirmation après le premier clic
            if st.session_state.suppression_confirmee_client:
                st.info(f"Êtes-vous absolument sûr de vouloir SUPPRIMER DÉFINITIVEMENT {client_selectionne_del} ?")
                col_del_ok, col_del_cancel = st.columns(2)
                
                with col_del_ok:
                    if st.button("CONFIRMER LA SUPPRESSION DÉFINITIVE DU CLIENT", type="primary"):
                        # Utiliser le Nom du client comme clé de recherche de ligne pour la suppression
                        if supprimer_client_sheet(sheet, infos_actuelles_del['nom']):
                            st.success(f"Le client {client_selectionne_del} a été SUPPRIMÉ avec succès.")
                            # Réinitialiser l'état de confirmation
                            st.session_state.suppression_confirmee_client = False
                            st.cache_resource.clear()
                            st.rerun()
                
                with col_del_cancel:
                    if st.button("Annuler la suppression du client"):
                        st.session_state.suppression_confirmee_client = False
                        st.rerun()
                        
        # --- Suppression Intervention ---
        st.markdown("---")
        st.subheader("2. Supprimer une Intervention Spécifique")
        st.warning("⚠️ ATTENTION : Cette action supprime uniquement l'intervention sélectionnée de l'historique du client.")
        
        client_selectionne_inter_del = st.selectbox("Sélectionnez le client (pour supprimer une intervention)", sorted(db.keys()), key="select_del_inter")
        
        if client_selectionne_inter_del:
            infos_actuelles_inter_del = db[client_selectionne_inter_del]
            historique_del = infos_actuelles_inter_del.get('historique', [])
            
            if not historique_del:
                st.info("Ce client n'a pas d'historique d'intervention à supprimer.")
            else:
                # Créer des titres d'intervention pour la sélection
                options_interventions_del = [
                    f"[{h['date']}] {h.get('type', 'Intervention')} - {h.get('desc', '')[:50]}..." 
                    for h in historique_del
                ]
                
                inter_a_supprimer_titre = st.selectbox(
                    "Sélectionnez l'intervention à supprimer",
                    options_interventions_del
                )
                
                # Trouver l'index de l'intervention sélectionnée
                inter_index_del = options_interventions_del.index(inter_a_supprimer_titre)
                
                if st.button(f"SUPPRIMER l'intervention : {inter_a_supprimer_titre}", type="primary"):
                    
                    # Retirer l'intervention de la liste
                    del historique_del[inter_index_del]
                    
                    # Convertir l'historique mis à jour en JSON
                    historique_txt_del = json.dumps(historique_del, ensure_ascii=False)
                    
                    # Enregistrer le nouvel historique dans Google Sheets (Colonne 9 / I)
                    if update_client_field(sheet, infos_actuelles_inter_del['nom'], 9, historique_txt_del):
                        st.success(f"L'intervention '{inter_a_supprimer_titre}' a été supprimée avec succès de l'historique de {client_selectionne_inter_del}.")
                        st.cache_resource.clear()
                        st.rerun()
