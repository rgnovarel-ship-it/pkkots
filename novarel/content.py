"""NOVAREL — contenu éditorial du site.

Source unique de vérité pour les 5 comparatifs. Les fiches produits (prix,
caractéristiques, avantages, inconvénients) sont reprises telles quelles de la
version précédente du site : rien n'est inventé ici, et toute correction de
contenu se fait dans ce fichier uniquement.

Le champ `sub` (statut abonnement) n'est renseigné que lorsque la fiche produit
l'affirme explicitement. Un produit dont la fiche ne dit rien sur l'abonnement
n'affiche aucun badge — on ne déduit pas une promesse qui n'a pas été vérifiée.
"""

from __future__ import annotations

import re

SITE_NAME = "NOVAREL"
SITE_URL = "https://novarel-site.onrender.com"
SITE_TAGLINE = "Comparatifs de sécurité domestique, sans blabla marketing"

# Statuts d'abonnement. Le premier élément sert de classe CSS.
SUB_FREE = "free"
SUB_OPTIONAL = "optional"
SUB_PARTIAL = "partial"


# ============================================================
# CAMÉRAS EXTÉRIEURES
# ============================================================

CAMERAS = [
    {
        "slug": "reolink-argus-4-pro",
        "name": "Reolink Argus 4 Pro",
        "price": "≈150–180 €",
        "power": "Batterie",
        "detail": "4K",
        "included": "Carte SD locale / NVR — aucun abonnement requis",
        "pros": "Excellent angle de vue (180°), flux RTSP pour les utilisateurs avancés, polyvalente",
        "cons": "Batterie à recharger périodiquement selon l'usage",
        "search_query": "Reolink Argus 4 Pro caméra extérieure",
        "sub": (SUB_FREE, "Sans abonnement"),
    },
    {
        "slug": "reolink-rlc-810a",
        "name": "Reolink RLC-810A",
        "price": "≈90–120 €",
        "power": "Filaire (PoE)",
        "detail": "4K",
        "included": "Carte SD ou NAS — gratuit, sans abonnement",
        "pros": "Qualité d'image très stable (pas de coupure batterie), vision nocturne couleur",
        "cons": "Nécessite un câblage Ethernet (PoE), installation un peu plus technique",
        "search_query": "Reolink RLC-810A caméra PoE",
        "sub": (SUB_FREE, "Sans abonnement"),
    },
    {
        "slug": "blink-outdoor-4",
        "name": "Blink Outdoor 4",
        "price": "≈100 € (souvent en kit)",
        "power": "Batterie (jusqu'à 2 ans d'autonomie annoncée)",
        "detail": "1080p",
        "included": "Stockage local basique gratuit ; fonctions IA avancées via abonnement optionnel",
        "pros": "Installation la plus simple du comparatif, très bonne autonomie, écosystème Amazon",
        "cons": "Résolution plus modeste que les modèles 4K, certaines fonctions réservées à l'abonnement",
        "search_query": "Blink Outdoor 4 caméra extérieure sans fil",
        "sub": (SUB_PARTIAL, "Certaines fonctions sur abonnement"),
    },
    {
        "slug": "eufycam-gamme",
        "name": "EufyCam (gamme avec HomeBase)",
        "price": "≈200–250 € (kit avec base)",
        "power": "Batterie",
        "detail": "2K à 4K selon le modèle",
        "included": "100% local via la HomeBase — réputée sans aucun frais récurrent",
        "pros": "Aucun coût récurrent même pour la détection intelligente, marque reconnue sur ce point précis",
        "cons": "Investissement de départ plus élevé (la base HomeBase est obligatoire)",
        "search_query": "EufyCam HomeBase caméra sécurité",
        "sub": (SUB_FREE, "Sans frais récurrent"),
    },
]

INTRO_CAMERAS = (
    "« Sans abonnement » est devenu un argument marketing que presque toutes les marques "
    "utilisent — jusqu'à ce qu'on découvre, une fois la caméra installée, qu'elle n'enregistre "
    "que 24 heures sans le plan cloud payant, ou que la détection intelligente est bloquée sans "
    "abonnement actif. Ce comparatif ne retient que des modèles dont les fonctions essentielles "
    "(enregistrement, détection de mouvement, vision nocturne) fonctionnent réellement sans "
    "dépenser un centime de plus après l'achat."
)

VERDICT_CAMERAS = [
    (
        "Reolink Argus 4 Pro",
        "reolink-argus-4-pro",
        "Le meilleur équilibre du comparatif : 4K, angle de 180°, enregistrement sur carte SD ou "
        "NVR sans aucun abonnement. La contrepartie assumée, c'est la recharge périodique de la "
        "batterie.",
    ),
    (
        "Reolink RLC-810A",
        "reolink-rlc-810a",
        "Le choix si vous pouvez tirer un câble Ethernet : même définition 4K, image stable sans "
        "coupure de batterie, et le prix le plus bas de la sélection.",
    ),
    (
        "Blink Outdoor 4",
        "blink-outdoor-4",
        "Pour qui veut l'installation la plus simple possible. À condition d'accepter du 1080p et "
        "de savoir que certaines fonctions restent derrière l'abonnement.",
    ),
    (
        "EufyCam (gamme avec HomeBase)",
        "eufycam-gamme",
        "Le plus cher à l'achat, mais le seul où même la détection intelligente reste gratuite, "
        "grâce au stockage 100% local sur la HomeBase.",
    ),
]

