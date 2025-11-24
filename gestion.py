import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import re # Importation du module re pour les expressions régulières/nettoyage

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Gestion Chauffagiste", page_icon="🔥", layout="wide")

# Initialiser l'état de session pour gérer la page d'entrée
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- URLs des images pour la page d'accueil ---
# FIX: Mise à jour du lien RAW de la première image
IMAGE_URL_1 = "https://raw.githubusercontent.com/Treyore/app-seb/c81b77576a13beee81e9d69f3f06f95842a34bb5/WhatsApp%20Image%202025-11-24%20at%2016.08.53.jpeg"
IMAGE_URL_2 = "https://raw.githubusercontent.com/Treyore/app-seb/92e1af7d7313f8df3cbc3ec186b5228764c23ba7/seb%20lunettes%20soleil.webp"


# --- CONNEXION GOOGLE SHEETS (Compatible PC et Cloud) ---
# Utiliser @st.cache_resource pour les connexions et ressources (Sheet, DB)
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

# --- FONCTIONS (inchangées) ---
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
            
    return db

def ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, tel, email, equipement, fichiers_client):
    # L'ordre DOIT correspond à l'ordre de vos colonnes dans Google Sheet !
    # Assurez-vous d'avoir ajouté la colonne 'Fichiers_Client' à votre Google Sheet, typiquement avant 'Historique' (colonne 9)
    nouvelle_ligne = [nom, prenom, adresse, ville, code_postal, tel, email, equipement, fichiers_client, "[]"]
    sheet.append_row(nouvelle_ligne)
    # Après ajout, invalider le cache de la feuille pour que les données soient rechargées
    st.cache_resource.clear()
    st.rerun()

# Fonction générique pour mettre à jour un champ unique dans la ligne d'un client
def update_client_field(sheet, nom_client, col_index, new_value):
    try:
        cellule = sheet.find(nom_client)
        # Utiliser la colonne 1 (Nom) pour la recherche car c'est la clé
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
        # Historique est en COLONNE 10
        sheet.update_cell(cellule.row, 10, historique_txt) 
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
# --- GESTION DE LA PAGE D'ENTRÉE ---
# ------------------------------------------------------------------
if not st.session_state.logged_in:
    st.title("🔥 App Chauffagiste - Connectée")
    st.markdown("---")
    st.header("Bienvenue Seb")
    st.markdown("## Votre tableau de bord de gestion client et interventions.")
    st.markdown("---")
    
    # Affichage des images
    col_img1, col_img2 = st.columns(2)
    
    with col_img1:
        st.image(IMAGE_URL_1, caption="Prêt pour l'action !")
        
    with col_img2:
        st.image(IMAGE_URL_2, caption="Le boss !", use_column_width=True)
        
    st.markdown("---")
    
    if st.button("Merci Ilune (Démarrer l'application)", type="primary"):
        st.session_state.logged_in = True
        st.rerun() # Recharge la page pour afficher le menu et l'appli principale

    # Arrêter l'exécution du reste du script tant que le bouton n'est pas cliqué
    st.stop()
    
# ------------------------------------------------------------------
# --- APPLICATION PRINCIPALE (Affiche uniquement si logged_in est True) ---
# ------------------------------------------------------------------

# 2. Menu (maintenant visible dans la sidebar)
menu = st.sidebar.radio(
    "Menu", 
    ("🏡 Accueil", "🔍 Rechercher", "➕ Nouveau Client", "🛠️ Nouvelle Intervention", "✍️ Mettre à jour Client"),
    # Après login, la page de recherche sera la page par défaut
    index=1 
)

# 3. Chargement des données (uniquement si ce n'est pas la page d'accueil, bien que le cache le rende rapide)
# On charge les données si on est sur n'importe quelle page fonctionnelle.
if menu == "🏡 Accueil":
    db = {} # Pas besoin de charger les données pour l'accueil simple
else:
    db = charger_donnees(sheet)

st.title("🔥 App Chauffagiste - Connectée")
st.markdown("---")

# ------------------------------------------------------------------
# --- LOGIQUE D'AFFICHAGE SELON LE MENU ---
# ------------------------------------------------------------------

if menu == "🏡 Accueil":
    st.header("Tableau de Bord")
    st.info("Bienvenue dans votre application de gestion. Utilisez le menu à gauche pour naviguer !")


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
        
        # CHAMP FICHIER CLIENT
        fichiers_client = st.text_area(
            "Liens Fichiers Client (PDF, Photos Chaudière, etc. - Séparez les liens par des virgules ou des retours à la ligne)", 
            height=100
        )
            
        valider = st.form_submit_button("Enregistrer le client")
        
        if valider and nom and prenom: # Exiger au moins Nom et Prénom
            nom_complet = f"{nom} {prenom}".strip()
            if nom_complet in db:
                st.warning(f"Le client {nom_complet} existe déjà dans la base.")
            else:
                ajouter_nouveau_client_sheet(sheet, nom, prenom, adresse, ville, code_postal, telephone, email, equipement, fichiers_client)
                st.success(f"Client {nom_complet} ajouté !")
                # st.rerun() est appelé dans la fonction d'ajout

