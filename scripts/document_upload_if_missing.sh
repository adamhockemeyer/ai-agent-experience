#!/usr/bin/env bash
set -euo pipefail

VERBOSE=${VERBOSE:-0}
log_debug() { if [[ "$VERBOSE" == "1" ]]; then echo "[debug] $*"; fi }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -a|--storage-account-name) STORAGE_ACCOUNT_NAME="$2"; shift 2 ;;
    -k|--storage-account-key) STORAGE_ACCOUNT_KEY="$2"; shift 2 ;;
    -c|--blob-container-name) BLOB_CONTAINER_NAME="$2"; shift 2 ;;
    -p|--local-documents-path) LOCAL_DOCUMENTS_PATH="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 -a NAME [-c container] [-p path]"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

BLOB_CONTAINER_NAME=${BLOB_CONTAINER_NAME:-documents}
LOCAL_DOCUMENTS_PATH=${LOCAL_DOCUMENTS_PATH:-./documents}

if [[ -z "${STORAGE_ACCOUNT_NAME:-}" ]]; then
  echo "❌ storage account name required (-a)"; exit 1
fi
if [[ ! -d "$LOCAL_DOCUMENTS_PATH" ]]; then
  echo "⚠️  Local path '$LOCAL_DOCUMENTS_PATH' missing. Skipping."; exit 0
fi

if [[ -z "${STORAGE_ACCOUNT_KEY:-}" ]]; then
  echo "Retrieving storage account key..."
  STORAGE_ACCOUNT_KEY=$(az storage account keys list --account-name "$STORAGE_ACCOUNT_NAME" --query "[0].value" -o tsv)
fi

echo "Ensuring container '$BLOB_CONTAINER_NAME' exists..."
az storage container create --name "$BLOB_CONTAINER_NAME" --account-name "$STORAGE_ACCOUNT_NAME" --account-key "$STORAGE_ACCOUNT_KEY" --output none >/dev/null

echo "Listing existing blobs..."
mapfile -t EXISTING < <(az storage blob list --container-name "$BLOB_CONTAINER_NAME" --account-name "$STORAGE_ACCOUNT_NAME" --account-key "$STORAGE_ACCOUNT_KEY" --query "[].name" -o tsv || true)
declare -A EXISTING_SET
for b in "${EXISTING[@]}"; do
  # Strip potential carriage return from Windows line endings
  b=${b%$'\r'}
  [[ -n "$b" ]] && EXISTING_SET["$b"]=1 && log_debug "existing: '$b'"
done
echo "Existing blob count: ${#EXISTING_SET[@]}"

# Fast path: AzCopy sync if available
if command -v azcopy >/dev/null 2>&1; then
  echo "AzCopy detected; attempting incremental sync (no delete)."
  expiry=$(date -u -d "+1 hour" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+1H +%Y-%m-%dT%H:%M:%SZ || true)
  sas=$(az storage container generate-sas --name "$BLOB_CONTAINER_NAME" --account-name "$STORAGE_ACCOUNT_NAME" --account-key "$STORAGE_ACCOUNT_KEY" --permissions rlwacd --expiry "$expiry" -o tsv || true)
  if [[ -n "$sas" ]]; then
    dest="https://${STORAGE_ACCOUNT_NAME}.blob.core.windows.net/${BLOB_CONTAINER_NAME}?$sas"
    echo "Running: azcopy sync '$LOCAL_DOCUMENTS_PATH' '$dest'"
    if azcopy sync "$LOCAL_DOCUMENTS_PATH" "$dest" --recursive --delete-destination=false --overwrite=ifSourceNewer; then
      echo "✅ AzCopy sync completed."
      exit 0
    else
      echo "⚠️  AzCopy sync failed, falling back to per-file uploads." >&2
    fi
  else
    echo "⚠️  Failed to generate SAS; falling back to per-file uploads." >&2
  fi
fi

UPLOAD_COUNT=0
SKIP_COUNT=0
while IFS= read -r -d '' file; do
  rel=${file#${LOCAL_DOCUMENTS_PATH}/}
  rel=${rel#./}
  rel=${rel//\\//}
  # Normalize possible leading ./ or \r from Windows conversions
  rel=${rel%$'\r'}
  log_debug "candidate rel='$rel'"
  if [[ -n "${EXISTING_SET[$rel]:-}" ]]; then
    echo "Skip (exists): $rel"
    ((SKIP_COUNT++))
    continue
  fi
  echo "Uploading: $rel"
  az storage blob upload --account-name "$STORAGE_ACCOUNT_NAME" --account-key "$STORAGE_ACCOUNT_KEY" --container-name "$BLOB_CONTAINER_NAME" --name "$rel" --file "$file" --overwrite false --no-progress --output none
  ((UPLOAD_COUNT++))
done < <(find "$LOCAL_DOCUMENTS_PATH" -type f -print0)

echo "✅ Completed. Uploaded: $UPLOAD_COUNT, Skipped: $SKIP_COUNT"