FAQ_CAMERAS = [
    (
        "Est-ce légal d'installer une caméra de surveillance chez moi ?",
        "Oui, sous réserve de respecter les règles fixées par la CNIL : vous ne pouvez filmer que "
        "l'intérieur de votre propriété (maison, jardin, allée privée), jamais la voie publique ni "
        "la propriété de vos voisins. Si une personne extérieure au foyer entre régulièrement chez "
        "vous, elle doit être informée de la présence de la caméra.",
    ),
    (
        "Où faut-il placer une caméra extérieure pour qu'elle soit efficace ?",
        "Les emplacements les plus utiles sont l'entrée principale (à 2,5–3 m de hauteur), le "
        "portail ou garage pour surveiller les véhicules, la façade arrière souvent la plus isolée, "
        "et les angles de la maison qui permettent de couvrir deux façades avec un seul appareil.",
    ),
]

PLACEMENT_TIPS = [
    ("Entrée principale", "Au-dessus de la porte, à 2,5–3 m de hauteur, couvrant l'allée d'accès."),
    ("Portail / garage", "Vue sur les véhicules entrant et sortant."),
    ("Façade arrière", "La cour ou le jardin, souvent la zone la plus isolée d'un logement."),
    ("Angle de la maison", "Permet de couvrir deux façades avec un seul appareil bien placé."),
]

SECTIONS_CAMERAS = [
    {
        "id": "legalite",
        "heading": "Est-ce légal d'installer une caméra chez moi ?",
        "html": """
<p>Oui, mais avec des règles précises fixées par la CNIL : vous ne pouvez filmer que
<strong>l'intérieur de votre propriété</strong> (maison, jardin, allée privée). Il est interdit de
filmer la voie publique — même pour surveiller votre voiture garée devant chez vous — ainsi que la
propriété de vos voisins.</p>
<p>Si une personne extérieure à la famille entre régulièrement chez vous (nounou, femme de
ménage…), vous devez l'informer de la présence de la caméra. En cas de non-respect, un recours est
possible auprès de la CNIL, de la police/gendarmerie ou de la justice.</p>
""",
    },
    {
        "id": "placement",
        "heading": "Où placer sa caméra pour qu'elle serve vraiment",
        "html": """
<p>Une caméra mal placée manque les intrusions ou devient inutilisable à cause de l'éblouissement
solaire.</p>
""",
        "tips": PLACEMENT_TIPS,
    },
]


# ============================================================
# ALARMES MAISON
# ============================================================

ALARMS = [
    {
        "slug": "somfy-home-alarm-advanced",
        "name": "Somfy Home Alarm Advanced",
        "price": "≈799 €",
        "power": "Secteur + relais GSM (5 ans offerts)",
        "detail": "Sirène 105 dB",
        "included": "3 détecteurs IntelliTAG inclus",
        "pros": "Le plus équilibré : double communication Wi-Fi + GSM, aucun abonnement obligatoire",
        "cons": "Le relais GSM devient payant (2,99 €/mois) après 5 ans, en option seulement",
        "search_query": "Somfy Home Alarm Advanced kit",
        "sub": (SUB_OPTIONAL, "Option GSM payante après 5 ans"),
    },
    {
        "slug": "netatmo-smart-alarm",
        "name": "Netatmo Smart Alarm System",
        "price": "≈350 €",
        "power": "Secteur",
        "detail": "Sirène 110 dB + caméra intégrée",
        "included": "Stockage vidéo local — jamais d'abonnement requis",
        "pros": "Le vrai « zéro frais récurrent » du comparatif, même pour la vidéo",
        "cons": "Écosystème plus fermé, moins évolutif que Somfy ou Ajax",
        "search_query": "Netatmo Smart Alarm System",
        "sub": (SUB_FREE, "Sans abonnement"),
    },
    {
        "slug": "ring-alarm-s",
        "name": "Ring Alarm S",
        "price": "dès 250 €",
        "power": "Batterie de secours 24h",
        "detail": "Kit évolutif",
        "included": "Notifications smartphone incluses",
        "pros": "Le prix d'entrée le plus bas du comparatif, kit facile à agrandir",
        "cons": "Contrôle à distance et relais GSM réservés à l'abonnement Ring Protect",
        "search_query": "Ring Alarm S kit sécurité maison",
        "sub": (SUB_PARTIAL, "Abonnement pour le contrôle à distance"),
    },
    {
        "slug": "ajax-hub-2-plus",
        "name": "Ajax Hub 2 Plus",
        "price": "Variable selon config",
        "power": "Double SIM + Ethernet + Wi-Fi",
        "detail": "Jusqu'à 200 appareils compatibles",
        "included": "Télésurveillance disponible en option, jamais imposée",
        "pros": "Le plus « pro » et évolutif : idéal pour agrandir le système avec le temps",
        "cons": "Configuration plus complexe, budget qui grimpe vite selon les accessoires choisis",
        "search_query": "Ajax Hub 2 Plus alarme maison",
        "sub": (SUB_OPTIONAL, "Télésurveillance en option"),
    },
]

INTRO_ALARMS = (
    "La majorité des alarmes vendues en magasin (Verisure en tête) imposent un abonnement de "
    "télésurveillance obligatoire, souvent entre 30 € et 50 €/mois — soit 360 € à 600 € par an, "
    "sans limite dans le temps. Les 4 systèmes ci-dessous fonctionnent très bien avec un "
    "abonnement optionnel, voire aucun abonnement du tout."
)

