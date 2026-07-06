"""
AyurKosha — Build Synonym Dictionaries
Generates herb and disease synonym JSON files.

These dictionaries are the highest-impact data asset in the system: without
synonym expansion, BM25 keyword search fails whenever a query uses a name
variant the source text does not (e.g. "Amla" vs "Amalaki" vs
"Phyllanthus emblica"). The tokenizer (src/retrieval/tokenizer.py) loads
these via src/ingestion/synonym_loader.py and expands every recognized term
to all of its known variants at index and query time.

The herb entries also carry Rasa/Guna/Virya/Vipaka/Dosha-relevant fields where
known; these feed the planned GraphRAG ontology (Phase 2).

Run: python scripts/build_synonyms.py

NOTE: This is a curated seed set aimed at the Phase 1 target (~50 herbs,
~30 diseases). Expand toward 200+ herbs / 100+ diseases from the Nighantu
texts (Bhavaprakasha, Dhanvantari, Raja, Kaiyadeva) over time.
"""

import json
from pathlib import Path

# Resolve the project root from this file so the script works regardless of the
# directory it is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_herb_synonyms() -> dict:
    """Build herb synonym dictionary. Keys are canonical lowercase slugs.

    Each entry lists name variants grouped by language/script plus botanical
    family. All variants are treated as mutually interchangeable during BM25
    synonym expansion.
    """
    return {
        "ashwagandha": {
            "sanskrit": ["Ashwagandha", "Vajigandha", "Balada", "Varahakarni"],
            "latin": ["Withania somnifera"],
            "hindi": ["Asgandh"],
            "english": ["Indian Ginseng", "Winter Cherry"],
            "family": "Solanaceae",
        },
        "amalaki": {
            "sanskrit": ["Amalaki", "Dhatri", "Amritaphala", "Sheetaphala", "Vayastha"],
            "latin": ["Emblica officinalis", "Phyllanthus emblica"],
            "hindi": ["Amla"],
            "english": ["Indian Gooseberry"],
            "family": "Phyllanthaceae",
        },
        "haritaki": {
            "sanskrit": ["Haritaki", "Abhaya", "Pathya", "Haimavati"],
            "latin": ["Terminalia chebula"],
            "hindi": ["Harad", "Harde"],
            "english": ["Chebulic Myrobalan"],
            "family": "Combretaceae",
        },
        "bibhitaki": {
            "sanskrit": ["Bibhitaki", "Vibhitaka", "Aksha"],
            "latin": ["Terminalia bellirica"],
            "hindi": ["Baheda"],
            "english": ["Belleric Myrobalan"],
            "family": "Combretaceae",
        },
        "haridra": {
            "sanskrit": ["Haridra", "Gauri", "Kanchani", "Nisha"],
            "latin": ["Curcuma longa"],
            "hindi": ["Haldi"],
            "english": ["Turmeric"],
            "family": "Zingiberaceae",
        },
        "guduchi": {
            "sanskrit": ["Guduchi", "Amrita", "Madhuparni", "Chinnaruha"],
            "latin": ["Tinospora cordifolia"],
            "hindi": ["Giloy"],
            "english": ["Heart-leaved Moonseed"],
            "family": "Menispermaceae",
        },
        "shatavari": {
            "sanskrit": ["Shatavari", "Shatamuli", "Bahusuta"],
            "latin": ["Asparagus racemosus"],
            "hindi": ["Shatavar"],
            "english": ["Wild Asparagus"],
            "family": "Asparagaceae",
        },
        "brahmi": {
            "sanskrit": ["Brahmi", "Saraswati", "Somavalli"],
            "latin": ["Bacopa monnieri"],
            "hindi": ["Brahmi"],
            "english": ["Water Hyssop"],
            "family": "Plantaginaceae",
        },
        "mandukaparni": {
            "sanskrit": ["Mandukaparni", "Manduki"],
            "latin": ["Centella asiatica"],
            "hindi": ["Brahmi Booti"],
            "english": ["Gotu Kola", "Indian Pennywort"],
            "family": "Apiaceae",
        },
        "tulsi": {
            "sanskrit": ["Tulasi", "Surasa", "Sulabha"],
            "latin": ["Ocimum sanctum", "Ocimum tenuiflorum"],
            "hindi": ["Tulsi"],
            "english": ["Holy Basil"],
            "family": "Lamiaceae",
        },
        "nimba": {
            "sanskrit": ["Nimba", "Arishta", "Pichumarda"],
            "latin": ["Azadirachta indica"],
            "hindi": ["Neem"],
            "english": ["Margosa", "Neem"],
            "family": "Meliaceae",
        },
        "yashtimadhu": {
            "sanskrit": ["Yashtimadhu", "Madhuka", "Madhuyashti"],
            "latin": ["Glycyrrhiza glabra"],
            "hindi": ["Mulethi"],
            "english": ["Licorice", "Liquorice"],
            "family": "Fabaceae",
        },
        "shunthi": {
            "sanskrit": ["Shunthi", "Nagara", "Vishwabheshaja", "Vishwa"],
            "latin": ["Zingiber officinale"],
            "hindi": ["Sonth", "Adrak"],
            "english": ["Ginger", "Dry Ginger"],
            "family": "Zingiberaceae",
        },
        "maricha": {
            "sanskrit": ["Maricha", "Ushana", "Krishna"],
            "latin": ["Piper nigrum"],
            "hindi": ["Kali Mirch"],
            "english": ["Black Pepper"],
            "family": "Piperaceae",
        },
        "pippali": {
            "sanskrit": ["Pippali", "Magadhi", "Krishna", "Vaidehi"],
            "latin": ["Piper longum"],
            "hindi": ["Pippal", "Peepli"],
            "english": ["Long Pepper"],
            "family": "Piperaceae",
        },
        "arjuna": {
            "sanskrit": ["Arjuna", "Kakubha", "Nadisarja"],
            "latin": ["Terminalia arjuna"],
            "hindi": ["Arjun"],
            "english": ["Arjun Tree"],
            "family": "Combretaceae",
        },
        "bhringaraja": {
            "sanskrit": ["Bhringaraja", "Kesharaja", "Markava"],
            "latin": ["Eclipta alba", "Eclipta prostrata"],
            "hindi": ["Bhringraj"],
            "english": ["False Daisy"],
            "family": "Asteraceae",
        },
        "gokshura": {
            "sanskrit": ["Gokshura", "Ikshugandha", "Shwadamshtra"],
            "latin": ["Tribulus terrestris"],
            "hindi": ["Gokhru"],
            "english": ["Puncture Vine", "Caltrops"],
            "family": "Zygophyllaceae",
        },
        "punarnava": {
            "sanskrit": ["Punarnava", "Shophaghni", "Raktakanda"],
            "latin": ["Boerhavia diffusa"],
            "hindi": ["Punarnava"],
            "english": ["Hogweed", "Spreading Hogweed"],
            "family": "Nyctaginaceae",
        },
        "shankhapushpi": {
            "sanskrit": ["Shankhapushpi", "Kshirapushpi"],
            "latin": ["Convolvulus pluricaulis"],
            "hindi": ["Shankhpushpi"],
            "english": ["Morning Glory"],
            "family": "Convolvulaceae",
        },
        "jatamansi": {
            "sanskrit": ["Jatamansi", "Bhutajata", "Tapasvini"],
            "latin": ["Nardostachys jatamansi"],
            "hindi": ["Jatamansi"],
            "english": ["Spikenard", "Muskroot"],
            "family": "Caprifoliaceae",
        },
        "katuki": {
            "sanskrit": ["Katuki", "Katurohini", "Tikta"],
            "latin": ["Picrorhiza kurroa"],
            "hindi": ["Kutki"],
            "english": ["Kutki"],
            "family": "Plantaginaceae",
        },
        "vidanga": {
            "sanskrit": ["Vidanga", "Krimighna", "Jantunashana"],
            "latin": ["Embelia ribes"],
            "hindi": ["Vaividang", "Baibidang"],
            "english": ["False Black Pepper"],
            "family": "Primulaceae",
        },
        "chitraka": {
            "sanskrit": ["Chitraka", "Agni", "Vahni"],
            "latin": ["Plumbago zeylanica"],
            "hindi": ["Chita", "Chitrak"],
            "english": ["Ceylon Leadwort"],
            "family": "Plumbaginaceae",
        },
        "musta": {
            "sanskrit": ["Musta", "Mustaka", "Abda"],
            "latin": ["Cyperus rotundus"],
            "hindi": ["Nagarmotha"],
            "english": ["Nut Grass"],
            "family": "Cyperaceae",
        },
        "vasa": {
            "sanskrit": ["Vasa", "Vasaka", "Sinhasya"],
            "latin": ["Adhatoda vasica", "Justicia adhatoda"],
            "hindi": ["Adusa", "Arusa"],
            "english": ["Malabar Nut"],
            "family": "Acanthaceae",
        },
        "kantakari": {
            "sanskrit": ["Kantakari", "Nidigdhika", "Kshudra"],
            "latin": ["Solanum xanthocarpum", "Solanum virginianum"],
            "hindi": ["Bhatkataiya"],
            "english": ["Yellow-berried Nightshade"],
            "family": "Solanaceae",
        },
        "bala": {
            "sanskrit": ["Bala", "Vatyayani", "Kharayashtika"],
            "latin": ["Sida cordifolia"],
            "hindi": ["Bariyar", "Kharenti"],
            "english": ["Country Mallow"],
            "family": "Malvaceae",
        },
        "ela": {
            "sanskrit": ["Ela", "Sukshmaila", "Truti"],
            "latin": ["Elettaria cardamomum"],
            "hindi": ["Elaichi"],
            "english": ["Cardamom"],
            "family": "Zingiberaceae",
        },
        "lavanga": {
            "sanskrit": ["Lavanga", "Devakusuma"],
            "latin": ["Syzygium aromaticum"],
            "hindi": ["Laung"],
            "english": ["Clove"],
            "family": "Myrtaceae",
        },
        "twak": {
            "sanskrit": ["Twak", "Darusita", "Varanga"],
            "latin": ["Cinnamomum zeylanicum", "Cinnamomum verum"],
            "hindi": ["Dalchini"],
            "english": ["Cinnamon"],
            "family": "Lauraceae",
        },
        "jatiphala": {
            "sanskrit": ["Jatiphala", "Malati Phala"],
            "latin": ["Myristica fragrans"],
            "hindi": ["Jaiphal"],
            "english": ["Nutmeg"],
            "family": "Myristicaceae",
        },
        "kumari": {
            "sanskrit": ["Kumari", "Ghritakumari", "Kanya"],
            "latin": ["Aloe vera", "Aloe barbadensis"],
            "hindi": ["Ghritkumari", "Gwarpatha"],
            "english": ["Aloe Vera"],
            "family": "Asphodelaceae",
        },
        "nirgundi": {
            "sanskrit": ["Nirgundi", "Sinduvara", "Nilika"],
            "latin": ["Vitex negundo"],
            "hindi": ["Sambhalu", "Nirgundi"],
            "english": ["Five-leaved Chaste Tree"],
            "family": "Lamiaceae",
        },
        "vacha": {
            "sanskrit": ["Vacha", "Ugragandha", "Golomi"],
            "latin": ["Acorus calamus"],
            "hindi": ["Bach", "Ghorvach"],
            "english": ["Sweet Flag"],
            "family": "Acoraceae",
        },
        "kutaja": {
            "sanskrit": ["Kutaja", "Indrayava", "Vatsaka"],
            "latin": ["Holarrhena antidysenterica", "Holarrhena pubescens"],
            "hindi": ["Kurchi", "Kutaj"],
            "english": ["Kurchi"],
            "family": "Apocynaceae",
        },
        "bilva": {
            "sanskrit": ["Bilva", "Shriphala", "Shailusha"],
            "latin": ["Aegle marmelos"],
            "hindi": ["Bel", "Bael"],
            "english": ["Bael", "Wood Apple"],
            "family": "Rutaceae",
        },
        "shalaparni": {
            "sanskrit": ["Shalaparni", "Sthira"],
            "latin": ["Desmodium gangeticum"],
            "hindi": ["Shalparni"],
            "english": ["Ticktrefoil"],
            "family": "Fabaceae",
        },
        "manjistha": {
            "sanskrit": ["Manjistha", "Vikasa", "Raktanga"],
            "latin": ["Rubia cordifolia"],
            "hindi": ["Manjith"],
            "english": ["Indian Madder"],
            "family": "Rubiaceae",
        },
        "daruharidra": {
            "sanskrit": ["Daruharidra", "Darvi", "Pita Daru"],
            "latin": ["Berberis aristata"],
            "hindi": ["Daruhaldi"],
            "english": ["Indian Barberry", "Tree Turmeric"],
            "family": "Berberidaceae",
        },
        "kalmegh": {
            "sanskrit": ["Bhunimba", "Kiratatikta", "Yavatikta"],
            "latin": ["Andrographis paniculata"],
            "hindi": ["Kalmegh"],
            "english": ["King of Bitters", "Green Chiretta"],
            "family": "Acanthaceae",
        },
        "shigru": {
            "sanskrit": ["Shigru", "Shobhanjana", "Akshiva"],
            "latin": ["Moringa oleifera"],
            "hindi": ["Sahjan", "Munga"],
            "english": ["Drumstick", "Moringa"],
            "family": "Moringaceae",
        },
        "kupilu": {
            "sanskrit": ["Kupilu", "Vishatinduka", "Kuchla"],
            "latin": ["Strychnos nux-vomica"],
            "hindi": ["Kuchla"],
            "english": ["Nux Vomica", "Poison Nut"],
            "family": "Loganiaceae",
        },
        "ativisha": {
            "sanskrit": ["Ativisha", "Shringi", "Vishwa"],
            "latin": ["Aconitum heterophyllum"],
            "hindi": ["Atis"],
            "english": ["Indian Atees"],
            "family": "Ranunculaceae",
        },
        "kushtha": {
            "sanskrit": ["Kushtha", "Vyaghi", "Vapya"],
            "latin": ["Saussurea lappa", "Saussurea costus"],
            "hindi": ["Kuth", "Kushta"],
            "english": ["Costus"],
            "family": "Asteraceae",
        },
        "ashoka": {
            "sanskrit": ["Ashoka", "Hemapushpa", "Tamrapallava"],
            "latin": ["Saraca asoca", "Saraca indica"],
            "hindi": ["Ashok"],
            "english": ["Ashoka Tree"],
            "family": "Fabaceae",
        },
        "lodhra": {
            "sanskrit": ["Lodhra", "Rodhra", "Tilvaka"],
            "latin": ["Symplocos racemosa"],
            "hindi": ["Lodh", "Lodhra"],
            "english": ["Lodh Tree"],
            "family": "Symplocaceae",
        },
        "shatapushpa": {
            "sanskrit": ["Shatapushpa", "Madhurika", "Misi"],
            "latin": ["Foeniculum vulgare"],
            "hindi": ["Saunf"],
            "english": ["Fennel"],
            "family": "Apiaceae",
        },
        "jeeraka": {
            "sanskrit": ["Jeeraka", "Ajaji", "Deepya"],
            "latin": ["Cuminum cyminum"],
            "hindi": ["Jeera"],
            "english": ["Cumin"],
            "family": "Apiaceae",
        },
        "methika": {
            "sanskrit": ["Methika", "Deepani", "Bahupatrika"],
            "latin": ["Trigonella foenum-graecum"],
            "hindi": ["Methi"],
            "english": ["Fenugreek"],
            "family": "Fabaceae",
        },
        "vidari": {
            "sanskrit": ["Vidari", "Vidarikanda", "Kroshtri"],
            "latin": ["Pueraria tuberosa"],
            "hindi": ["Vidarikand"],
            "english": ["Indian Kudzu"],
            "family": "Fabaceae",
        },
    }


