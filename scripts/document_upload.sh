#!/bin/bash
set -e

# Accept parameters
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -a|--storage-account-name) STORAGE_ACCOUNT_NAME="$2"; shift ;;
        -k|--storage-account-key) STORAGE_ACCOUNT_KEY="$2"; shift ;;
        -c|--blob-container-name) BLOB_CONTAINER_NAME="$2"; shift ;;
        -p|--local-documents-path) LOCAL_DOCUMENTS_PATH="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo "🔑 Loading parameters"

# Set defaults for optional parameters
BLOB_CONTAINER_NAME="${BLOB_CONTAINER_NAME:-documents}"
LOCAL_DOCUMENTS_PATH="${LOCAL_DOCUMENTS_PATH:-./documents}"

# Print debug info
echo "Using STORAGE_ACCOUNT_NAME: $STORAGE_ACCOUNT_NAME"
echo "Using BLOB_CONTAINER_NAME: $BLOB_CONTAINER_NAME"
echo "Using LOCAL_DOCUMENTS_PATH: $LOCAL_DOCUMENTS_PATH"

# Check required values
if [ -z "$STORAGE_ACCOUNT_NAME" ]; then
    echo "❌ STORAGE_ACCOUNT_NAME is not set. Please provide it using -a or --storage-account-name parameter."
    exit 1
fi

# If no key, get it from az
if [[ -z "$STORAGE_ACCOUNT_KEY" ]]; then
    echo "🔍 No storage account key provided, retrieving with az storage account keys list"
    STORAGE_ACCOUNT_KEY=$(az storage account keys list --account-name "$STORAGE_ACCOUNT_NAME" --query "[0].value" -o tsv)
fi

echo "📦 Creating storage account container if it doesn't exist"
az storage container create \
    --name "$BLOB_CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_ACCOUNT_KEY" \
    --output none

# Count local files
local_file_count=$(find "$LOCAL_DOCUMENTS_PATH" -type f | wc -l)
echo "📂 Found $local_file_count files in $LOCAL_DOCUMENTS_PATH to upload."

echo "⬆️  Uploading files to the storage account container"
az storage blob upload-batch \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_ACCOUNT_KEY" \
    --destination "$BLOB_CONTAINER_NAME" \
    --source "$LOCAL_DOCUMENTS_PATH" \
    --overwrite

# Count blobs in the container after upload
blob_count=$(az storage blob list \
    --container-name "$BLOB_CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_ACCOUNT_KEY" \
    --query "[].name" -o tsv | wc -l)

echo "✅ Upload complete. $local_file_count files in source, $blob_count blobs in container."
if [[ "$local_file_count" -ne "$blob_count" ]]; then
    echo "⚠️  Warning: Source file count and blob count do not match!"
fi