elif menu == "🛠️ Nouvelle Intervention":
    st.header("Nouvelle Intervention")
    if db:
        # Triage de la liste des clients pour le selectbox
        choix = st.selectbox("Client", sorted(db.keys()))
        
        # CHAMPS
        col_type, col_tech = st.columns(2)
        
        with col_type:
            type_inter = st.selectbox(
                "Type d'intervention",
                ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique"],
                index=0
            )

        with col_tech:
            techniciens = st.multiselect(
                "Technicien(s) assigné(s)",
                ["Seb", "Colin"],
                default=[]
            )
            
        date = st.date_input("Date", datetime.now())
        desc = st.text_area("Description de l'intervention")
        prix = st.number_input("Prix (en €)", step=10)
        
        # CHAMP FICHIER INTERVENTION
        fichiers_inter = st.text_area(
            "Liens Fichiers Intervention (Facture, Photo des travaux, etc. - Séparez les liens par des virgules ou des retours à la ligne)", 
            height=80
        )
        
        if st.button("Valider l'intervention"):
            # Vérification simple pour s'assurer que l'intervention est assignée à au moins un technicien
            if not techniciens:
                st.warning("Veuillez assigner au moins un technicien à l'intervention.")
            else:
                # MISE À JOUR : Ajout des nouvelles informations dans le dictionnaire
                inter = {
                    "date": str(date), 
                    "type": type_inter,           
                    "techniciens": techniciens,   
                    "desc": desc, 
                    "prix": prix,
                    "fichiers_inter": fichiers_inter # Nouveau champ
                }
                ajouter_inter_sheet(sheet, choix, db, inter)
                st.success("Intervention sauvegardée en ligne !")
                # st.rerun() est appelé dans la fonction d'ajout
    else:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")