def build_disease_synonyms() -> dict:
    """Build disease synonym dictionary mapping Ayurvedic ↔ modern terms.

    Keys are canonical lowercase slugs. Each entry lists Ayurvedic disease
    names and their approximate modern biomedical equivalents. Mappings are
    approximate: Ayurvedic nosology does not map one-to-one onto modern
    diagnoses, so these are retrieval aids, not clinical equivalences.
    """
    return {
        "diabetes": {
            "ayurvedic": ["Prameha", "Madhumeha"],
            "modern": ["Diabetes Mellitus", "Type 2 Diabetes", "T2DM"],
        },
        "arthritis": {
            "ayurvedic": ["Amavata", "Sandhivata", "Sandhigata Vata"],
            "modern": ["Rheumatoid Arthritis", "Osteoarthritis"],
        },
        "gout": {
            "ayurvedic": ["Vatarakta"],
            "modern": ["Gout", "Gouty Arthritis"],
        },
        "hypertension": {
            "ayurvedic": ["Raktachapa", "Uchcha Raktachapa"],
            "modern": ["High Blood Pressure", "Hypertension", "HTN"],
        },
        "asthma": {
            "ayurvedic": ["Tamaka Shwasa", "Shwasa Roga"],
            "modern": ["Bronchial Asthma"],
        },
        "cough": {
            "ayurvedic": ["Kasa"],
            "modern": ["Cough", "Bronchitis"],
        },
        "anemia": {
            "ayurvedic": ["Pandu", "Panduroga"],
            "modern": ["Anemia", "Anaemia"],
        },
        "jaundice": {
            "ayurvedic": ["Kamala"],
            "modern": ["Jaundice", "Hepatitis"],
        },
        "constipation": {
            "ayurvedic": ["Vibandha", "Koshtabaddhata"],
            "modern": ["Constipation"],
        },
        "diarrhea": {
            "ayurvedic": ["Atisara"],
            "modern": ["Diarrhea", "Diarrhoea"],
        },
        "malabsorption": {
            "ayurvedic": ["Grahani", "Grahani Roga"],
            "modern": ["Malabsorption Syndrome", "Irritable Bowel Syndrome", "IBS"],
        },
        "indigestion": {
            "ayurvedic": ["Ajirna", "Agnimandya"],
            "modern": ["Indigestion", "Dyspepsia"],
        },
        "hyperacidity": {
            "ayurvedic": ["Amlapitta"],
            "modern": ["Hyperacidity", "Acid Reflux", "GERD"],
        },
        "obesity": {
            "ayurvedic": ["Sthaulya", "Medoroga"],
            "modern": ["Obesity"],
        },
        "skin_disease": {
            "ayurvedic": ["Kushtha", "Twak Roga"],
            "modern": ["Skin Disorders", "Dermatitis", "Eczema"],
        },
        "psoriasis": {
            "ayurvedic": ["Eka Kushtha", "Kitibha"],
            "modern": ["Psoriasis"],
        },
        "fever": {
            "ayurvedic": ["Jwara"],
            "modern": ["Fever", "Pyrexia"],
        },
        "headache": {
            "ayurvedic": ["Shirashula", "Shiroroga"],
            "modern": ["Headache", "Cephalalgia"],
        },
        "migraine": {
            "ayurvedic": ["Ardhavabhedaka"],
            "modern": ["Migraine"],
        },
        "insomnia": {
            "ayurvedic": ["Anidra", "Nidranasha"],
            "modern": ["Insomnia", "Sleeplessness"],
        },
        "epilepsy": {
            "ayurvedic": ["Apasmara"],
            "modern": ["Epilepsy", "Seizure Disorder"],
        },
        "vertigo": {
            "ayurvedic": ["Bhrama"],
            "modern": ["Vertigo", "Dizziness"],
        },
        "hemorrhoids": {
            "ayurvedic": ["Arsha"],
            "modern": ["Hemorrhoids", "Piles"],
        },
        "fistula": {
            "ayurvedic": ["Bhagandara"],
            "modern": ["Anal Fistula"],
        },
        "dysuria": {
            "ayurvedic": ["Mutrakricchra"],
            "modern": ["Dysuria", "Urinary Tract Infection", "UTI"],
        },
        "urinary_calculi": {
            "ayurvedic": ["Ashmari"],
            "modern": ["Urinary Calculi", "Kidney Stone", "Renal Stone"],
        },
        "edema": {
            "ayurvedic": ["Shotha", "Shvayathu"],
            "modern": ["Edema", "Oedema", "Swelling"],
        },
        "worm_infestation": {
            "ayurvedic": ["Krimi", "Krimiroga"],
            "modern": ["Helminthiasis", "Worm Infestation"],
        },
        "tuberculosis": {
            "ayurvedic": ["Rajayakshma", "Kshaya"],
            "modern": ["Tuberculosis", "TB"],
        },
        "bleeding_disorder": {
            "ayurvedic": ["Raktapitta"],
            "modern": ["Bleeding Disorders", "Hemorrhage"],
        },
        "leucorrhea": {
            "ayurvedic": ["Shweta Pradara"],
            "modern": ["Leucorrhea", "Leukorrhea"],
        },
        "menorrhagia": {
            "ayurvedic": ["Asrigdara", "Raktapradara"],
            "modern": ["Menorrhagia"],
        },
        "alopecia": {
            "ayurvedic": ["Khalitya", "Indralupta"],
            "modern": ["Alopecia", "Hair Loss", "Hair Fall"],
        },
    }


def main():
    output_dir = PROJECT_ROOT / "data" / "synonyms"
    output_dir.mkdir(parents=True, exist_ok=True)

    herbs = build_herb_synonyms()
    diseases = build_disease_synonyms()

    with open(output_dir / "herb_synonyms.json", "w", encoding="utf-8") as f:
        json.dump(herbs, f, ensure_ascii=False, indent=2)

    with open(output_dir / "disease_synonyms.json", "w", encoding="utf-8") as f:
        json.dump(diseases, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(herbs)} herb entries to {output_dir / 'herb_synonyms.json'}")
    print(f"Saved {len(diseases)} disease entries to {output_dir / 'disease_synonyms.json'}")


if __name__ == "__main__":
    main()