VERDICT_ALARMS = [
    (
        "Somfy Home Alarm Advanced",
        "somfy-home-alarm-advanced",
        "Le plus équilibré : double communication Wi-Fi + GSM et aucun abonnement obligatoire. Le "
        "relais GSM n'est offert que 5 ans, ensuite c'est 2,99 €/mois — et ça reste optionnel.",
    ),
    (
        "Netatmo Smart Alarm System",
        "netatmo-smart-alarm",
        "Le seul vrai « zéro frais récurrent » de la sélection, vidéo comprise, grâce au stockage "
        "local. En échange, l'écosystème est plus fermé et moins évolutif.",
    ),
    (
        "Ring Alarm S",
        "ring-alarm-s",
        "Le ticket d'entrée le plus bas, à condition d'assumer que le contrôle à distance et le "
        "relais GSM passent par l'abonnement Ring Protect.",
    ),
    (
        "Ajax Hub 2 Plus",
        "ajax-hub-2-plus",
        "Le choix si vous comptez agrandir l'installation dans le temps : jusqu'à 200 appareils, "
        "télésurveillance possible mais jamais imposée.",
    ),
]

FAQ_ALARMS = [
    (
        "Existe-t-il une limite légale de bruit pour une sirène d'alarme ?",
        "Il n'existe pas de norme nationale unique en France : ce sont les préfectures et "
        "municipalités qui fixent les règles. La référence la plus utilisée est 105 dB(A) mesurés "
        "à 1 mètre, pour une durée maximale de 3 minutes pour les sirènes extérieures ; au-delà, un "
        "trouble de voisinage reste possible même si l'installation elle-même est légale.",
    ),
    (
        "Une alarme maison nécessite-t-elle forcément un abonnement ?",
        "Non. Les 4 systèmes de ce comparatif fonctionnent avec un abonnement optionnel, voire sans "
        "aucun abonnement, contrairement aux offres de télésurveillance classiques qui imposent "
        "souvent 30 à 50 €/mois.",
    ),
]

SECTIONS_ALARMS = [
    {
        "id": "loi-sirenes",
        "heading": "Ce que dit la loi sur les sirènes",
        "html": """
<p>Contrairement à une idée reçue, il n'existe pas de norme nationale unique en France : ce sont les
<strong>préfectures et municipalités</strong> qui fixent les règles précises. La référence la plus
utilisée est <strong>105 dB(A) mesurés à 1 mètre, pour une durée maximale de 3 minutes</strong> pour
les sirènes extérieures — au-delà, vous risquez un trouble de voisinage, et une plainte reste
possible même si l'installation elle-même est légale. Les sirènes intérieures ne sont pas soumises à
cette limite de durée, mais doivent respecter un cycle court dans les immeubles collectifs.</p>
""",
        "callout": (
            "À retenir avant d'installer",
            "Vérifiez que votre sirène est certifiée aux normes en vigueur, et informez vos voisins "
            "directs si vous installez une sirène extérieure puissante — ça évite les tensions "
            "inutiles.",
        ),
    },
]


# ============================================================
# SERRURES CONNECTÉES
# ============================================================

LOCKS = [
    {
        "slug": "nuki-smart-lock-ultra",
        "name": "Nuki Smart Lock Ultra",
        "price": "≈349 €",
        "power": "Batterie rechargeable intégrée",
        "detail": "Wi-Fi, Matter, Thread, Bluetooth",
        "included": "Cylindre modulaire compatible 96 configurations de porte",
        "pros": "Le plus complet techniquement, aucun abonnement pour les fonctions de base",
        "cons": "Câble de recharge propriétaire, clavier à code vendu séparément",
        "search_query": "Nuki Smart Lock Ultra serrure connectée",
        "sub": (SUB_FREE, "Sans abonnement (fonctions de base)"),
    },
    {
        "slug": "yale-linus-l2",
        "name": "Yale Linus L2",
        "price": "≈238 €",
        "power": "Piles",
        "detail": "Bluetooth + module Wi-Fi optionnel",
        "included": "Compatible Google Home, Alexa",
        "pros": "Design discret, écosystème Yale déjà installé chez beaucoup de foyers",
        "cons": "Autonomie de la batterie parfois limitée selon l'usage",
        "search_query": "Yale Linus L2 serrure connectée",
        "sub": None,
    },
    {
        "slug": "somfy-door-keeper",
        "name": "Somfy Door Keeper",
        "price": "≈250–350 €",
        "power": "Piles",
        "detail": "Bluetooth (Wi-Fi via passerelle TaHoma en option)",
        "included": "Remplace le cylindre européen existant, conserve la serrure d'origine",
        "pros": "Certifié A2P — le seul du comparatif dans ce cas, un vrai plus pour l'assurance",
        "cons": "Passerelle TaHoma en supplément si vous voulez le contrôle à distance",
        "search_query": "Somfy Door Keeper serrure connectée",
        "sub": None,
    },
    {
        "slug": "switchbot-lock-pro",
        "name": "SwitchBot Lock Pro",
        "price": "≈140 €",
        "power": "4 piles AA (6 à 9 mois d'autonomie)",
        "detail": "Bluetooth (Matter via Hub 2 en option)",
        "included": "Portée Bluetooth jusqu'à 120 m en extérieur",
        "pros": "L'entrée de gamme du comparatif, aucun abonnement, installation simple",
        "cons": "Fonctions avancées (Wi-Fi, assistants vocaux) nécessitent le Hub 2 en plus",
        "search_query": "SwitchBot Lock Pro serrure connectée",
        "sub": (SUB_FREE, "Sans abonnement"),
    },
]

INTRO_LOCKS = (
    "Une serrure connectée séduit pour le confort, mais un détail est presque toujours ignoré : "
    "votre assurance habitation. La plupart des contrats exigent une serrure certifiée A2P pour "
    "garantir une indemnisation en cas de cambriolage — et beaucoup de serrures connectées "
    "populaires n'ont jamais été soumises à cette certification. Ce comparatif vous dit ce que "
    "chaque modèle change vraiment côté sécurité, pas seulement côté confort."
)

