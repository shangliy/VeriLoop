# Provenance Merge Report: Museum Exports A and B

## 1. Summary

- The two batch exports contain **70 object rows** (A: 36, B: 34) after removing 6 non-object rows (blank lines, a vendor header, and footer/notes rows).
- Normalising accession numbers reduces these to **25 distinct objects** (catalog records). **45 rows** are redundant.
- **17 objects appear in both batches**; 8 appear only in B. No object appears only in A.
- Each batch contains internal duplicates. A holds 19 redundant rows (for example, `X-100`, `X 100`, and `x_100` are one vase); B holds 9.
- One record (`T88X`, "Bronze mirror (typo id)") is **not merged** into `T88` because its accession ID is not a formal match. It is flagged for registrar confirmation. If it is confirmed as a duplicate, the catalog drops to 24 objects.
- Of the 25 records, 24 have a usable date. Two of these are **reproductions** (a 20th-century rubbing and a 1998 replica), so the collection contains **22 dated originals**.
- The dated originals are spread thinly across two millennia. Only 4 predate 220 CE, and none date from the 2nd to the 5th century CE. About 41% (9 of 22) fall between 1600 and 1900, with the **19th century the single largest bin (5 objects)**.

## 2. Data and methods

### 2.1 Inputs
- `data/museum_export_a.csv` (Batch A; columns `accno, title, year_note`)
- `data/museum_export_b.csv` (Batch B; columns `accession, object_name, remarks`)

The files are read-only. Both use different column names and are processed by position.

### 2.2 Non-object rows excluded
| Batch | Line | Content | Reason |
|---|---|---|---|
| A | 2 | blank | empty row |
| A | 3 | `---` / "BATCH A PULL 2024-11" | vendor header row |
| A | 40 | `TOTAL_ROWS` / "system footer" | footer |
| B | 2 | blank | empty row |
| B | 3 | `EXPORT_NOTE` / "merged from legacy DB" | internal note |
| B | 38 | `FOOTER` / "row count check" | footer |

A row is treated as an object only if its accession field, after normalisation, matches `letters + digits + optional letters`.

### 2.3 Accession normalisation (the merge key)
The raw accession field is normalised as follows:
1. Trim whitespace, upper-case, and remove spaces, hyphens, and underscores (`x_100`, `X 100`, `X-100` → `X100`).
2. Drop leading zeros in the numeric part (`T088` / `T-088` → `T88`; `A001` / `A-001` → `A1`; `Y-050` → `Y50`).
3. Keep trailing letters, so `T88X` stays distinct from `T88`.

The naive approach of counting distinct raw strings (whitespace-trimmed) gives **53** "objects". This overcounts because the same object is recorded under several hyphen, space, and zero-padding variants. The normalised key gives **25**.

### 2.4 Dating
Dates were assigned by reading every source note for each object (both batches). The rules were:
- Use an explicit date (card, label, or ledger) where one is given.
- Otherwise, intersect the period named in the notes (for example, "Kangxi" = 1662–1722, "late Ming" intersected with "Wanli" = 1572–1620) with the century named in the notes.
- The representative year is the explicit date where one exists, otherwise the midpoint of the admissible range.
- A confidence level is recorded: *high* for explicit dates or reign-bounded periods; *medium* for period- or dynasty-level dating or approximate labels; *low* for style-only attribution.

These decisions are recorded in `code/merge_catalog.py` (the `DATING` table), and each is traceable to its source note in `outputs/catalog.csv`.

### 2.5 Reproductions
Two objects are flagged as reproductions and excluded from the "originals" distribution: `A1` (a 20th-century copy of a stele, so the date is that of the copy) and `Z999` (a marked 1998 reproduction).

## 3. Results

### 3.1 Merge results
| Measure | Value |
|---|---|
| Object rows, Batch A | 36 (→ 17 objects; 19 internal duplicates) |
| Object rows, Batch B | 34 (→ 25 objects; 9 internal duplicates) |
| Total object rows | 70 |
| Distinct objects after normalisation | **25** |
| Objects in both batches | 17 |
| Objects in B only | 8 (`T88X`, `S400`, `W700`, `Y50`, `Q120`, `V303`, `U808`, `E505`) |
| Rows removed by merge | 45 |

Accession variants found: `X100` appears as `X-100`, `X 100`, `x_100`, `X100`, and `X100 ` (trailing space); `M205` as `M-205`, `M 205`, `M205`; `T88` as `T-088` and `T088`; `K12` as `K-012` and `K12 `. All 17 overlapping objects have consistent descriptions across batches.