# Section pour mettre à jour et SUPPRIMER un client
elif menu == "✍️ Mettre à jour Client":
    st.header("Mettre à jour / Supprimer un client & Modifier les Interventions")
    if not db:
        st.info("La base est vide. Veuillez ajouter un client d'abord.")
    else:
        # Initialiser ou réinitialiser l'état de confirmation
        if 'suppression_confirmee' not in st.session_state:
            st.session_state.suppression_confirmee = False
            
        client_selectionne = st.selectbox("Sélectionnez le client", sorted(db.keys()))
        
        if client_selectionne:
            infos_actuelles = db[client_selectionne]
            
            # ------------------------------------------------------------------
            # --- BLOC 1 : Modification des Informations Client ---
            # ------------------------------------------------------------------
            st.subheader(f"1. Informations Générales de {client_selectionne}")
            
            with st.form("form_update_client"):
                col1_up, col2_up = st.columns(2)
                
                # J'ASSUME QUE LE NOM ET PRÉNOM NE SONT PAS MODIFIABLES (clé de recherche)
                with col1_up:
                    st.text_input("Nom (Clé)", value=infos_actuelles['nom'], disabled=True)
                    nouvelle_adresse = st.text_input("Adresse", value=infos_actuelles['adresse'])
                    nouveau_code_postal = st.text_input("Code Postal", value=infos_actuelles['code_postal'])
                    nouveau_telephone = st.text_input("Téléphone", value=infos_actuelles['telephone'])
                    
                with col2_up:
                    st.text_input("Prénom (Clé)", value=infos_actuelles['prenom'], disabled=True)
                    nouvelle_ville = st.text_input("Ville", value=infos_actuelles['ville'])
                    nouvel_email = st.text_input("Email", value=infos_actuelles['email'])
                    nouvel_equipement = st.text_input("Équipement", value=infos_actuelles['equipement'])
                
                # NOUVEAU CHAMP DE FICHIERS CLIENT
                nouveaux_fichiers_client = st.text_area(
                    "Liens Fichiers Client", 
                    value=infos_actuelles.get('fichiers_client', ''),
                    height=100
                )
                
                update_valider = st.form_submit_button("Sauvegarder les modifications Client")
                
                if update_valider:
                    try:
                        # 1. On cherche la ligne du client (par son Nom)
                        cellule = sheet.find(infos_actuelles['nom'])
                        ligne_a_modifier = cellule.row
                        
                        # 2. On met à jour les champs (ATTENTION aux INDEX de COLONNES)
                        # Je suppose l'ordre des colonnes : 1:Nom, 2:Prenom, 3:Adresse, 4:Ville, 5:CP, 6:Tel, 7:Email, 8:Equipement
                        # 9:Fichiers_Client, 10:Historique
                        sheet.update_cell(ligne_a_modifier, 3, nouvelle_adresse)  
                        sheet.update_cell(ligne_a_modifier, 4, nouvelle_ville)    
                        sheet.update_cell(ligne_a_modifier, 5, nouveau_code_postal) 
                        sheet.update_cell(ligne_a_modifier, 6, nouveau_telephone)  
                        sheet.update_cell(ligne_a_modifier, 7, nouvel_email)     
                        sheet.update_cell(ligne_a_modifier, 8, nouvel_equipement)
                        sheet.update_cell(ligne_a_modifier, 9, nouveaux_fichiers_client) # Mise à jour du nouveau champ
                        
                        st.success(f"Informations générales du client {client_selectionne} mises à jour !")
                        
                        # 3. Forcer le rechargement des données
                        st.cache_resource.clear()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Erreur lors de la mise à jour : Impossible de trouver la ligne du client. Vérifiez l'ordre des colonnes dans la fonction. {e}")
                        
            st.markdown("---")
            
            # ------------------------------------------------------------------
            # --- BLOC 2 : Modification des Interventions ---
            # ------------------------------------------------------------------
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
                
                with st.form(f"form_modifier_inter_{inter_index}"):
                    
                    col_edit_date, col_edit_prix = st.columns(2)
                    with col_edit_date:
                        # Assurer que la date est au bon format pour st.date_input
                        date_obj = datetime.strptime(inter_a_modifier['date'], '%Y-%m-%d').date()
                        nouvelle_date = st.date_input("Date", value=date_obj, key=f"date_{inter_index}")
                    
                    with col_edit_prix:
                        nouveau_prix = st.number_input("Prix (€)", value=inter_a_modifier['prix'], step=10, key=f"prix_{inter_index}")

                    col_edit_type, col_edit_tech = st.columns(2)
                    with col_edit_type:
                        nouveau_type = st.selectbox(
                            "Type d'intervention",
                            ["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique"],
                            index=["Entretien annuel", "Dépannage", "Installation", "Devis", "Visite technique"].index(inter_a_modifier.get('type', "Entretien annuel")),
                            key=f"type_{inter_index}"
                        )
                    with col_edit_tech:
                        nouveaux_techniciens = st.multiselect(
                            "Technicien(s) assigné(s)",
                            ["Seb", "Colin"],
                            default=inter_a_modifier.get('techniciens', []),
                            key=f"tech_{inter_index}"
                        )

                    nouvelle_desc = st.text_area(
                        "Description de l'intervention", 
                        value=inter_a_modifier['desc'], 
                        key=f"desc_{inter_index}"
                    )
                    
                    # NOUVEAU CHAMP FICHIER INTERVENTION
                    nouveaux_fichiers_inter = st.text_area(
                        "Liens Fichiers Intervention", 
                        value=inter_a_modifier.get('fichiers_inter', ''), 
                        height=80,
                        key=f"fichiers_{inter_index}"
                    )
                    
                    sauvegarder_inter = st.form_submit_button("Sauvegarder l'intervention modifiée")
                    
                    if sauvegarder_inter:
                        # Mettre à jour l'objet dans la liste historique
                        historique[inter_index] = {
                            "date": str(nouvelle_date),
                            "type": nouveau_type,
                            "techniciens": nouveaux_techniciens,
                            "desc": nouvelle_desc,
                            "prix": nouveau_prix,
                            "fichiers_inter": nouveaux_fichiers_inter
                        }
                        
                        # Convertir l'historique mis à jour en JSON
                        historique_txt = json.dumps(historique, ensure_ascii=False)
                        
                        # Enregistrer le nouvel historique dans Google Sheets (Colonne 10)
                        if update_client_field(sheet, infos_actuelles['nom'], 10, historique_txt):
                            st.success(f"Intervention du {nouvelle_date} mise à jour avec succès.")
                            st.cache_resource.clear()
                            st.rerun()

            st.markdown("---")
            
            # ------------------------------------------------------------------
            # --- BLOC 3 : Suppression du Client (inchangé) ---
            # ------------------------------------------------------------------
            st.subheader("3. Suppression Définitive du Client")
            st.error("Zone de Danger")
            st.warning(f"Attention : La suppression du client **{client_selectionne}** est définitive et ne peut être annulée.")

            # Étape 1: Bouton pour commencer la confirmation
            if st.button(f"Supprimer le client {client_selectionne}", key="btn_confirm_del"):
                st.session_state.suppression_confirmee = True
            
            # Étape 2: Afficher les boutons de confirmation après le premier clic
            if st.session_state.suppression_confirmee:
                st.info("Êtes-vous absolument sûr de vouloir supprimer ce client ?")
                col_del_ok, col_del_cancel = st.columns(2)
                
                with col_del_ok:
                    if st.button("CONFIRMER LA SUPPRESSION DÉFINITIVE", type="primary"):
                        if supprimer_client_sheet(sheet, infos_actuelles['nom']):
                            st.success(f"Le client {client_selectionne} a été SUPPRIMÉ avec succès.")
                            st.session_state.suppression_confirmee = False
                            # Forcer le rechargement des données
                            st.cache_resource.clear()
                            st.rerun()
                
                with col_del_cancel:
                    if st.button("Annuler la suppression"):
                        st.session_state.suppression_confirmee = False
                        st.rerun()
                        
                        
elif menu == "🔍 Rechercher":
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