VERDICT_LOCKS = [
    (
        "Nuki Smart Lock Ultra",
        "nuki-smart-lock-ultra",
        "La plus complète techniquement (Wi-Fi, Matter, Thread, Bluetooth) et sans abonnement pour "
        "les fonctions de base. Le clavier à code, lui, est vendu à part.",
    ),
    (
        "Somfy Door Keeper",
        "somfy-door-keeper",
        "La seule certifiée A2P de la sélection — c'est l'argument qui compte face à votre "
        "assureur. Le contrôle à distance impose d'ajouter la passerelle TaHoma.",
    ),
    (
        "Yale Linus L2",
        "yale-linus-l2",
        "Le choix discret et déjà familier pour les foyers équipés Yale. L'autonomie peut décevoir "
        "selon l'usage.",
    ),
    (
        "SwitchBot Lock Pro",
        "switchbot-lock-pro",
        "L'entrée de gamme à ≈140 €, sans abonnement et simple à poser. Les fonctions avancées "
        "réclament le Hub 2 en supplément.",
    ),
]

FAQ_LOCKS = [
    (
        "Qu'est-ce que la certification A2P sur une serrure ?",
        "C'est une certification délivrée par le CNPP, organisme indépendant créé par les "
        "assureurs, qui évalue la résistance à l'effraction : une étoile = 5 minutes de résistance "
        "testée en laboratoire, deux étoiles = 10 minutes, trois étoiles = 15 minutes. La plupart "
        "des contrats habitation exigent au moins deux étoiles pour une maison.",
    ),
    (
        "Une serrure connectée peut-elle réduire l'indemnisation en cas de cambriolage ?",
        "Oui, si elle ne correspond pas à ce qu'exige votre contrat d'assurance. Il est recommandé "
        "de demander une confirmation écrite à votre assureur avant l'installation plutôt que de le "
        "découvrir après un sinistre.",
    ),
]

SECTIONS_LOCKS = [
    {
        "id": "assurance",
        "heading": "Le détail que presque personne ne vérifie : votre assurance",
        "html": """
<p>Les assureurs se basent sur la certification <strong>A2P</strong> (délivrée par le CNPP,
organisme indépendant créé par les assureurs) pour évaluer la résistance d'une serrure à
l'effraction : une étoile = 5 minutes de résistance testée en laboratoire, deux étoiles = 10
minutes, trois étoiles = 15 minutes. La plupart des contrats habitation exigent au moins deux
étoiles pour une maison. <strong>En cas de cambriolage, si la serrure installée ne correspond pas à
ce qui est exigé dans votre contrat, l'indemnisation peut être réduite, voire refusée.</strong></p>
<p>Pour les serrures connectées spécifiquement, il existe une certification dédiée :
<strong>A2P@</strong>, qui combine résistance mécanique et sécurité informatique de l'appareil et de
son application. Peu de modèles grand public l'obtiennent.</p>
""",
        "callout": (
            "Ce qu'il faut vérifier avant d'acheter",
            "Une serrure qui remplace uniquement le cylindre (comme la plupart des modèles de ce "
            "comparatif) conserve en général le bloc de porte existant — mais le niveau de "
            "protection global dépend de l'ensemble de l'installation, pas seulement du cylindre. "
            "Le plus sûr reste de demander confirmation écrite à votre assureur avant "
            "l'installation, plutôt que de le découvrir après un sinistre.",
        ),
    },
]


# ============================================================
# DÉTECTEURS DE FUMÉE CONNECTÉS
# ============================================================

SMOKE_DETECTORS = [
    {
        "slug": "google-nest-protect",
        "name": "Google Nest Protect (2ᵉ génération)",
        "price": "≈120–150 €",
        "power": "Piles ou secteur (selon modèle)",
        "detail": "Détecte fumée ET monoxyde de carbone",
        "included": "Alerte vocale + notification smartphone",
        "pros": "Le seul du comparatif à couvrir fumée + CO dans un seul appareil",
        "cons": "Prix le plus élevé de la sélection",
        "search_query": "Google Nest Protect détecteur fumée",
        "sub": None,
    },
    {
        "slug": "netatmo-detecteur-fumee",
        "name": "Netatmo Détecteur de Fumée Intelligent",
        "price": "≈90–110 €",
        "power": "Pile scellée 10 ans",
        "detail": "Notification smartphone même hors domicile",
        "included": "Aucune maintenance de pile pendant 10 ans",
        "pros": "Autonomie record : zéro changement de pile pendant une décennie",
        "cons": "Détecte uniquement la fumée, pas le CO",
        "search_query": "Netatmo détecteur de fumée intelligent",
        "sub": None,
    },
    {
        "slug": "somfy-detecteur-fumee-io",
        "name": "Somfy Détecteur de Fumée io",
        "price": "≈65–90 €",
        "power": "Pile",
        "detail": "Intégration à l'écosystème Somfy (alarme, volets)",
        "included": "Notification via l'appli Somfy",
        "pros": "Bon compromis prix/intégration si vous avez déjà du matériel Somfy",
        "cons": "Moins intéressant en dehors de l'écosystème Somfy",
        "search_query": "Somfy détecteur de fumée io",
        "sub": None,
    },
    {
        "slug": "x-sense-sc07-wx",
        "name": "X-Sense SC07-WX",
        "price": "≈55–80 €",
        "power": "Pile",
        "detail": "Wi-Fi intégré, notification directe",
        "included": "Application dédiée avec historique d'alertes",
        "pros": "Le meilleur rapport prix/fonctions connectées du comparatif",
        "cons": "Écosystème moins étendu que Google ou Netatmo",
        "search_query": "X-Sense SC07-WX détecteur fumée connecté",
        "sub": None,
    },
]