### 3.2 Catalog
The full catalog is in `outputs/catalog.csv`, and the row-level crosswalk (raw ID → canonical ID) is in `outputs/id_crosswalk.csv`. Summary (sorted by representative date):

| ID | Title | Batches | Representative date | Range | Century | Confidence | Note |
|---|---|---|---|---|---|---|---|
| G333 | Jade pendant | A+B | 348 BCE | 475–221 BCE | 4th c. BCE | low | style-based |
| Q120 | Iron sword | B | 310 BCE | 400–221 BCE | 4th c. BCE | medium | |
| X100 | Vase, Han style | A+B | 200 BCE | Han, 206 BCE–220 CE | 2nd c. BCE | high | card "200BC" |
| Y50 | Glass bead strand | B | 7 CE (midpoint) | Han, 206 BCE–220 CE | 1st c. CE | medium | reference range only |
| K12 | Stone Bodhisattva | A+B | 550 CE | 550 (approx.) | 6th c. CE | medium | label "550 CE approx" |
| T88 | Bronze mirror | A+B | 762 | 618–907 | 8th c. CE | high | Tang, card range |
| V303 | Gilt bronze fitting | B | 762 | 618–907 | 8th c. CE | high | Tang |
| U808 | Stoneware jar | B | 933 | 907–960 | 10th c. CE | medium | Five Dynasties |
| H222 | Ewer | A+B | 1150 | 1101–1200 | 12th c. CE | high | |
| R500 | Celadon dish | A+B | 1203 | 1127–1279 | 13th c. CE | medium | Southern Song |
| W700 | Bronze bell | B | 1450 | 1400–1499 | 15th c. CE | high | Ming |
| N300 | Inkstone | A+B | 1596 | 1572–1620 | 16th c. CE | medium | Wanli reign |
| D77 | Lacquer box | A+B | 1650 | 1603–1700 | 17th c. CE | high | Edo, 17th c. |
| B44 | Porcelain figure | A+B | 1692 | 1662–1722 | 17th c. CE | high | Kangxi |
| M205 | Landscape handscroll | A+B | 1752 | 1752 | 18th c. CE | high | ledger date |
| L600 | Snuff bottle | A+B | 1765 | 1736–1795 | 18th c. CE | medium | Qianlong style |
| J150 | Wood printing block | A+B | 1850 | 1800–1899 | 19th c. CE | high | |
| E505 | Painting album leaf | B | 1850 | 1800–1899 | 19th c. CE | high | |
| F888 | Cloisonné vase | A+B | 1875 | 1850–1899 | 19th c. CE | medium | export ware, late Qing |
| S400 | Snuff dish | B | 1880 | 1880 | 19th c. CE | high | |
| P401 | Robe fragment (silk) | A+B | 1900 | 1890–1910 | 19th c. CE (midpoint) | high | sits on the 19th/20th boundary |
| C901 | Silver hairpin | A+B | 1925 | 1920–1929 | 20th c. CE | high | Republic era |
| A1 | Rubbing (copy of stele) | A+B | 1950 | 1901–2000 | 20th c. CE | high | **reproduction** |
| Z999 | Replica vase | A+B | 1998 | 1998 | 20th c. CE | high | **reproduction** |
| T88X | Bronze mirror (typo id) | B | undated | — | undated | none | **possible duplicate of T88; not merged** |

