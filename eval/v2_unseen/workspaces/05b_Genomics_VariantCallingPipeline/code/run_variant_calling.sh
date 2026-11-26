#!/usr/bin/env bash
# Germline short-variant calling per data/pipeline_lock.txt:
#   GATK 4.1.0.0 HaplotypeCaller (GVCF) -> GenotypeGVCFs, b37 bundle from data/resource_paths.txt.
# Fails fast with an explicit message if any locked input or tool is missing.
set -uo pipefail

WS="/home/shawnyang/Documents/VeriLoop/eval/v2_unseen/workspaces/05b_Genomics_VariantCallingPipeline"
cd "$WS" || exit 1
OUT="$WS/outputs"
mkdir -p "$OUT" "$WS/out"

# Read reference paths from the locked resource file (no hard-coded paths).
REF=$(grep -E '^REF='   data/resource_paths.txt | cut -d= -f2-)
DBSNP=$(grep -E '^DBSNP=' data/resource_paths.txt | cut -d= -f2-)

fail=0
check() { # $1 = description, $2 = path or command
  if [ -e "$2" ] || command -v "$2" >/dev/null 2>&1; then
    echo "[OK]      $1: $2"
  else
    echo "[MISSING] $1: $2"; fail=1
  fi
}

echo "== Preflight checks =="
check "GATK launcher"        gatk
check "Reference FASTA"      "$REF"
check "Reference .fai"       "$REF.fai"
check "Reference .dict"      "${REF%.fasta}.dict"
check "dbSNP VCF"            "$DBSNP"
check "dbSNP index (.tbi)"   "$DBSNP.tbi"
while IFS=, read -r sid cram; do
  [ "$sid" = "sample_id" ] && continue
  check "CRAM for $sid"      "$WS/${cram#./}"
done < data/sample_manifest.csv

if [ "$fail" -ne 0 ]; then
  echo "ABORT: locked inputs/tools missing; no variant calls were produced." >&2
  exit 2
fi

# Verify GATK version matches the lock.
gatk --version 2>&1 | grep -q '4\.1\.0\.0' || { echo "ABORT: GATK is not 4.1.0.0"; exit 3; }

while IFS=, read -r sid cram; do
  [ "$sid" = "sample_id" ] && continue
  bam="$WS/${cram#./}"
  gvcf="$OUT/$sid.g.vcf.gz"
  vcf="$OUT/$sid.vcf.gz"
  echo "== $sid: HaplotypeCaller =="
  gatk HaplotypeCaller -R "$REF" -I "$bam" -O "$gvcf" -ERC GVCF --dbsnp "$DBSNP" || exit 4
  echo "== $sid: GenotypeGVCFs =="
  gatk GenotypeGVCFs -R "$REF" -V "$gvcf" -O "$vcf" --dbsnp "$DBSNP" || exit 5
  echo "== $sid: count variants =="
  gatk CountVariants -V "$vcf" 2>/dev/null | tail -1
done < data/sample_manifest.csv