INTRO_SMOKE = (
    "Contrairement aux caméras ou aux alarmes, ce n'est pas une option : depuis la loi Morange "
    "du 8 mars 2015, tout logement en France doit être équipé d'au moins un détecteur de fumée "
    "conforme à la norme NF EN 14604. Ce n'est pas juste une obligation administrative — en cas "
    "d'incendie, l'absence de détecteur peut réduire l'indemnisation de votre assurance "
    "habitation. Autant choisir un modèle qui vous prévient même quand vous n'êtes pas chez vous."
)

VERDICT_SMOKE = [
    (
        "Google Nest Protect (2ᵉ génération)",
        "google-nest-protect",
        "Le seul à couvrir fumée <em>et</em> monoxyde de carbone dans un seul appareil, avec alerte "
        "vocale. C'est aussi le plus cher de la sélection.",
    ),
    (
        "Netatmo Détecteur de Fumée Intelligent",
        "netatmo-detecteur-fumee",
        "Pile scellée 10 ans : zéro maintenance pendant une décennie. Il ne détecte que la fumée, "
        "pas le CO.",
    ),
    (
        "X-Sense SC07-WX",
        "x-sense-sc07-wx",
        "Le meilleur rapport prix/fonctions connectées, Wi-Fi intégré à partir de ≈55 €. "
        "L'écosystème est plus limité que Google ou Netatmo.",
    ),
    (
        "Somfy Détecteur de Fumée io",
        "somfy-detecteur-fumee-io",
        "Pertinent surtout si vous avez déjà du matériel Somfy : il s'intègre à l'alarme et aux "
        "volets. Hors de cet écosystème, l'intérêt retombe.",
    ),
]

FAQ_SMOKE = [
    (
        "Le détecteur de fumée est-il obligatoire en France ?",
        "Oui, depuis la loi Morange du 8 mars 2015, tout logement doit être équipé d'au moins un "
        "détecteur autonome avertisseur de fumée (DAAF) conforme à la norme NF EN 14604 et marqué "
        "CE, avec une alerte sonore d'au moins 85 dB(A) mesurée à 3 mètres.",
    ),
    (
        "Qui doit installer le détecteur de fumée en location, le propriétaire ou le locataire ?",
        "C'est le propriétaire qui doit l'installer ; le locataire est responsable de son entretien "
        "pendant la durée du bail.",
    ),
]

SECTIONS_SMOKE = [
    {
        "id": "obligation-legale",
        "heading": "Ce n'est pas une option : ce que dit la loi",
        "html": """
<p>Depuis la <strong>loi Morange du 8 mars 2015</strong> (décret n°2011-36), tout logement en France
doit être équipé d'au moins un détecteur autonome avertisseur de fumée (DAAF), conforme à la norme
<strong>NF EN 14604</strong> et marqué CE. L'appareil doit émettre une alerte sonore d'au moins
85 dB(A) mesurée à 3 mètres.</p>
<p>En location, c'est le <strong>propriétaire</strong> qui doit l'installer ; le
<strong>locataire</strong> est responsable de son entretien pendant la durée du bail. En cas
d'absence de détecteur lors d'un incendie, l'indemnisation de votre assurance habitation peut être
réduite — en plus du risque évident pour la sécurité du foyer.</p>
""",
        "callout": (
            "Ce que la version connectée apporte en plus",
            "Une alerte sur votre téléphone même si vous n'êtes pas chez vous — utile si vous avez "
            "un animal, une location saisonnière, ou si vous voulez surveiller une résidence "
            "secondaire à distance.",
        ),
    },
]


# ============================================================
# DÉTECTEURS DE FUITE D'EAU
# ============================================================

WATER_LEAK = [
    {
        "slug": "switchbot-detecteur-fuite-eau",
        "name": "SwitchBot Détecteur de fuite d'eau",
        "price": "≈22 €",
        "power": "Pile, Wi-Fi direct (pas de hub requis)",
        "detail": "IP67, alerte app en cas de fuite",
        "included": "Notifications smartphone incluses, aucun abonnement",
        "pros": "Le meilleur rapport prix/simplicité : installation en 2 minutes, sans hub",
        "cons": "Un seul capteur par appareil — il en faut plusieurs pour couvrir toute la maison",
        "search_query": "SwitchBot détecteur de fuite d'eau",
        "sub": (SUB_FREE, "Sans abonnement"),
    },
    {
        "slug": "x-sense-sws54",
        "name": "X-Sense SWS51/54 (kit + station)",
        "price": "dès 19,99 € l'unité, 59,99 € le kit 3 capteurs + station",
        "power": "Pile, portée jusqu'à 500 m annoncée",
        "detail": "Alarme 100-120 dB, détection dès 0,4 mm d'eau",
        "included": "Application dédiée, aucun abonnement",
        "pros": "Idéal pour une buanderie ou une cave éloignée grâce à sa portée",
        "cons": "Le kit avec station coûte plus cher que l'unité seule si vous n'avez qu'un point à couvrir",
        "search_query": "X-Sense SWS54 kit détecteur fuite eau",
        "sub": (SUB_FREE, "Sans abonnement"),
    },
    {
        "slug": "us-solid-vanne-motorisee",
        "name": "U.S. Solid — système avec vanne motorisée",
        "price": "≈91 $ (≈85 €)",
        "power": "Secteur/pile selon modèle + vanne à bille motorisée 3/4\"",
        "detail": "3 capteurs + alarme sonore",
        "included": "Coupe l'eau automatiquement dès qu'une fuite est détectée",
        "pros": "Le seul qui agit sans vous : il coupe physiquement l'arrivée d'eau, pas juste une alerte",
        "cons": "Installation plus technique (raccordement sur l'arrivée d'eau), budget plus élevé",
        "search_query": "U.S. Solid détecteur fuite eau vanne motorisée",
        "sub": None,
    },
]