No dating conflicts were found between notes of the same object. One apparent conflict (B's remark "1752 vs 18th c conflict" for `M205`) is not a real conflict, because 1752 lies within the 18th century.

### 3.3 Distribution over time
Counts use the representative year (midpoint method). "Range overlap" counts every dated record whose admissible range touches the century, and is included as a sensitivity check.

| Century | Originals (midpoint) | All dated (midpoint) | All dated (range overlap) |
|---|---|---|---|
| 4th c. BCE | 2 | 2 | 2 |
| 3rd c. BCE | 0 | 0 | 4 |
| 2nd c. BCE | 1 | 1 | 2 |
| 1st c. BCE | 0 | 0 | 2 |
| 1st c. CE | 1 | 1 | 2 |
| 2nd–5th c. CE | 0 | 0 | 0–2 |
| 6th c. CE | 1 | 1 | 1 |
| 7th c. CE | 0 | 0 | 2 |
| 8th c. CE | 2 | 2 | 2 |
| 9th c. CE | 0 | 0 | 2 |
| 10th c. CE | 1 | 1 | 3 |
| 11th c. CE | 0 | 0 | 0 |
| 12th c. CE | 1 | 1 | 2 |
| 13th c. CE | 1 | 1 | 1 |
| 14th c. CE | 0 | 0 | 1 |
| 15th c. CE | 1 | 1 | 1 |
| 16th c. CE | 1 | 1 | 1 |
| 17th c. CE | 2 | 2 | 3 |
| 18th c. CE | 2 | 2 | 5 |
| 19th c. CE | 5 | 5 | 5 |
| 20th c. CE | 1 | 3 | 4 |
| **Total** | **22** | **24** (+1 undated) | |

Key figures:
- **Pre-220 CE:** 4 originals (G333, Q120, X100, Y50). X100 has a card date (high confidence); Q120 and Y50 are medium; G333 is low (style-based).
- **Before 1600 vs. 1600 onward:** 12 vs. 10 originals.
- **Peak:** the 19th century holds 5 of 22 originals (23%). Including the 18th and 17th centuries, 9 of 22 (41%) fall between 1600 and 1900.
- **Gaps:** no originals are dated to the 2nd–5th centuries CE, the 7th, 9th, 11th, or 14th centuries. The 1st century CE is represented only by a Han-range object.
- **20th century:** only one original (C901). The other two 20th-century items are reproductions, so the "20th century" count is inflated by copies if read naively.

## 4. Discussion

**The normalisation changes the answer.** A naive catalogue built from raw accession strings would report 53 objects and would wrongly count a single vase as three or four. Only the normalised key gives the correct figure of 25.

**The temporal skew is real but thin.** The 19th-century peak and the ancient-to-medieval gap are visible in both midpoint and range-overlap counts. However, the sample has only 22 dated originals, and most dates are period-level (dynasty or reign ranges) rather than exact. The distribution should be read as a rough shape, not as a statistically reliable profile. The 19th-century concentration in particular should not be taken as evidence of collecting intent without knowing the sampling frame; the two exports may themselves be a subset of the collection.

**Dating sensitivity.** The midpoint method places Han objects in the 2nd century BCE, but their admissible range spans the 3rd century BCE to the 3rd century CE. Under range-overlap counts, the early centuries gain weight. The qualitative conclusion (sparse early material, cluster in the 17th–19th centuries) holds under both methods.

**Data quality issues observed.** Accession IDs vary in case, spacing, hyphenation, trailing whitespace, and zero-padding. Footer and note rows are mixed into the data. Batch B's `remarks` field contains explicit cross-references ("duplicate of batch A X-100", "should match T88") that helped confirm merges.

## 5. Decisions and limitations

1. **Merged on normalised accession.** A zero-padded and an unpadded ID were merged when they agree in every other field. The data never shows a zero-padded ID that conflicts with its unpadded partner. If the registrar treats the two forms as distinct series, the affected merges (`T88`, `A1`, `K12`, `Y50`, and others) would need to be revisited.
2. **`T88X` kept separate.** Its own remark says it "should match T88", but it is a typo-ID with no date. Merging it would reduce the count to 24 and would add no date information. I left it unmerged and flagged it for registrar review.
3. **Reproductions kept in the catalog but excluded from originals-only statistics.** `A1` and `Z999` are real objects in the collection, but their dates describe the copy, not the source object.
4. **Dates are inferred from notes, not verified.** No external authority was consulted. Medium- and low-confidence dates (for example, `G333` style-based, `K12` approximate) should be checked against physical records before any published analysis.
5. **Sample size.** Twenty-two dated originals is too few for fine-grained statistics. Percentages are given for orientation only.

## 6. Files

| File | Contents |
|---|---|
| `code/merge_catalog.py` | Full pipeline: parsing, normalisation, merge, dating table, distribution |
| `out/merge_log.txt` | Stdout audit log of the run (row counts, merge groups, distribution) |
| `outputs/catalog.csv` | 25-record deduplicated catalog with dates, confidence, flags, and source notes |
| `outputs/id_crosswalk.csv` | All 70 object rows with their raw ID, canonical ID, and batch |
| `outputs/time_distribution.csv` | Century counts (midpoint and range-overlap) |
| `report/report.md` | This report |
| `report/provenance_merge_report.md` | Copy of this report under the requested deliverable name |
