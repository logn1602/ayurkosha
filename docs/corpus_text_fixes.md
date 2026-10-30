# Corpus Text Fixes — Proposal

Status: **approved 2026-10-29; all fixes on by default.** They take effect on the
next ingestion (`scripts/reingest.py`). Nothing has been re-ingested yet.

| Fix | Setting | Default |
|---|---|---|
| 3a. Legacy-font → IAST character map | `apply_font_char_map` | `True` (approved) |
| 3a. Diacritic folding + romanization keys (BM25 docs, queries, synonym lookups) | `bm25_fold_diacritics` | `True` (approved) |
| 3b. Split run-together OCR words (BM25 text only) | `split_glued_ocr_words` | `True` (approved) |
| 3c. Contextual chunk headers (embedding + rerank text) | `contextual_chunk_headers` | `True` |
| 3d. Exclude Charaka Samhita | `exclude_charaka` | `True` |
| 3d. Exclude AH Srikantha Murthy vol 1 / Sanskrit commentaries | `exclude_ah_srikantha_murthy`, `exclude_ah_sanskrit_commentaries` | `True` |

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

### Romanization keys (added when folding was enabled)

Folding alone doesn't make "Ashwagandha" match "Aśvagandhā": the synonym
dictionaries are popular romanization ("Ashwagandha", "Shatavari", "Guduchi"),
while folded IAST and the Formulary's ASCII write "asvagandha", "satavari",
"guduci". `src/utils/transliterate.romanization_key` collapses the popular-vs-IAST
letter choices (sh/s, ch/c, w/v, ri/ṛ, doubled vowels):

```
ashwagandha / asvagandha / aśvagandhā  -> asvagandha
shatavari   / satavari   / śatāvarī    -> satavar
guduchi     / guduci     / guḍūcī      -> guduci
```

With `bm25_fold_diacritics` on:
- the tokenizer adds the key after each Latin token, for documents and queries
  alike (both go through `tokenize_ayurvedic`);
- synonym-dictionary variants are folded and keyed the same way;
- `get_synonyms` also looks terms up by key, so "asvagandha" finds the
  "Ashwagandha" entry.

**Keys are for Sanskrit-like tokens only.** Applied to plain English, the same
rules merge unrelated words (ship/sip, wine/vine, shore/sore, food/fud). So a
token gets a key only if it was written with IAST diacritics, is a
Sanskrit/Hindi/Ayurvedic term from the synonym dictionaries, or isn't among
the 50,000 most frequent English words (wordninja's list:
`transliterate.english_words`). That list holds 32 of 34 common collision
words but only 6 of 54 Sanskrit terms checked. Of those six, pandu, rasa and pitta
key to themselves; krishna is a dictionary term, so it's keyed anyway; and
shiva/chakra aren't medical terms. The rule is
`synonym_loader.wants_romanization_key`, used for documents, queries and
dictionary lookups alike. One more guard: an *unrecognized* word (neither
dictionary Sanskrit nor written with diacritics, e.g. an OCR form like
"braches") keeps its key only if the key isn't itself a common English word
("braces"). The simpler of the two options was chosen: restricting keys rather
than indexing romanized forms as a separate BM25 field.

BM25 vocabulary on the 22,718 chunks that will be indexed:

| Key rule | Vocab | Tokens | Keys landing on an English word |
|---|---|---|---|
| Folding only, no keys | 90,937 | 1,262,040 | — |
| Keys on every token (b1b7330) | 104,396 | 1,498,929 | merges **329** English pairs (ache/ace, arch/arc, …) |
| Sanskrit-like tokens only (d76eb1d) | 102,084 | 1,375,500 | 108 (unrecognized words, e.g. braches→braces) |
| **+ unrecognized-word guard (current)** | **101,986** | **1,371,577** | **12**, all from diacritic or dictionary words (keyed by design) |

