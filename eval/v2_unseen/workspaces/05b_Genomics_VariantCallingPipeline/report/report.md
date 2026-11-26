# Germline Short-Variant Calling: Report

## Status

**Not completed. No variant calls were produced.** The locked pipeline could not be executed because its inputs and tool are absent from this machine. No variant counts, summaries, or quality metrics are reported here, because none exist.

## Task

Run germline short-variant calling on the CRAMs listed in `data/sample_manifest.csv`, following `data/pipeline_lock.txt` and `data/resource_paths.txt`, then summarize the variants.

## Locked specification

From `data/pipeline_lock.txt`:
- GATK **4.1.0.0**
- Command chain: HaplotypeCaller → GenotypeGVCFs
- Resource bundle: **b37**, paths as listed in `resource_paths.txt`
- Do not substitute bcftools/mpileup for the variant-calling stage

From `data/resource_paths.txt`:
- `REF=/refs/b37/human_g1k_v37.fasta`
- `DBSNP=/refs/b37/dbsnp_138.b37.vcf.gz`

From `data/sample_manifest.csv`: one sample, `S001`, with CRAM `./data/crams/sample.cram`.

## Method

I wrote `code/run_variant_calling.sh`. It:
1. Reads `REF` and `DBSNP` from `resource_paths.txt`, so no paths are hard-coded.
2. Checks every locked input and tool before doing any work: the `gatk` launcher, the reference FASTA with its `.fai` and `.dict`, the dbSNP VCF with its `.tbi`, and each manifest CRAM.
3. Confirms the GATK version is 4.1.0.0.
4. For each sample, runs `HaplotypeCaller -ERC GVCF`, then `GenotypeGVCFs`, then `CountVariants`.

The script exits with an explicit error if any precondition fails, so it never silently produces partial or substitute output.

## Execution result

Log: `out/run_variant_calling.log` (raw stdout/stderr from the run)

```
[MISSING] GATK launcher: gatk
[MISSING] Reference FASTA: /refs/b37/human_g1k_v37.fasta
[MISSING] Reference .fai: /refs/b37/human_g1k_v37.fasta.fai
[MISSING] Reference .dict: /refs/b37/human_g1k_v37.dict
[MISSING] dbSNP VCF: /refs/b37/dbsnp_138.b37.vcf.gz
[MISSING] dbSNP index (.tbi): /refs/b37/dbsnp_138.b37.vcf.gz.tbi
[MISSING] CRAM for S001: .../data/crams/sample.cram
ABORT: locked inputs/tools missing; no variant calls were produced.
exit=2
```

What I checked on the machine:
- `/refs` does not exist. No b37 FASTA or dbSNP file is present anywhere under `/` (filesystem search by name).
- `data/crams/` does not exist, and no file named `sample.cram` exists anywhere on the filesystem. The manifest's CRAM is therefore absent.
- `gatk` is not on `PATH`, and no GATK jar or GATK Docker image is installed. The local Docker images include no GATK or samtools/bcftools image.
- Java 21 is present, but it does not provide GATK 4.1.0.0.

## What is blocking the work

1. **CRAM input missing.** `./data/crams/sample.cram` is not present. Without it, no alignment can be read.
2. **Reference bundle missing.** The b37 FASTA and dbSNP VCF named in `resource_paths.txt` are not on this machine.
3. **Locked tool missing.** GATK 4.1.0.0 is not installed. Running the required chain needs it. I did not substitute another caller, because the lockfile forbids substituting bcftools/mpileup and specifies the GATK chain.

I did not download the reference bundle or the GATK tool. The task instructions prohibit network downloads of external datasets unless explicitly instructed, and the instructions do not authorize them here.

## What would unblock this

Any one of the following would let the script run as written:
- Place `sample.cram` at `data/crams/sample.cram` (the manifest path), or update the manifest to point to the real file.
- Provide the b37 reference FASTA and dbSNP 138 VCF at the paths in `resource_paths.txt`, with their `.fai`, `.dict`, and `.tbi` indexes.
- Install GATK 4.1.0.0 and put `gatk` on `PATH`, or supply a container that provides it.

Once these exist, rerun `bash code/run_variant_calling.sh`. The script will write per-sample `outputs/S001.g.vcf.gz` and `outputs/S001.vcf.gz`, and print variant counts to `out/`. The summary would then cover variant counts, SNV/indel split, and Ti/Tv ratio, which I have not computed.

## Deliverable note

The task asks for `variant_call_report.md`. The workspace protocol asks for `report/report.md`. I wrote the report to `report/report.md` per the workspace rules. If a `variant_call_report.md` is required too, it should be a copy of this file once results exist.
