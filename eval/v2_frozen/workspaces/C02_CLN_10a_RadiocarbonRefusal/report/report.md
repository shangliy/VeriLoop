# Huangtupo site chronology

**STATUS: INFEASIBLE** for the complete requested chronology: the supplied data do not include a radiocarbon calibration curve, a reservoir correction, a Harris matrix, or archaeological cultural-period criteria. Conventional radiocarbon ages and a conditional relative sequence are nevertheless calculated below. Calendar dates and named cultural periods cannot be established responsibly from the supplied files.

## Method

The input consists of the assay table and its accompanying specification. The reproducible calculation is `python code/analyze.py`; its complete output is in [analysis.txt](../out/analysis.txt). Following the specification, conventional age is −8033 ln(F14), in radiocarbon years BP. The interval shown is obtained by transforming the measured F14 plus and minus its laboratory 1σ uncertainty; the transformation reverses the endpoints and makes the age interval asymmetric. It is a transformed measurement interval, not a calibrated calendar interval or a complete statement of dating uncertainty. No clipping was required. Ages and interval endpoints are rounded to whole years.

## Assays

| Artifact | Provenience | Material | F14 ± 1σ | Batch | Conventional age BP | Transformed 1σ interval BP | Calibrated calendar | Context or caution |
|---|---|---|---|---|---:|---:|---|---|
| AC-107 | Trench3-L1 | charcoal | 0.883 ± 0.004 | BP-24091 | 1000 | 963–1036 | unavailable | Broad tree-ring block; possible old-wood offset |
| AC-108 | Trench3-L2 | charred bone | 0.647 ± 0.003 | BP-24092 | 3498 | 3460–3535 | unavailable | Lab notes well-preserved collagen |
| AC-109 | Trench3-L3 | charcoal | 0.0041 ± 0.0008 | BP-24093 | 44156 | 42724–45899 | unavailable | Very small carbon yield after pretreatment; contamination sensitivity warrants scrutiny |
| AC-110 | Trench3-L4 | shell organics | 0.0065 ± 0.0010 | BP-24094 | 40454 | 39304–41796 | unavailable | Reservoir correction discussion pending |
| AC-111 | Trench3-L5 | charcoal | 0.2187 ± 0.0020 | BP-24095 | 12211 | 12137–12284 | unavailable | Same ridge source as AC-112 |
| AC-112 | Trench3-L6 | charcoal | 0.2195 ± 0.0020 | BP-24096 | 12181 | 12108–12255 | unavailable | Same ridge source as AC-111 |
| AC-113 | Trench4-pit7 | charcoal | 0.451 ± 0.002 | BP-24097 | 6397 | 6361–6432 | unavailable | Short-lived twigs |
| AC-114 | Trench2-surface scatter | charcoal | 0.771 ± 0.003 | BP-24098 | 2089 | 2058–2120 | unavailable | Root intrusion risk flagged |

A calibration curve converts radiocarbon age to a probability distribution over calendar time, potentially with multiple ranges; subtracting a conventional age from a reference year does not perform calibration. No curve, version, hemisphere, or relevant shell reservoir parameters are provided. Shell origin and reservoir effects must be established before choosing an appropriate calibration and correction. Lab error alone also does not capture old wood, contamination, redeposition, or material-specific offsets.

## Relative chronology and interpretation

If the Trench3 labels denote successive undisturbed layers numbered from top to bottom, the provisional depositional order from youngest to oldest is L1 → L2 → L3 → L4 → L5 → L6. This is an assumption, not a documented Harris matrix. The assays do not support a simple monotonic age sequence: L3 is older than L4 in conventional radiocarbon age, and both are much older than L5 and L6. L5 is also nominally older than L6, although their uncertainty ranges overlap. The latter pair differs by −0.0008 F14, or −0.28 combined standard deviations assuming independent laboratory errors; shared source and possible correlated effects mean this is not proof of independent agreement or contemporaneous deposition. Reservoir effects, sample integrity, old carbon, redeposition, intrusion, or incorrect inferred layer relationships could contribute to discordance; these data do not identify the cause.

The pit and surface scatter have no supplied stratigraphic links to Trench3 or each other. Their conventional ages should not be used to establish direct depositional relationships. In particular, the surface sample's field-noted root intrusion risk weakens its association with site occupation.

## Periodization sketch and next steps

The assays suggest several distinct radiocarbon-age groupings, but no named cultural periods or occupation phases can be assigned from ages alone. Material age is not necessarily the age of deposition or occupation, and the strong reversals make an integrated timeline premature. Obtain the excavation matrix and context descriptions, assess association and sample quality, resolve the shell source and reservoir correction, and calibrate each appropriate assay using a documented curve and software. Only then compare calibrated distributions and securely associated diagnostic artifacts with an independently sourced regional cultural sequence. Any modeled stratigraphic constraints should be justified by the actual matrix and tested for outliers rather than imposed on these discordant assays.
