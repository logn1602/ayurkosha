# Eval Relabel Review

**Status: reviewed by logn1602 on 2026-10-29. All 30 rows approved**, eval_003 and eval_008 after
a re-check (see the section below). Every row carries provenance
`agent-proposed from corpus text, human-reviewed` with `reviewed_by: logn1602`. Labels follow
[`LABELING_CRITERIA.md`](LABELING_CRITERIA.md) **v2**.

Reviewer decisions so far (these are the reviewer's, not row approvals):
- The **v2 Formulary rule**
  (for treatment/management questions, the Formulary is gold when it has formulation monographs
  indicated for the disease). 7 rows were re-checked and gained `afi` under it; `eval_024`
  stays Sushruta-only because the question names Sushruta.
- `eval_017` was reworded by the reviewer to "Which classical formulations are indicated for Amavata?" (gold: Formulary).
- All other rows are the agent's v1 proposals, approved in the reviewer's row review on 2026-10-29.
- eval_003 and eval_008 were re-checked at the reviewer's request and decided as recorded below.
- Evidence came from plain text search of the corpus (parent chunks), never from retrieval or eval
  output. Formulary evidence is a monograph whose title and "Important therapeutic uses" list sit in
  the same chunk.
- Supporting ids are **parent chunk ids**, also stored per item in `provenance.supporting_chunk_ids`.
- **19/30** questions changed label versus the original (bm25-keyword-evidence) set.

| ID | Question | Previous gold | Applied gold | Reason | Supporting chunk ids | Notes |
|---|---|---|---|---|---|---|
| eval_001 | What are the Rasa, Guna, Virya, and Vipaka of Ashwagandha? | afi, api | api | API monograph gives Rasa/Guna/Vīrya/Vipāka/Karma; AFI only lists it as an ingredient; no classical work describes its properties. | `api_all_volume_pdf_40_P0` |  |
| eval_002 | What are the Rasa, Guna, Virya, and Vipaka of Bibhitaka? | api | api, ashtanga_hridaya | API monograph + AH Sūtrasthāna dravya section gives Vibhītakī rasa/guna/vīrya/vipāka; AFI only uses it as an ingredient. | `api_all_volume_pdf_57_P0`<br>`ashtanga_hridaya_vidyanath_illustrated_pdf_163_P0` | SS vol1 p535 describes Vibhītaka *oil*, not the fruit. |
| eval_003 | What are the properties and therapeutic actions of Pippali? | afi, sushruta | api, ashtanga_hridaya, sushruta **(re-checked)** | API monograph + AH gives Pippalī (fresh/dry) rasa/guna/vīrya/vipāka; SS only ranks it "best of pungents"; AFI is ingredient lists. | `api_all_volume_pdf_959_P0`<br>`ashtanga_hridaya_vidyanath_illustrated_pdf_164_P0`<br>`ashtanga_hridaya_vidyanath_illustrated_pdf_488_P0`<br>`sushruta_samhita_vol_1_pdf_599_P0` | Reviewer re-check: SS Sūtrasthāna 46 p599 gives Pippalī fresh vs dried properties, so `sushruta` was added. |
| eval_004 | What are the therapeutic actions of Punarnava? | afi | api | API Rakta/Śveta-punarnavā monographs give properties and karma; others only mention it in groups or recipes. | `api_all_volume_pdf_724_P0`<br>`api_all_volume_pdf_1295_P1` | SS vol1 p604 gives potency/taste of Punarnavā *leaves* jointly with other pot-herbs (group-level). |
| eval_005 | What is the classical action of Brahmi described as Medhya? | afi | api, sushruta | API Brāhmī karma lists Medhya; SS Cikitsā Brāhmī-ghṛta rasāyana describes the memory/intellect-promoting action. | `api_all_volume_pdf_278_P0`<br>`sushruta_samhita_vol_2_pdf_580_P0` |  |
| eval_006 | What are the properties of Gokshura and its action on the urinary system? | sushruta, api | api | API Gokṣura (root, fruit) monographs give properties and urinary karma (mūtrakṛcchra, aśmarīhara, vastiśodhana). | `api_all_volume_pdf_78_P0`<br>`api_all_volume_pdf_80_P0` | AH p166/p488 give properties of laghu-pañcamūla as a group, Gokṣura included. |
| eval_007 | What are the properties and actions of Guduchi? | sushruta | api | API Guḍūcī monograph gives properties and karma; SS/AH only name it in groups and recipes. | `api_all_volume_pdf_84_P0` | SS vol1 p607: bitter taste/doṣa action of a group of herbs incl. Guḍūcī. |
| eval_008 | What are the properties and actions of Shatavari? | sushruta, api | api, sushruta **(re-checked)** | API Śatāvarī monograph; SS Sūtrasthāna 46 gives Śatāvarī-specific taste and action. | `api_all_volume_pdf_984_P0`<br>`sushruta_samhita_vol_1_pdf_614_P0` | Reviewer re-check, option (a): SS p614 describes the root (Bulb group), so it stays in; AH p149 describes only the sprouts, so it stays out. |
| eval_009 | What are the Rasa and Vipaka of Haritaki? | afi, sushruta | api, ashtanga_hridaya | API Harītakī monograph + AH dravya list gives Harītakī rasa and madhura vipāka explicitly. | `api_all_volume_pdf_93_P0`<br>`ashtanga_hridaya_vidyanath_illustrated_pdf_487_P0` | SS vol1 p503 gives the collective taste of Triphalā, not Harītakī alone. |
| eval_010 | What are the ingredients and indications of Yogaraja Guggulu? | afi | afi | AFI monograph gives ingredients, dose and therapeutic uses; API only lists it as an "important formulation". | `afi_part1_pdf_121_P0` |  |
| eval_011 | What are the ingredients and dose of Amavatari Rasa? | afi | afi | AFI monograph (Bhaiṣajya Ratnāvalī, Āmavātādhikāra) gives ingredients and dose; no other work has it. | `afi_part2_pdf_234_P0` |  |
| eval_012 | What are the ingredients of Sitopaladi Churna and what is it used for? | afi, sushruta | afi | AFI monograph gives ingredients and uses; SS never mentions it (later Śārṅgadhara formulation); API only lists the name. | `afi_part1_pdf_168_P0` |  |
| eval_013 | What is Kaishora Guggulu used for? | sushruta, afi | afi | AFI monograph gives ingredients and uses; SS never mentions it (Bhaiṣajya Ratnāvalī formulation). | `afi_part1_pdf_119_P0` |  |
| eval_014 | What is the principal herb and indication of Rasnadi Kwatha Churna? | afi | afi | AFI gives Rāsnādi Kvātha Cūrṇa (Sahasrayoga) with Rāsnā as the lead ingredient, plus the Mahā variant. | `afi_part1_pdf_112_P0` |  |
| eval_015 | What is Vyoshadi Guggulu indicated for? | sushruta, afi | afi | AFI monograph gives ingredients and uses; its source (AH Cikitsā 21) is not in the English AH volumes; SS never mentions it. | `afi_part1_pdf_122_P0` | AH p262 "Vyoṣādi yoga" is a different obesity preparation. |
| eval_016 | What are the three ingredients of Triphala and its uses? | sushruta, afi | afi, sushruta | AFI Triphalā Cūrṇa gives ingredients, dose and uses; SS defines the Triphalā group and its actions. | `afi_part1_pdf_162_P0`<br>`sushruta_samhita_vol_1_pdf_442_P0`<br>`sushruta_samhita_vol_1_pdf_503_P0` | AH p62 lists Triphalā ingredients only as a tooth-cleaning paste. |
| eval_017 | Which classical formulations are indicated for Amavata? | afi | afi **(reworded)** | Reworded by reviewer. AFI monographs list Āmavāta in their therapeutic uses: Āmavātāri Rasa, Rāsnādi Kvātha Cūrṇa (4:27; its uses list is in the next chunk), Vātāri Guggulu, Vāsāguḍūcyādi Kvātha Cūrṇa, Vyoṣādi Guggulu, Ānandabhairava Rasa, Nimbādi Cūrṇa. | `afi_part2_pdf_234_P0`<br>`afi_part1_pdf_112_P1`<br>`afi_part1_pdf_122_P1`<br>`afi_part1_pdf_113_P0`<br>`afi_part1_pdf_122_P0`<br>`afi_part1_pdf_310_P0`<br>`afi_part1_pdf_164_P0` | Yogarāja Guggulu (p121) is drawn from Bhaiṣajya Ratnāvalī's Āmavātādhikāra, but its uses line is OCR-garbled, so it isn't cited. |
| eval_018 | What is the initial line of treatment for Jwara (fever) in Ayurveda? | sushruta | sushruta, afi **(v2 rule)** | SS Uttara-tantra 39 gives the general line of fever treatment incl. fasting (laṅghana) and when it is prohibited. AFI: formulations indicated for Jvara (e.g. Amrtarista, Vasavaleha) count under the v2 rule. | `sushruta_samhita_vol_3_pdf_203_P0`<br>`sushruta_samhita_vol_3_pdf_204_P0`<br>`afi_part1_pdf_58_P0`<br>`afi_part1_pdf_97_P1` | AFI/API list Jvara only as an indication. AFI added by the v2 rule (question asks for treatment). |
| eval_019 | How is Prameha classified and managed in Ayurveda? | api | sushruta, afi **(v2 rule)** | SS Nidāna 6 classifies Prameha; SS Cikitsā 11–12 gives management; API only lists it as a therapeutic use. AFI: formulations indicated for Prameha (e.g. Triphala Curna, Rasasindura) count under the v2 rule. | `sushruta_samhita_vol_2_pdf_100_P0`<br>`sushruta_samhita_vol_2_pdf_427_P0`<br>`sushruta_samhita_vol_2_pdf_434_P0`<br>`afi_part1_pdf_162_P0`<br>`afi_part1_pdf_264_P0` |  |
| eval_020 | What is the cause and treatment of Grahani in Ayurveda? | afi, sushruta | sushruta, afi **(v2 rule)** | SS Uttara-tantra 40 gives causes, doṣa types, treatment and diet for Grahaṇī; AFI only lists it as an indication. AFI: formulations indicated for Grahaṇī (e.g. Nyagrodhadi Kvatha Curna, Patolamuladi Kvatha Curna) count under the v2 rule. | `sushruta_samhita_vol_3_pdf_256_P0`<br>`sushruta_samhita_vol_3_pdf_257_P0`<br>`afi_part1_pdf_109_P0`<br>`afi_part1_pdf_109_P1` |  |
| eval_021 | How is Atisara (diarrhoea) treated according to its stage? | afi, sushruta | sushruta, afi **(v2 rule)** | SS Uttara-tantra 40 gives the types and stage-wise treatment of Atisāra (incl. āma); AFI only lists it as an indication. AFI: formulations indicated for Atisāra (e.g. Mustakaranjadi Kvatha Curna, Balacaturbhadrika Curna) count under the v2 rule. | `sushruta_samhita_vol_3_pdf_253_P0`<br>`afi_part1_pdf_112_P0`<br>`afi_part1_pdf_165_P1` |  |
| eval_022 | What is the Ayurvedic approach to Pandu (anaemia)? | afi | sushruta, afi **(v2 rule)** | SS Uttara-tantra 44 (Pāṇḍu-roga pratiṣedha) gives etiology and treatment; AFI only lists it as an indication. AFI: formulations indicated for Pāṇḍu (e.g. Draksavaleha, Punarnavadi Kvatha Curna) count under the v2 rule. | `sushruta_samhita_vol_3_pdf_290_P0`<br>`sushruta_samhita_vol_3_pdf_296_P0`<br>`afi_part1_pdf_92_P1`<br>`afi_part1_pdf_110_P0` |  |
| eval_023 | How is Kasa (cough) treated in Ayurveda? | afi, sushruta | sushruta, afi **(v2 rule)** | SS Uttara-tantra 52 (Kāsa pratiṣedha) gives etiology, classification and treatment. AFI: formulations indicated for Kāsa (e.g. Vasavaleha, Punarnavadi Kvatha Curna) count under the v2 rule. | `sushruta_samhita_vol_3_pdf_347_P0`<br>`afi_part1_pdf_97_P1`<br>`afi_part1_pdf_110_P0` | AH p91 covers suppressing the urge to cough, not treating Kāsa. |
| eval_024 | What are the four therapeutic modalities for Arsha (haemorrhoids) in Sushruta? | sushruta, ashtanga_hridaya | sushruta | SS Cikitsā 6 names the four modalities (medicine, kṣāra, cautery, surgery); the question is Sushruta-specific. | `sushruta_samhita_vol_2_pdf_371_P0` | AH p449 describes only kṣāra application in Arśas. |
| eval_025 | How is Kushtha (skin disease) managed in classical Ayurveda? | sushruta | sushruta, afi **(v2 rule)** | SS Nidāna 5 classifies Kuṣṭha; SS Cikitsā 9–10 gives management (e.g. khadira regimen); AFI only lists it as an indication. AFI: formulations indicated for Kuṣṭha (e.g. Patolamuladi Kvatha Curna, Kancanara Guggulu) count under the v2 rule. | `sushruta_samhita_vol_2_pdf_415_P0`<br>`sushruta_samhita_vol_2_pdf_416_P0`<br>`afi_part1_pdf_109_P1`<br>`afi_part1_pdf_119_P0` |  |
| eval_026 | What is Vamana Karma and when is it indicated? | ashtanga_hridaya | ashtanga_hridaya, sushruta | AH Sūtrasthāna 18 lists the indications for emesis; SS Cikitsā 33 gives the vamana procedure and indications. | `ashtanga_hridaya_vidyanath_illustrated_pdf_311_P0`<br>`sushruta_samhita_vol_2_pdf_621_P0` |  |
| eval_027 | What is Virechana Karma and what does it eliminate? | ashtanga_hridaya | ashtanga_hridaya, sushruta | AH Sūtrasthāna 18 defines virecana and what it eliminates; SS Cikitsā 33 gives the purgation procedure. | `ashtanga_hridaya_vidyanath_illustrated_pdf_310_P0`<br>`sushruta_samhita_vol_2_pdf_625_P0` |  |
| eval_028 | Why is Basti considered the foremost treatment for Vata? | sushruta | sushruta, ashtanga_hridaya | SS Cikitsā 35 holds vasti the best of all measures and explains why; AH Sūtrasthāna 1 names vasti the best treatment for Vāta. | `sushruta_samhita_vol_2_pdf_645_P0`<br>`ashtanga_hridaya_vidyanath_illustrated_pdf_53_P0` |  |
| eval_029 | What is Nasya Karma and for which disorders is it used? | ashtanga_hridaya, sushruta | ashtanga_hridaya, sushruta | AH Sūtrasthāna 20 gives the nasya types and indications; SS Cikitsā 40 gives the kinds of nasya and doses. | `ashtanga_hridaya_vidyanath_illustrated_pdf_345_P0`<br>`sushruta_samhita_vol_2_pdf_714_P0` |  |
| eval_030 | What does Dinacharya (daily regimen) include in Ayurveda? | ashtanga_hridaya, sushruta | ashtanga_hridaya, sushruta | AH Sūtrasthāna 2 (Dinacaryā) and SS Cikitsā 24 (hygiene: tooth-brushing, collyrium, etc.) both cover the daily regimen. | `ashtanga_hridaya_vidyanath_illustrated_pdf_62_P0`<br>`sushruta_samhita_vol_2_pdf_535_P0`<br>`sushruta_samhita_vol_2_pdf_536_P0` | SS never uses the word "dinacharya" but covers the topic in full. |

## Re-check requested by the reviewer: eval_003, eval_008 (decided 2026-10-29)

Both re-checks are in Sushruta Sūtrasthāna ch. 46 (vol 1, pp. 558–660), found by plain text search.

**eval_003 (Pippalī, properties).** Present. In the "spices and herbs" group, p599
(`sushruta_samhita_vol_1_pdf_599_P0`): *"the unripe or immature Pippali is heavy of digestion,
sweet in taste, cooling in potency and generates Kapham. Dried Pippali subdues the Vayu and Kapham,
acts as a spermatopoietic and slightly soothes the Pittam."* This is a Pippalī-specific fresh-vs-dry
entry, the same kind as AH p164/p488. Per the reviewer's rule, the action would be to **add
`sushruta`** with that chunk id.

**eval_008 (Śatāvarī, properties).** The SS passage (pp613–614, `sushruta_samhita_vol_1_pdf_614_P0`)
is in **"The Bulb Group … edible bulbous plants (Kandas)"** and describes the **root (tuber)**:
*"The Shatavari has a sweet and bitter taste and is spermatopoietic. It subdues the Vayu and Pittam,
the one belonging to the large-sized species being palatable and appetising and tonic. The latter
improves the intellect and proves curative in cases of mesenteric diarrhoea (Grahani) and piles, and
is spermatopoietic, rejuvenating, restorative, and cooling in its potency."* One more sentence covers
the sprouts: *"The under-sprouts of this creeper (large-sized Shatavari) have a bitter taste and subdue
the Pittam and Kapham."* AH p149 (`ashtanga_hridaya_vidyanath_illustrated_pdf_149_P0`) is
**sprouts only**, as a vegetable: *"Sprouts of satavari … tikta rasa and aphrodisiac … mitigates all the
three dosas."*

So the two passages aren't the same case: SS describes the root, the part the API monograph covers
("Satavari (Rt.)"), plus a sentence on sprouts; AH describes only the sprouts. Options:
(a) keep as proposed, SS in (root) and AH out (sprouts); (b) both in (diet-chapter descriptions
count); (c) both out (diet-chapter food descriptions don't count).

## Complete Formulary supporting sets (v2-rule rows and eval_017)

Every AFI monograph whose title and "therapeutic uses" list sit in the same parent chunk, with the
list naming the disease. Plain text search over the parent store with the Formulary char map applied.
Titles are the upper-case run after "N:M", since OCR often drops the "(" that follows. A uses list ends
at its first full stop, ignoring abbreviation stops in parentheses. These replace the AFI ids each row
cited before; non-AFI ids (Sushruta passages) are kept.

| ID | Disease | AFI chunks | AFI monographs | Other supporting ids |
|---|---|---|---|---|
| eval_017 | Amavata | 9 | 9 | 0 |
| eval_018 | Jvara | 60 | 59 | 2 |
| eval_019 | Prameha | 18 | 19 | 3 |
| eval_020 | Grahani | 30 | 30 | 2 |
| eval_021 | Atisara | 26 | 26 | 1 |
| eval_022 | Pandu | 32 | 32 | 2 |
| eval_023 | Kasa | 41 | 42 | 1 |
| eval_025 | Kustha | 19 | 20 | 2 |

A chunk can hold two monographs, so chunks can number fewer than monographs. Monographs per question:

- **eval_017 (Amavata)**: Amavatari Rasa, Anandabhairava Rasa, Brhat Saindhavadya Taila, Draksadi Gutika, Nimbadi Curna, Svarnabhupati Rasa, Vasaguducyadi Kvatha Curna, Vatari Guggulu, Vyosadi Guggulu
- **eval_018 (Jvara)**: Abhaya Vat, Amrtarista, Anandabhairava Rasa, Astangavaleha, Bharngyadi Kvatha Curna, Brhat Guduci Taila, Brhat Vangesvara Rasa, Candanadi Lauha, Devadarvad, Garbha Cintamani Rasa, Gojihvadi Kvatha Curna, Guducyadi Gana Kvatha Curna, Hemagarbha Pottal, Hiranya Garbha Pottali Rasa, Hrdyavirecana Leha, Jvaraghni Gutika, Jvarankusa Rasa, Jvararyabhra, Kadali Ksara, Kanakasundara Rasa, Kasturi Bhairava Rasa, Kumarakalyana Rasa, Kutajaghana Vat, Laghu Malinivasanta Rasa, Maha Jvarankusa Rasa, Mahalaksadi Taila, Mrtyunjaya Rasa, Muktapancamrta Rasa, Nagarjunabhra Rasa, Nimbadi Kvatha Curna, Pacanamrta Kvatha Curna, Patolamuladi Kvatha Curna, Phalatrikadi Kvatha Curna, Prabhakara Rasa, Pranada Gutika, Pratapalankesvara Rasa, Pusyanuga Curna, Rajanyadi Curna, Rasamanikya, Sadanga Kvatha Curna, Samsamani Vat, Saptamrta Lauha, Satamulyadi Lauha, Satpala Ghrta, Saubhagya Vati, Sri Jayamangala Rasa, Srngarabhra Rasa, Srngyadi Curna, Svacchanda Bhairava Rasa, Svarnabhupati Rasa, Triphala Curna, Vasanta Malati Rasa, Vasanta Tilaka Rasa, Vasavaleha, Vatagnikumara Rasa, Vyaghri Taila, Yakrdari Lauha, Yakrtplihari Lauha, Yogaraja
- **eval_019 (Prameha)**: Anandabhairava Rasa, Brhat Vangesvara Rasa, Caturbhuja Rasa, Hemanatha Rasa, Kancanabhra Rasa, Mandura Vataka, Mutrasangrahaniya Kasaya Curna, Narasimha Curna, Pancanana Rasa, Rasasindura, Srngarabhra Rasa, Svarnabhupati Rasa, Tamra Parpat, Trikatu Curna, Triphala Curna, Tuvaraka Taila, Vasanta Tilaka Rasa, Yasada Bhasma, Yogaraja
- **eval_020 (Grahani)**: Brhadagnikumara Rasa, Brhat Gangadhara Curna, Brhat Vangesvara Rasa, Grahani Kapata Rasa, Hiranya Garbha Pottali Rasa, Kadali Ksara, Kanakasundara Rasa, Kravyada Rasa, Kutajaghana Vat, Mahagandhaka Vati, Mahasankha Vati, Mutrasangrahaniya Kasaya Curna, Nrpativallabha Rasa, Nyagrodhadi Kvatha Curna, Palasa Ksara, Patolamuladi Kvatha Curna, Pratapalankesvara Rasa, Pravala Pancamrta Rasa, Rajanyadi Curna, Satpala Ghrta, Sulaharana Yoga, Sutasekhara Rasa, Svarnabhupati Rasa, Tamra Parpat, Taramandura Guda, Tiktaka Ghrta, Varatika Bhasma, Vasa Ksara, Vasanta Tilaka Rasa, Yasada Bhasma
- **eval_021 (Atisara)**: Anandabhairava Rasa, Bhuvanesvara Vat, Brhat Gangadhara Curna, Brhat Vangesvara Rasa, Devadarvad, Dhanyapancaka Kvatha Curna, Hiranya Garbha Pottali Rasa, Jvarankusa Rasa, Kanakasundara Rasa, Kravyada Rasa, Kumarakalyana Rasa, Kutajaghana Vat, Kutajastaka Kvatha Curna, Laghu Malinivasanta Rasa, Mahagandhaka Vati, Mukta Pisti, Mustakaranjadi Kvatha Curna, Nagarjunabhra Rasa, Pancanana Rasa, Pratapalankesvara Rasa, Pravala Pancamrta Rasa, Pusyanuga Curna, Rajanyadi Curna, Sulaharana Yoga, Sutasekhara Rasa, Vatsakadi Kvatha Curna
- **eval_022 (Pandu)**: Abhaya Vat, Brhadagnikumara Rasa, Brhat Vangesvara Rasa, Caturbhuja Rasa, Dasamulasatpalaka Ghrta, Dhatri Lauha, Draksavaleha, Dugdha Vat, Hiranya Garbha Pottali Rasa, Hutabhugadi Curna, Kantavallabha Rasa, Mandura Vataka, Manikya Rasa, Narasimha Curna, Navayasa Lauha, Nimbadi Curna, Nrpativallabha Rasa, Pancanana Rasa, Punarnavadi Kvatha Curna, Rajanyadi Curna, Rasasindura, Rasnairandadi Kvatha Curna, Samsamani Vat, Satpala Ghrta, Srngarabhra Rasa, Svarnabhupati Rasa, Tamra Parpat, Taramandura Guda, Tiktaka Ghrta, Vasanta Tilaka Rasa, Yakrtplihari Lauha, Yogaraja
- **eval_023 (Kasa)**: Agnimukha Curna, Akika Bhasma, Akika Pisti, Ardraka Khanda Avaleha, Astangavaleha, Brhat Guduci Taila, Chagaladya Ghrta, Devadarvad, Eladi Curna, Gojihvadi Kvatha Curna, Hemanatha Rasa, Hiranya Garbha Pottali Rasa, Jvararyabhra, Kancanabhra Rasa, Kantavallabha Rasa, Karpuradi Curna, Khadiradi Gutika, Kumarakalyana Rasa, Mahalaksadi Taila, Mrdvikadi Lehya, Muktapancamrta Rasa, Narasimha Curna, Plihari Vatika, Pravala Pancamrta Rasa, Punarnavadi Kvatha Curna, Pusyanuga Curna, Rajanyadi Curna, Satpala Ghrta, Saubhagya Vati, Srngarabhra Rasa, Srngyadi Curna, Sutasekhara Rasa, Svarnabhupati Rasa, Svasa Kasa Cintamani Rasa, Trikatu Curna, Vasa Ksara, Vasanta Tilaka Rasa, Vasavaleha, Vyaghri Haritaki, Vyaghri Taila, Yakrdari Lauha, Yogaraja
- **eval_025 (Kustha)**: Brahmi Ghrta, Kancanara Guggulu, Kasisadi Ghrta, Kustharaksasa Taila, Mandura Vataka, Manikya Rasa, Maricadya Taila, Narasimha Curna, Navayasa Lauha, Nimbadi Curna, Pancanana Rasa, Pathyadi Lepa, Patolamuladi Kvatha Curna, Svarnabhupati Rasa, Tamra Parpat, Tiktaka Ghrta, Trikatu Curna, Triphala Curna, Tuvaraka Taila, Yogaraja

**Correction (eval_017).** The earlier citation of `afi_part1_pdf_112_P1` as "Mahā Rāsnādi Kvātha Cūrṇa"
was wrong. In that chunk the "amavata; vataroga" uses list comes *before* the 4:28 RASNADI KVATHA CURNA
(MAHA) title, so it belongs to 4:27 Rasnadi Kvatha Curna, whose title is in the previous chunk. It
falls outside the same-chunk rule and out of the set, and the gold answer now names Rasnadi Kvatha
Curna instead.

### Decisions (reviewer, 2026-10-29)

- **eval_003:** add `sushruta`, supported by `sushruta_samhita_vol_1_pdf_599_P0` (the fresh vs dried
  Pippalī entry). Gold is now api, ashtanga_hridaya, sushruta.
- **eval_008:** option (a). Sushruta stays in: its Sūtrasthāna 46 passage describes Śatāvarī's root
  (the tuber in the Bulb group: taste, potency, rasāyana, medhya, grahaṇī/arśas), the same part the
  Pharmacopoeia monograph covers. AH p149 stays out: it describes only the sprouts eaten as a
  vegetable, not the drug. Gold stays api, sushruta.
- Both rows are now `human-reviewed`, `reviewed_by: logn1602`.