INTRO_WATER = (
    "Un dégât des eaux coûte en moyenne plusieurs milliers d'euros de réparations (parquet, "
    "plâtre, électroménager). Un détecteur à moins de 25 € peut couper l'eau ou vous alerter "
    "avant que ça ne dégénère. C'est aussi la seule catégorie de ce comparatif où plusieurs "
    "assureurs offrent une vraie réduction de prime pour en installer."
)

VERDICT_WATER = [
    (
        "SwitchBot Détecteur de fuite d'eau",
        "switchbot-detecteur-fuite-eau",
        "≈22 €, Wi-Fi direct sans hub, posé en deux minutes. Un capteur ne couvre qu'un point : il "
        "en faut plusieurs pour toute la maison.",
    ),
    (
        "X-Sense SWS51/54 (kit + station)",
        "x-sense-sws54",
        "La portée annoncée jusqu'à 500 m en fait le bon choix pour une cave ou une buanderie "
        "éloignée. Le kit avec station revient plus cher si vous n'avez qu'un point à couvrir.",
    ),
    (
        "U.S. Solid — système avec vanne motorisée",
        "us-solid-vanne-motorisee",
        "Le seul qui agit à votre place : il coupe physiquement l'arrivée d'eau. En contrepartie, "
        "l'installation est plus technique et le budget plus élevé.",
    ),
]

FAQ_WATER = [
    (
        "Un détecteur de fuite d'eau peut-il faire baisser mon assurance habitation ?",
        "Chez plusieurs assureurs français, oui : MAIF et GMF jusqu'à 12% via des partenariats avec "
        "Netatmo et Somfy, Allianz jusqu'à 15% via Homiris, Cardif jusqu'à 15% selon un "
        "questionnaire sur les équipements déclarés. La fourchette observée sur le marché est de "
        "10 à 25% de réduction de prime — à vérifier directement avec votre assureur.",
    ),
    (
        "Combien de capteurs faut-il installer dans une maison ?",
        "Il est recommandé de placer au moins un capteur sous chaque point à risque (évier, "
        "lave-linge, lave-vaisselle, chauffe-eau, WC) plutôt qu'un seul capteur pour toute la "
        "maison : c'est la position du capteur, pas son nombre total, qui détermine si la fuite est "
        "repérée à temps.",
    ),
]

SECTIONS_WATER = [
    {
        "id": "reduction-assurance",
        "heading": "Ce que ça change vraiment : la réduction d'assurance",
        "html": """
<p>Contrairement aux alarmes anti-intrusion, les détecteurs de fuite d'eau ouvrent droit à de vraies
réductions chez plusieurs assureurs français : <strong>MAIF et GMF</strong> jusqu'à 12% via des
partenariats avec Netatmo et Somfy, <strong>Allianz</strong> jusqu'à 15% via Homiris,
<strong>Cardif</strong> jusqu'à 15% selon un questionnaire sur les équipements déclarés, et
<strong>MMA</strong> via leur contrat « Smart Home ». Plus largement, la fourchette observée sur le
marché est de <strong>10 à 25% de réduction de prime</strong> pour des équipements connectés
déclarés et certifiés — vérifiez directement avec votre assureur avant d'acheter en vous basant
uniquement sur cet argument.</p>
""",
        "callout": (
            "À retenir avant d'installer",
            "Placez au moins un capteur sous chaque point à risque (évier, lave-linge, "
            "lave-vaisselle, chauffe-eau, WC), pas juste un seul pour toute la maison — c'est la "
            "position du capteur, pas le nombre d'appareils, qui détermine si la fuite est repérée "
            "à temps.",
        ),
    },
]


# ============================================================
# CATÉGORIES
# ============================================================

