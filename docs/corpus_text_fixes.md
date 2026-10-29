# Corpus Text Fixes — Proposal

Status: **code in place, not applied.** Each fix is behind a setting and takes
effect only on the next ingestion. Nothing has been re-ingested.

| Fix | Setting | Default | Needs your OK |
|---|---|---|---|
| 3a. Legacy-font → IAST character map | `apply_font_char_map` | `False` | **yes**: confirm the table below |
| 3a. Diacritic folding in the BM25 tokenizer | `bm25_fold_diacritics` | `False` | turn on together with the char map |
| 3b. Split run-together OCR words (BM25 text only) | `split_glued_ocr_words` | `False` | **yes**: review the samples |
| 3c. Contextual chunk headers (embedding + rerank text) | `contextual_chunk_headers` | `True` | no |
| 3d. Exclude Charaka Samhita | `exclude_charaka` | `True` | no |

---

## 3a. Character mapping

### How it was derived

`python scripts/char_inventory.py [--work API] [--after-map]` lists every
non-ASCII, non-Devanagari character in the indexed corpus by frequency, with
per-work counts and sample words. Mappings come from those samples: a
character is mapped only when the words containing it decode to known IAST
spellings.

**The same byte means different things in different books**, so the maps are
scoped per work. For example, `£` is ū in the Pharmacopoeia (`R£kÀa` = Rūkṣa),
ā in the Sushruta/AH English OCR (`V£yu` = Vāyu), and "g" (grams) in the
Formulary (`24 £.` = 24 g.).

### Ayurvedic Pharmacopoeia of India: legacy 8-bit IAST font

| Char | Count | → | Evidence |
|---|---|---|---|
| `¡` | 6357 | ā | Vip¡ka → Vipāka |
| `À` | 2603 | ṣ | UÀ¸a → Uṣṇa |
| `¸` | 2409 | ṇ | Gu¸a → Guṇa |
| `¢` | 2394 | ī | V¢rya → Vīrya |
| `£` | 1417 | ū | R£kÀa → Rūkṣa |
| `¶` | 1369 | ṭ | Ka¶u → Kaṭu |
| `á` | 1251 | Ś | á¢ta → Śīta; AáOKA → AŚOKA |
| `¤` | 1242 | ṛ | Gh¤ta → Ghṛta |
| `¿` | 997 | ś | A¿vagandh¡ → Aśvagandhā |
| `·` | 362 | ḍ | P¡¸·u → Pāṇḍu |
| `´` | 197 | ṅ | A´gamarda → Aṅgamarda |
| `Æ` | 158 | ṃ | B¤Æha¸a → Bṛṃhaṇa |
| `Å` | 120 | ḥ | áiraÅ → Śiraḥ |
| `®` | ~20 | e | T®j°vati → Tejovati; D®vak¡Àtha → Devakāṣṭha *(medium)* |
| `Ë` | 730 | Ā | AJAGANDHË → AJAGANDHĀ |
| `Ì` | 313 | Ī | ËMALAKÌ → ĀMALAKĪ |
| `â` | 107 | Ṣ | GOKâURA → GOKṢURA |
| `Í` | 99 | Ū | BABBÍLA → BABBŪLA |
| `Û` | 96 | Ṇ | ERAÛÚA → ERAṆḌA |
| `Ù` | 74 | Ṭ | KUâÙHA → KUṢṬHA |
| `Ú` | 50 | Ḍ | GUÚÍCÌ → GUḌŪCĪ |
| `×` | 49 | Ṅ | VIÚA×GA → VIḌAṄGA |
| `Î` | 42 | Ṛ | KÎâÛAJÌRAKA → KṚṢṆAJĪRAKA |
| `é` | 41 | Ḥ | PALĀŚAé → PALĀŚAḤ *(medium; found on re-inventory)* |
| `Ø` | 31 | Ñ | GUØJË → GUÑJĀ |
| `ê` | 14 | Ṃ | HAêSAPADÌ → HAṂSAPADĪ |
| `Ó` | 2 | E | RÓÛUKA → REṆUKA *(low)* |
| `½` | 1 | l | N¡rik®½a → Nārikela *(low)* |

**Context rules** (these characters are also real symbols in the Pharmacopoeia):

| Char | Count | Rule |
|---|---|---|
| `µ` | 831 | → ñ **only between letters** (Karaµja → Karañja, Paµca → Pañca); otherwise kept as micron (`35 µ`, `µm`) |
| `°` | 206 | → o **only between letters** (L°hitapuÀpa → Lohitapuṣpa, á°dhana → Śodhana); otherwise kept as degrees (`105°C`) |
| `ƒÊ` | 2 | → µ (`ƒÊm` is a garbled `µm`) |

**Result on the corpus:** odd characters in the Pharmacopoeia go from **23,895 →
1,222** occurrences. What's left is legitimate: µ (micron), °C, Greek letters in
chemical names, quotes, dashes.

Before / after (`api_all_volume_pdf_40_P0`, the Aśvagandhā monograph):

```
BEFORE  Rasa : Tikta, KaÀ¡ya | Gu¸a : Laghu | V¢rya : UÀ¸a | Vip¡ka : Madhura |
        Karma : V¡takaph¡paha, Balya, Ras¡yana, V¡j¢kara¸a | ... A¿vagandh¡dyariÀ¶a
AFTER   Rasa : Tikta, Kaṣāya | Guṇa : Laghu | Vīrya : Uṣṇa | Vipāka : Madhura |
        Karma : Vātakaphāpaha, Balya, Rasāyana, Vājīkaraṇa | ... Aśvagandhādyariṣṭa
```

### Sushruta Samhita / Ashtanga Hridaya: English OCR

| Char | Rule | Evidence |
|---|---|---|
| `£` | → ā **inside words only** *(medium)* | V£yu → Vāyu, vid£rigandha → vidārigandha, Bh£vaprakdsham |
| U+00AD soft hyphen | remove, with any following space | `our­ selves` → ourselves (831 in SS) |

Everything else in these works is ordinary punctuation (—, ’, “ ”, •) or OCR
noise inside Devanagari pages (`€`, `§`, `‰`, `›`, mainly in AH/Charaka). Noise
isn't a font code, so it's **not mapped**.

### Ayurvedic Formulary of India

The Formulary is otherwise ASCII-transliterated (`Kantakari`, `NagakeSara`).

| Char | Rule | Evidence |
|---|---|---|
| `£` | → g **only right after a quantity** *(medium)* | `bibhitaka (p.) 24 £.` → 24 g. (430 of 465 cases; the other 35 are noise) |

### Required companion change: diacritic folding

The BM25 tokenizer keeps only `[a-z0-9]` runs, so after decoding, `Aśvagandhā`
would tokenize to `['vagandh']`. `bm25_fold_diacritics` folds Latin diacritics
(ā→a, ś→s) before tokenizing, giving `['asvagandha']`. Devanagari is left
untouched: its vowel signs are combining marks too, and folding them would
corrupt the text.

**To confirm:** the table above, especially the *medium* and *low* rows. Then set
`APPLY_FONT_CHAR_MAP=true` and `BM25_FOLD_DIACRITICS=true` before re-ingesting.