`tests/test_romanization.py` pins this down: an "Ashwagandha" query retrieves a
chunk that only says "Aśvagandhā" (and doesn't with folding off), while "ship"
does not match "sip", and wine, shore, food and teeth get no key.

**Approved 2026-10-29** with no exceptions; both settings now default to `True`.

---

## 3b. Splitting run-together OCR words (BM25 text only)

### Where the problem is

Measured per source (`text_cleanup.glued_run_ratio`: share of letter runs of 15+ chars):

| Source | Glued runs | Latin text inside glued runs |
|---|---|---|
| sushruta_samhita_vol_1.pdf | **51.3%** | **85%** |
| sushruta_samhita_vol_2.pdf | **46.0%** | **83%** |
| sushruta_samhita_vol_3.pdf | 0.0% | 0% |
| afi_part1/2.pdf | 1.4–1.5% | 4–5% |
| api_all_volume.pdf | 0.2% | 1% |
| ashtanga_hridaya_vidyanath_illustrated.pdf | 0.3% | 1% |

Vols 1–2 hold Sushruta's Sūtra-, Nidāna-, Śārīra- and Cikitsā-sthāna, which is
where 14 of the proposed gold labels point (`data/eval/relabel_review.md`).

### Method (`text_cleanup.GluedWordSplitter`)

1. **Language model** = wordninja's English frequency list merged with a
   **protected vocabulary** learned from the corpus's properly spaced sources
   (glued-run ratio ≤ 5%) plus the synonym dictionaries: 14,530 words, mostly
   Sanskrit/IAST terms (folded to ASCII). Glued sources never teach vocabulary,
   so fragments like "andthe" can't become words.
2. Letter runs are first cut at lowercase→Uppercase boundaries. The translation
   capitalizes Sanskrit names, so a case change marks a word start.
3. Only runs of 8+ characters that aren't already known words are candidates.
4. **Short capitalized words** (< 15 chars) are treated as names and kept whole,
   unless they open with a glued function word ("Amedicated" → "A medicated")
   or end with one ("Indivaraand" → "Indivara and").
5. Pieces the model isn't confident about are glued back to their unknown
   neighbours, so unrecognized Sanskrit stays whole ("Prithak", not "Pr it hak").
   A split is kept only when known words cover ≥ 60% of the run, or exactly one
   word-sized gap remains.

Only `bm25_text` changes. `text` (display, citations, embeddings, rerank) is
untouched.

### Results on the corpus

| Source | Glued-run ratio | Synonym-dictionary terms found as BM25 tokens | Time |
|---|---|---|---|
| Sushruta vol 1 | 51.4% → **0.1%** | 405 → **2,073** | 9.3s |
| Sushruta vol 2 | 46.0% → **0.1%** | 719 → **3,024** | 12.8s |
| Sushruta vol 3 (control: already spaced) | 0.0% → 0.0% | 2,138 → 2,142 | 0.5s |
| Pharmacopoeia (control) | 0.3% → 0.0% | 5,583 → 5,610 | 1.1s |

### Before / after samples

`sushruta_samhita_vol_2_pdf_371_P0` (Arśas, four modalities: gold for eval_024)
```
BEFORE: CHAPTERVI.NowweshalldiscourseonthemedicaltreatmentofHaemorrhoids(Arsas).i . Theremedialmeasuresin
        haemorrhoidsmaybegroupedunderfoursubheads;namely,theemploymentof(active)medicinalremedies,...
AFTER:  CHAPTERVI.Now we shall discourse on the medical treatment of Haemorrhoids(Arsas).i . The remedial
        measures in haemorrhoids maybe grouped under four subheads;namely,the employment of(active)
        medicinal remedies,the application"^of an alkali(into the seat of the disease),actual cauterization
        (of the polyp ii)and surgical operation.
```

`sushruta_samhita_vol_1_pdf_614_P0` (Sanskrit names must survive)
```
BEFORE: Pindaluka,Madhviluka,Hastyaluka,KastMluka,ShankhSluka,Rakteluka,IndivaraandUtpalaetc.alleviatehaemoptysis,
        arecoolingintheirpotency,sweetintheirtasteandheavyofdigestion.Theytendtoincreasethesemen...
AFTER:  Pindaluka,Madhviluka,Hastyaluka,Kast Mluka,Shankh Sluka,Rakteluka,Indivara and Utpala etc.alleviate
        haemoptys is,are cooling in their potency,sweet in their taste and heavy of digestion.They tend to
        increase the semen...
```

`sushruta_samhita_vol_1_pdf_423_P0` (OCR-garbled names in a list)
```
BEFORE: AmedicatedGhritam,preparedwiththePrithak-parni,Atmagupbt,Haridra,Daruharidra,Malati,Sita,anddrugs
        belongingtotheIvdkolyadigroup,isrenownedforitshealingproperties.AmedicatedoilpreparedwithKjtldnusari,
AFTER:  A medicated Ghritam,prepared with the Prithak-parni,Atmagupbt,Haridra,Daruharidra,Malati,Sita,and drugs
        belonging to the Iv d kolyadi group,is renowned for its healing properties.A medicated oil prepared
        with Kjtldnusari,
```

`sushruta_samhita_vol_2_pdf_416_P0` (Kuṣṭha treatment: gold for eval_025)
```
BEFORE: AKushtha-patientdesirousofbeingperfectlycuredshouldconstantlyusepreparationsofKhadirainhisdrinks,
AFTER:  A Kushtha-patient desirous of being perfectly cured should constantly use preparations of Khadira in
        his drinks,
```

**Known residual errors** (rare, and still better than the glued run for BM25):
"haemoptys is", "digest ant", "CHIKITSA STHANA M", "in u his on" (an OCR-garbled
phrase), "Iv d kolyadi" (an OCR-garbled name).

**Approved 2026-10-29**; `split_glued_ocr_words` now defaults to `True`. Adds
`wordninja==2.0.0` to requirements.

---

## 3c. Contextual chunk headers

Each child chunk gets `metadata["context_header"]` = `[Work] > [Section/Chapter] > [Herb/Formulation]`.
`contextual_text()` prepends it to the text used for **embedding** (ingestion) and
**reranking** (`cohere_rerank`). `text` itself is unchanged, so display, citations,
the parent store and BM25 all keep the raw page text.

Why it matters: a 450-char child often lacks the words that identify it. The
Pharmacopoeia's `Rasa : Tikta, Kaṣāya …` block never names its herb (the name is on
the monograph's first page), and a Sushruta passage doesn't say which chapter or
disease it belongs to.

### How structure is read (`src/ingestion/context_headers.py`)

| Work | Item marker | Section marker |
|---|---|---|
| Pharmacopoeia | `10. Asvagandha (Rt.)`, the monograph's opening line | PROPERTIES AND ACTION, SYNONYMS, … |
| Formulary | `5:2 KAISORA GUGGULU (Bhaisajyaratnavali…)` | `GROUP No. 5 GUGGULU` |
| Sushruta | — | sthāna + chapter from the running head `Chap.IX.]CHIKITSASTHANAM`, or the opening `CHAPTER XLIV. Now we shall discourse…` |
| Ashtanga Hridaya (English) | `Amalaki (Emblica officinalis):` drug entries | `Dinacarya Adhyaya : 2` running head + sthāna |

Items and sections **carry forward across pages** until the next marker. A chunk
takes the header in effect at its midpoint, located by word sequence because chunks
are re-joined with single spaces and so aren't verbatim substrings of the page.

The Sushruta OCR needed most of the work:
- Chapters may only move **forward** within a sthāna. Running heads may step 0–3.
- A chapter opening **always** moves the chapter on. Its numeral may jump up to 3
  ahead (an opening lost to OCR leaves a gap). An unreadable numeral, or one that
  is behind or further ahead, is a misreading, so the opening counts as the next
  chapter.
- Openings are matched glitch-tolerantly. The heading may be letter-spaced, glued,
  or damaged (`H A P T E R`, `CHAPTEK`, `CH.\PTER`, `chapterIX`). The numeral may
  be misread (`Vn` VII, `ym` VIII, `in` III, `11` II, `XXXIIT` XXXIII, `I v i I I`),
  and so may the sentence (`Xow we`, `I^ow^we`, `No\yweshall`, `Now shall`). The
  pattern needs only the heading and a numeral with "shall" close behind.
- OCR numeral slips (`XVIIl`, `XXXILI`, `XLY`, `XHI`, `XL1I`) are normalized. Only
  canonical numerals are accepted, and when two readings are valid (`XL` = 40 vs
  XI), the one nearest the next expected chapter wins.
- Cross-references ("see Chap. X", "as in the Sutrasthana") are ignored: only
  capitalized running heads and chapter openings count.
- Table-of-contents pages are ignored. A sthāna change clears the chapter count.

**Chapter-boundary audit (2026-10-30), all three volumes.** All 186 chapters
(Sutra 46, Nidana 16, Sharira 10, Chikitsa 40, Kalpa 8, Uttara 66) were located
independently of the header code. 184 were found by their opening. The openings of
Sutra II and Uttara VI are lost in the OCR, so those two are located by the
previous chapter's closing colophon. Every opening numeral agrees with the
chapter's place in its sthāna.

The header state just after each boundary was then checked: **165/186** right
before this fix, **184/186** after. The pattern matches all 184 openings the OCR
has, with no false matches (contents pages, sub-section openers such as "Now we
shall discourse on the Bulb group"). The two misses are those lost openings: their
pages keep the previous chapter's number, Sutra II on p106–109 of vol 1 and
Uttara VI on p40–45 of vol 3. 312 of ~9,000 Sushruta chunks changed header, each
to its true chapter. The largest groups: 114 chunks of Uttara 18 had read 17, 43
of Uttara 1 had no chapter, and 28 of Nidana 7–8 had read 6.

### Results

| Work | Chunks with section or item | All three levels |
|---|---|---|
| Pharmacopoeia | 99% | 92% |
| Formulary | 51% item level (was 91%, mostly wrong; see below) | — |
| Sushruta | 95% | n/a (no item level) |
| Ashtanga Hridaya | 15% | 14% (only the English Vidyanath volume has markers) |

All **20 Sushruta pages cited in `relabel_review.md`** carry the right sthāna and
chapter, e.g. vol2 p535 → *Chikitsasthana, Chapter 24* (hygiene), vol3 p204 →
*Uttaratantra, Chapter 39* (fever), vol3 p347 → *Uttaratantra, Chapter 52* (cough).

### Formulary item headers: fixed 2026-10-29

The first version found a formulation title only as "G:I TITLE (", and carried
the last name forward otherwise. It missed 260 of 568 titles, so chunks from about
46% of monographs, and every index, appendix and glossary page, got the *previous*
formulation's name. The fix:
- **Titles** are the upper-case run (≤ 6 words) after the number, in any OCR form:
  `16:3`, `1 : 9`, `1 ; 14`, `7.2`, or `3:17PUGA`, with or without the "(" that
  follows. When OCR garbled the number, a title is still found from the
  upper-case run right before its classical source reference ("fe LASUNADI
  GHRTA (Astangahrdaya…"). The source list (24 works, plus OCR variants) was taken
  from the reference heads that follow parsed titles.
- **No carry-forward across unreadable boundaries** (a wrong header is worse than
  none). The item goes blank:
  - at a source reference with no title before it (a monograph whose title is
    unreadable, or a citation stranded by the two-column layout);
  - at the top of a page that doesn't continue a monograph (no quantities, dose,
    anupāna or uses before its first title);
  - on index and summary-table pages (≥ 12 bare section numbers; monograph pages
    have ≤ 9).
- **OCR traps in titles** (found while building the inclusive spans below):
  - The second volume renders Devanagari verses as Latin garbage. The run before
    a verse's closing citation looked like a title ("aaoda aH BOT II
    (Vasavarajiyam…"), so a garbage name ran over the rest of the monograph. A
    title found by its reference is rejected if it holds a danda read as "II"/"Il"
    or a "W" (not an IAST letter), or follows mixed-case junk ("HaCaT"), unless a
    list number ("21.") sits right before it.
  - A title word may carry one lowercase slip ("VATi", "POTTALi RASA",
    "PALASABiJADI") but never ends right before a lowercase letter: that capital
    starts the next word ("BHASMA A|cceptable", "RASA B|haisajyaratnavali").
  - A heading split by OCR is joined ("12:4 KASTURYADI (VAYU) GUTIKA",
    "18:6 TRIVANGA! BHASMA").
  - A section number may end in a period ("4:2. ARKADI KVATHA CURNA"): 16 more
    titles in the second volume.

  The first three changed 36 chunk headers: 31 truncated or split names
  completed, 4 garbage names blanked, 1 new title (Boladi Vati).
- **Recovery from section numbers.** Most chunks blanked as "title unreadable"
  sit inside a monograph whose title did parse. A doubtful boundary had blanked
  them: a citation the two-column layout misplaced, or, in the second volume,
  the citation that closes the verse block, well over 160 chars after the title.
  A blank inside a monograph span is given the monograph's name only when nothing
  else can start there:
  - the next parsed title carries the next section number (G:I, then G:I+1; or
    G+1:1 after a group end trimmed before the introduction), and
  - the span holds at most one therapeutic-uses list. A misread number or an
    untitled formulation in between would bring a second one.

  A title found without its number takes it from its neighbours (between G:I-1
  and G:I+1, or G:last and G+1:2). Table pages stay blank, and no named chunk
  is renamed. This filled 297 blanks: 251 of the 425 "title unreadable" chunks
  and 46 verse chunks. A spot check of 10 against the page text found all 10
  right (Sri Ramabana Rasa's chunk reads "Grahani, Amavata"; Punarnavadyarista's
  chunk carries its own Sotharogadhikara citation).

Item-level coverage over 4,090 chunks went from 91.1% to **51.4%**:

| Chunks now | Count | Share |
|---|---|---|
| named | 2,101 | 51.4% |
| blank: non-monograph page (front matter, glossary, appendix, garbage OCR) | 1,206 | 29.5% |
| blank: index / summary-table page | 467 | 11.4% |
| blank: formulation content, still unresolved (**miss**) | 174 | 4.3% |
| blank: verse / OCR-noise chunk on a monograph page | 142 | 3.5% |

The old 91% was mostly carry-forward error. 1,364 of its 3,726 named chunks sat on
non-monograph or index pages, so those blanks are correct, and 857 of the chunks
named after the title fix had a different name before. Spot check of 10 changed
headers (title fix): 7 correct, 2 straddle a monograph boundary (the header names
the monograph at the chunk's midpoint), and 1 was wrong (a summary-table page),
which the table-page rule now blanks.

The 174 remaining misses break down as:
- 63 back-matter entries (purification procedures, appendices) or titles without
  a section number;
- 56 outside every monograph span: group introductions and front or back matter;
- 28 in spans holding two or more uses lists (an untitled formulation inside);
- 27 before a next title that skips the new group's first formulations.

About 119 of these are right to stay blank. The ~55 that are real formulation
content can't be told apart without the untitled formulation's own title.

**The Formulary's own index and contents pages** were tried for that last step.
They are:
- the formula-wise therapeutic index (back matter: serial, name and G:I for every
  formulation, by group);
- the table at the start of each group (formulation, source, verses and printed
  page).

In the parent store their line breaks are gone, so names run together in the
column-wise blocks ("…KUMARYASAVA (A) KUMARYASAVA (B) KHADIRARISTA…"). Scored
against the titles that do parse, the index-derived section map agreed on 137 of
194 numbers. The group-table rows agreed on 165 of 225, and their page column
gave no stable printed-to-PDF offset in the second volume. Assigning titles from
either map would add wrong headers, so neither is used. A layout-aware re-read of
those pages from the PDFs (word positions, not the joined text) would be needed
first.

**Evidence sets use different boundaries.** A blank header is safe, but a
supporting set that stops at a doubtful boundary drops real evidence. So
`afi_monograph_spans` keeps a formulation whole. It runs from its parsed title
to the next parsed title, across pages, through orphan or misplaced citations.
It stops early only before a new group's introduction or the back matter, and
always after the formulation's uses list. See `data/eval/LABELING_CRITERIA.md`.

### Pharmacopoeia item headers: carry-forward audit 2026-10-29

Same check on the Pharmacopoeia. Boundaries were found independently of the header
code, from the upper-case IAST title line every monograph opens with
(`AŚVAGANDHĀ (Root)`). Result: 20 random boundaries, **19/20** headed with their own
drug; all 513, **501**. Eleven of the 12 misses were carry-forward errors, where the
previous drug's name ran on for a whole monograph:
- Seven running headers didn't parse because the plant part contains "&"
  (`Yashti (Stm& RT.)`, `Kumkuma (Sty & Stg.)`, …).
- Four had garbled punctuation: `1. Akarakarabha (R)t.)` (headed "Yavani (Frt.)"),
  `16. Dronapushpi (W.P.).)`, `11. Dhanvayasa (Wh/Pl)` and
  `24. Jivaka (Pseudo –bulb)`.

The twelfth, CIÑCĀ headed "Chicha (Ft. Pl.)", is the same drug spelled differently.

The fix:
- The running-header pattern accepts "&" and commas in the plant part.
- When the running header doesn't parse, the IAST title line names the monograph,
  if a "<Drug> consists of … (Fam. …)" opening sentence follows.
- An opening sentence with no title before it still blanks the item.
- Description sentences ("mesocarp consists of …") never cite a family, so they
  don't count as openings.

After: **512/513** (only the CIÑCĀ spelling variant). Item coverage is unchanged at
99.2%. 162 of 6,557 chunks (2.5%) were renamed across 11 monographs, from the
previous drug to the right one, e.g. Tagara (Rz.) → Tamalaki (Rt. St.& Lf.) (16
chunks).

Examples:
```
api_all_volume_pdf_40_P0_C0   Ayurvedic Pharmacopoeia of India > Properties and Action > Asvagandha (Rt.)
afi_part1_pdf_162_P0_C2       Ayurvedic Formulary of India > Triphala Curna
sushruta_samhita_vol_2_pdf_416_P0_C0   Sushruta Samhita > Chikitsasthana, Chapter 9
ashtanga_hridaya_vidyanath_illustrated_pdf_163_P0_C0
                              Ashtanga Hridaya > Sutrasthana, Annasvarupa Vijnaniya Adhyaya (6) > Amalaki (Emblicaofficinalis)
```

`contextual_chunk_headers` defaults to `True`, but it only takes effect on
re-ingestion. Because the embedded text changes, **every vector must be
re-embedded**. `scripts/reingest.py` does this into a fresh index (see 3e).

---

## 3d. Charaka Samhita excluded; Ashtanga Hridaya audit

`settings.exclude_charaka` (default `True`): ingestion skips Charaka Samhita and
reports it in `stats["excluded_files"]`. The current index still contains it until
the next re-ingest.

Text-layer quality per file (parent store; "readable English" = a parent with 40+
Latin words, > 60% of them English):

| Source | Parents | Latin | Devanagari | Readable-English parents | Verdict |
|---|---|---|---|---|---|
| charaka_samhita_pv_sharma.pdf | 1,626 | 0% | 56% | 0 (0%) | English translation OCR'd as Devanagari; only the Sanskrit verses are legible. **Excluded.** |
| ashtanga_hridaya_vidyanath_illustrated.pdf | 951 | 77% | 0% | 492 (52%) | Good English (Sūtrasthāna) |
| ashtanga_hridaya_sanskrit_commentaries.pdf | 3,266 | 0% | 80% | 0 | Legible Sanskrit commentary, Devanagari only |
| ashtanga_hridaya_srikantha_murthy_vol1.pdf | 1,219 | 0% | 42% | 0 | **Garbage**: an English book OCR'd with a Hindi engine (`€0712178 121 2764 …`) |

**Ashtanga Hridaya overall: 492 / 5,436 parents (9%) are readable English**, all of
them from the Vidyanath volume. Yet AH is 45% of the index (21,140 of 46,826
children).

**Recommendation: keep Ashtanga Hridaya, but only the Vidyanath volume.**
- *Vidyanath*: keep. It's the only English AH text, and it's gold for 9 proposed
  labels (Dinacaryā, vamana/virecana, nasya, vasti, dravya properties).
- *Srikantha Murthy vol 1*: exclude now. Its text layer can't be matched by any
  query, and it holds 26% of AH's chunks. It's worth re-OCRing with an English engine,
  since it covers Sūtra- and Śārīrasthāna.
- *Sanskrit commentaries*: exclude for this English-question eval. It's real
  Sanskrit, but English queries can't match it lexically, and it adds 15k chunks of
  semantic near-misses. Revisit if Devanagari queries are supported.

**Approved 2026-10-29:** both are excluded behind `exclude_ah_srikantha_murthy` and
`exclude_ah_sanskrit_commentaries` (default `True`), alongside `exclude_charaka`.
`pipeline.excluded_reason(filename)` gives the reason for each skipped file.

---

## 3e. Re-ingestion cost estimate

Computed offline: the corpus was re-chunked from the parent store with the font map
and headers applied (`chunk_record` + `contextual_text`). Embedding runs in batches
of 96 children per Cohere call (`embedder.MAX_BATCH`). Headers add 16–91 chars per
chunk (the most in Vidyanath and API, the least where there's no structure).

| Scenario | Children | **Cohere embed calls** | ≈ Tokens | Time (throttle-bound at 80k tok/min) |
|---|---|---|---|---|
| A. All sources | 46,948 | 490 | 4.7M | ~58 min |
| **B. Charaka excluded (current default)** | 40,780 | **425** | 4.1M | ~51 min |
| C. B + Srikantha Murthy & Sanskrit commentaries excluded (recommended) | 22,842 | **238** | 2.4M | ~30 min |

- Token counts use ~4 chars/token, which undercounts Devanagari. Scenario A/B times
  are therefore optimistic; C is mostly Latin text.
- **No Claude calls.** BM25, the parent store, OCR splitting, headers and the font
  map are all local.
- **Quota fit (trial key, 1,000 calls/month), for the chosen scenario C:**
  - The dry run gives 237 re-ingest calls.
  - The comparison (`scripts/run_comparison.py`) runs each deterministic config
    once and only HyDE three times: `before` (old index; rrf, rerank) = 60, and
    `after` (rrf, rerank, rerank_mmr, rerank_hyde ×3) = 270.
  - **Total 60 + 237 + 270 = 567, leaving a 433-call (43%) margin**, plus 90 Claude
    Haiku calls for HyDE.
- **Procedure: `scripts/reingest.py`, blue/green.** This corrects earlier notes here
  that suggested an in-place rebuild with `skip_existing=False` and
  `delete_by_source`.
  - The rebuild goes into a **new** Pinecone index. Serverless indexes can't delete
    by metadata filter, so `delete_by_source` couldn't remove excluded sources in
    place.
  - In an empty index, `skip_existing` makes the run resumable: if it stops on a
    Cohere quota error, re-running the same command embeds only what's missing.
  - BM25/parent stores are staged in `data/cache/staging/<index>/` and promoted,
    with a timestamped backup of the old ones, only once the new index's vector
    count matches the chunk count. Then set `PINECONE_INDEX_NAME` to the new index.
  - The live index and stores stay untouched until then.
  - The eval embedding cache needs no rebuild: it's keyed by text, and changed
    texts simply miss.