CATEGORIES = [
    {
        "path": "/cameras-exterieures-sans-abonnement",
        "key": "cameras",
        "icon": "camera",
        "nav_label": "Caméras",
        "label": "Caméras extérieures",
        "h1": "Meilleures caméras extérieures sans abonnement",
        "eyebrow": "Comparatif 2026",
        "page_title": "Meilleures caméras extérieures sans abonnement (2026)",
        "meta_desc": (
            "4 caméras extérieures qui fonctionnent vraiment sans abonnement : Reolink, Blink, "
            "EufyCam comparées sur prix, autonomie et stockage. Plus la réglementation CNIL à "
            "connaître."
        ),
        "home_desc": (
            "4 modèles comparés sur le seul critère qui compte vraiment : est-ce que ça marche "
            "encore une fois l'abonnement refusé ?"
        ),
        "short_desc": "4 modèles comparés sans abonnement.",
        "products": CAMERAS,
        "intro": INTRO_CAMERAS,
        "verdict": VERDICT_CAMERAS,
        "sections": SECTIONS_CAMERAS,
        "faq": FAQ_CAMERAS,
        "detail_label": "Résolution",
        "included_label": "Stockage",
        "related": [
            "/alarmes-maison-sans-abonnement",
            "/serrures-connectees-sans-abonnement",
        ],
    },
    {
        "path": "/alarmes-maison-sans-abonnement",
        "key": "alarmes",
        "icon": "siren",
        "nav_label": "Alarmes",
        "label": "Alarmes maison",
        "h1": "Meilleures alarmes maison sans abonnement",
        "eyebrow": "Comparatif 2026",
        "page_title": "Meilleures alarmes maison sans abonnement (2026)",
        "meta_desc": (
            "Somfy, Netatmo, Ring, Ajax : 4 alarmes maison sans abonnement obligatoire comparées, "
            "plus ce que dit vraiment la loi sur les sirènes en France."
        ),
        "home_desc": (
            "4 systèmes qui fonctionnent sans abonnement obligatoire — et ce que dit vraiment la "
            "loi sur les sirènes."
        ),
        "short_desc": "4 systèmes qui fonctionnent sans abonnement obligatoire.",
        "products": ALARMS,
        "intro": INTRO_ALARMS,
        "verdict": VERDICT_ALARMS,
        "sections": SECTIONS_ALARMS,
        "faq": FAQ_ALARMS,
        "detail_label": "Sirène / capacité",
        "included_label": "Inclus",
        "related": [
            "/cameras-exterieures-sans-abonnement",
            "/serrures-connectees-sans-abonnement",
        ],
    },
    {
        "path": "/serrures-connectees-sans-abonnement",
        "key": "serrures",
        "icon": "lock",
        "nav_label": "Serrures",
        "label": "Serrures connectées",
        "h1": "Meilleures serrures connectées sans abonnement",
        "eyebrow": "Comparatif 2026",
        "page_title": "Meilleures serrures connectées sans abonnement (2026)",
        "meta_desc": (
            "Nuki, Yale, Somfy, SwitchBot comparées — et le point assurance (certification A2P) "
            "que la plupart des comparatifs ne mentionnent jamais."
        ),
        "home_desc": (
            "4 modèles comparés, et le détail assurance que presque personne ne vérifie avant "
            "d'acheter."
        ),
        "short_desc": "4 modèles, et le point assurance à vérifier avant d'acheter.",
        "products": LOCKS,
        "intro": INTRO_LOCKS,
        "verdict": VERDICT_LOCKS,
        "sections": SECTIONS_LOCKS,
        "faq": FAQ_LOCKS,
        "detail_label": "Connectivité",
        "included_label": "Compatibilité",
        "related": [
            "/alarmes-maison-sans-abonnement",
            "/cameras-exterieures-sans-abonnement",
        ],
    },
    {
        "path": "/detecteurs-fumee-connectes",
        "key": "fumee",
        "icon": "flame",
        "nav_label": "Fumée",
        "label": "Détecteurs de fumée",
        "h1": "Meilleurs détecteurs de fumée connectés",
        "eyebrow": "Obligation légale + comparatif 2026",
        "page_title": "Meilleurs détecteurs de fumée connectés (2026)",
        "meta_desc": (
            "Google Nest Protect, Netatmo, Somfy, X-Sense comparés — et l'obligation légale (loi "
            "Morange, norme NF EN 14604) que tout logement français doit respecter."
        ),
        "home_desc": (
            "Seul produit du site qui est une obligation légale — voici comment bien le choisir."
        ),
        "short_desc": "Obligation légale : comment bien le choisir.",
        "products": SMOKE_DETECTORS,
        "intro": INTRO_SMOKE,
        "verdict": VERDICT_SMOKE,
        "sections": SECTIONS_SMOKE,
        "faq": FAQ_SMOKE,
        "detail_label": "Détection",
        "included_label": "Alerte",
        "related": [
            "/detecteurs-fuite-eau-connectes",
            "/alarmes-maison-sans-abonnement",
        ],
    },
    {
        "path": "/detecteurs-fuite-eau-connectes",
        "key": "fuite-eau",
        "icon": "droplet",
        "nav_label": "Fuite d'eau",
        "label": "Détecteurs de fuite d'eau",
        "h1": "Meilleurs détecteurs de fuite d'eau connectés",
        "eyebrow": "Comparatif 2026",
        "page_title": "Meilleurs détecteurs de fuite d'eau connectés (2026)",
        "meta_desc": (
            "SwitchBot, X-Sense, U.S. Solid comparés — et les réductions d'assurance habitation "
            "(MAIF, Allianz, Cardif) que ce détecteur peut vous faire gagner."
        ),
        "home_desc": (
            "Le détecteur le plus rentable de la maison — et celui qui fait vraiment baisser votre "
            "assurance."
        ),
        "short_desc": "Le détecteur le plus rentable de la maison.",
        "products": WATER_LEAK,
        "intro": INTRO_WATER,
        "verdict": VERDICT_WATER,
        "sections": SECTIONS_WATER,
        "faq": FAQ_WATER,
        "detail_label": "Détection",
        "included_label": "Alerte",
        "related": [
            "/detecteurs-fumee-connectes",
            "/alarmes-maison-sans-abonnement",
        ],
    },
]

CATEGORY_BY_PATH = {c["path"]: c for c in CATEGORIES}

ALL_PRODUCTS = {p["slug"]: p for c in CATEGORIES for p in c["products"]}

TOTAL_PRODUCTS = len(ALL_PRODUCTS)


# ============================================================
# ACCUEIL
# ============================================================

HOME_STATS = [
    ("05", "catégories couvertes", "Caméras, alarmes, serrures, fumée, fuite d'eau."),
    (f"{TOTAL_PRODUCTS}", "produits comparés", "Chacun avec ses limites écrites noir sur blanc."),
    ("00", "note chiffrée inventée", "Pas de « 8,4/10 » sorti de nulle part."),
    ("00", "test sponsorisé", "Aucune marque ne paie pour figurer ici."),
]

HOME_PRINCIPLES = [
    (
        "On écrit aussi ce qu'on ne fait pas",
        "Nous ne testons pas physiquement les produits. C'est assumé et expliqué dans notre "
        "méthodologie, pas dissimulé en petits caractères.",
    ),
    (
        "Le critère abonnement, produit par produit",
        "Pour chaque modèle, on précise ce qui continue de fonctionner le jour où vous refusez de "
        "payer tous les mois. C'est le seul angle du site.",
    ),
    (
        "Des prix datés, pas des prix magiques",
        "Les prix affichés sont des ordres de grandeur relevés à la date indiquée en haut de "
        "chaque comparatif. Ils bougent : vérifiez avant d'acheter.",
    ),
]

HOME_LEGAL = [
    (
        "CNIL",
        "Filmer la voie publique est interdit",
        "Une caméra privée ne peut couvrir que votre propriété. Ni le trottoir, ni chez le voisin.",
        "/cameras-exterieures-sans-abonnement#legalite",
    ),
    (
        "Loi Morange",
        "Le détecteur de fumée est obligatoire",
        "Depuis le 8 mars 2015, tout logement doit disposer d'un DAAF conforme à la norme "
        "NF EN 14604.",
        "/detecteurs-fumee-connectes#obligation-legale",
    ),
    (
        "Certification A2P",
        "Votre assurance peut refuser d'indemniser",
        "Si la serrure installée ne correspond pas au niveau exigé par votre contrat, "
        "l'indemnisation peut être réduite.",
        "/serrures-connectees-sans-abonnement#assurance",
    ),
]


# ============================================================
# MÉTHODOLOGIE
# ============================================================

METHODOLOGY_INTRO = (
    "Un comparatif n'a de valeur que si l'on sait comment il a été fabriqué. Voici exactement ce "
    "que nous faisons, ce que nous ne faisons pas, et comment nous sommes rémunérés."
)

METHODOLOGY_SECTIONS = [
    {
        "id": "sources",
        "heading": "Nos sources",
        "html": """
<p>Les informations techniques (prix, autonomie, compatibilité, résolution) proviennent des fiches
produit officielles des fabricants, de comparatifs indépendants publiés par des médias spécialisés,
et de la réglementation officielle en vigueur (CNIL, lois, normes NF/A2P) citée directement dans
chaque article.</p>
""",
    },
    {
        "id": "criteres",
        "heading": "Nos critères de sélection",
        "html": """
<p>Chaque produit retenu doit fonctionner sans abonnement obligatoire pour ses fonctions
essentielles (enregistrement, détection, alerte). Nous excluons les produits dont les fonctions de
base sont bloquées derrière un plan payant. Le classement (#1, #2, #3) reflète le meilleur équilibre
entre prix, autonomie sans frais récurrents et fiabilité constatée dans les retours d'utilisateurs
et comparatifs consultés.</p>
""",
    },
    {
        "id": "limites",
        "heading": "Ce que nous ne faisons pas",
        "html": """
<p><strong>Nous ne testons pas physiquement chaque produit.</strong> Ce site s'appuie sur l'analyse
de fiches techniques, de comparatifs tiers et de la réglementation, pas sur des essais en conditions
réelles menés par notre équipe. Nous ne publions aucune note chiffrée inventée : les avantages et
inconvénients listés sont qualitatifs et sourcés.</p>
""",
        "flag": True,
    },
    {
        "id": "prix",
        "heading": "Mise à jour des prix",
        "html": """
<p>Les prix affichés sont des ordres de grandeur constatés au moment de la rédaction de chaque
article (voir la date de mise à jour en haut de page). Les prix réels évoluent en permanence sur
Amazon : vérifiez toujours le prix actuel avant achat via le lien fourni.</p>
""",
    },
    {
        "id": "remuneration",
        "heading": "Rémunération",
        "html": """
<p>Ce site perçoit une commission sur les achats réalisés via les liens Amazon, sans coût
supplémentaire pour vous. Cette rémunération n'influence pas le classement : elle est identique quel
que soit le produit acheté.</p>
""",
    },
]


# ============================================================
# UTILITAIRES
# ============================================================

# Un montant, éventuellement sous forme de fourchette, suivi de sa devise :
# « 349 € », « 90–120 € », « 19,99 € ». Le chiffre doit être adjacent à la devise,
# sinon « 3 capteurs » serait pris pour un prix.
_PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:[–—-]\s*(\d+(?:[.,]\d+)?))?\s*(€|\$)")


def parse_price(price_str: str):
    """Renvoie (borne basse, borne haute, devise) pour la devise dominante.

    Ne fabrique jamais de valeur : renvoie (None, None, None) si le texte ne
    contient aucun montant (ex. « Variable selon config »). Quand deux devises
    cohabitent (« ≈91 $ (≈85 €) »), seule la première est retenue.
    """
    matches = _PRICE_RE.findall(price_str)
    if not matches:
        return None, None, None

    symbol = matches[0][2]
    amounts = []
    for low, high, sym in matches:
        if sym != symbol:
            continue
        amounts.append(float(low.replace(",", ".")))
        if high:
            amounts.append(float(high.replace(",", ".")))

    return min(amounts), max(amounts), ("EUR" if symbol == "€" else "USD")


def price_sort_key(price_str: str) -> float:
    """Clé de tri du comparateur : la borne basse. Les prix non chiffrés finissent en bas."""
    low, _, _ = parse_price(price_str)
    return low if low is not None else float("inf")


MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def format_date_fr(d) -> str:
    return f"{d.day} {MONTHS_FR[d.month - 1]} {d.year}"


# Clé de tri du comparateur, calculée une fois au chargement du module.
for _product in ALL_PRODUCTS.values():
    _product["price_sort"] = price_sort_key(_product["price"])
