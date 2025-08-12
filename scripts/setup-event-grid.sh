#!/usr/bin/env bash
set -euo pipefail

# Disable MSYS path conversion for arguments (Git Bash) so /subscriptions/... IDs are not rewritten.
if [[ -n "${MSYSTEM:-}" ]]; then
  export MSYS2_ARG_CONV_EXCL='*'
fi

# setup-event-grid.sh
# Mirrors logic of setup-event-grid.ps1 for posix environments.
# Requires: az CLI. Optional: jq (for JSON parsing). If jq is absent, script will attempt a simplified path.

usage() {
  cat <<EOF
Usage: $0 \
  --storage-account-name NAME \
  --resource-group-name RG \
  --function-app-name FUNCAPP \
  --environment-name ENV \
  --location LOCATION [--debug]

Optional:
  --existing-system-topic-name NAME   # Reuse specified topic instead of detecting
  --debug                             # Verbose output (IDs, detection internals)
EOF
}

DEBUG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --storage-account-name) STORAGE_ACCOUNT_NAME="$2"; shift 2 ;;
    --resource-group-name) RESOURCE_GROUP_NAME="$2"; shift 2 ;;
    --function-app-name) FUNCTION_APP_NAME="$2"; shift 2 ;;
    --environment-name) ENVIRONMENT_NAME="$2"; shift 2 ;;
    --location) LOCATION="$2"; shift 2 ;;
  --existing-system-topic-name) EXISTING_SYSTEM_TOPIC_NAME="$2"; shift 2 ;;
  --debug) DEBUG=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

missing=()
[[ -z "${STORAGE_ACCOUNT_NAME:-}" ]] && missing+=(--storage-account-name)
[[ -z "${RESOURCE_GROUP_NAME:-}" ]] && missing+=(--resource-group-name)
[[ -z "${FUNCTION_APP_NAME:-}" ]] && missing+=(--function-app-name)
[[ -z "${ENVIRONMENT_NAME:-}" ]] && missing+=(--environment-name)
[[ -z "${LOCATION:-}" ]] && missing+=(--location)
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "❌ Missing required args: ${missing[*]}" >&2
  usage
  exit 1
fi

if [[ $DEBUG -eq 1 ]]; then
  echo "[debug] Enabling shell xtrace"
  set -x
fi

RESOLVED_PREFIX=${EVENTGRID_RESOURCE_PREFIX:-$ENVIRONMENT_NAME}
echo "=== Event Grid System Topic Setup (posix) ==="
echo "StorageAccount: $STORAGE_ACCOUNT_NAME"
echo "FunctionApp:   $FUNCTION_APP_NAME"
echo "Environment:   $ENVIRONMENT_NAME"
echo "Prefix Used:   $RESOLVED_PREFIX"
echo "Location:      $LOCATION"

echo "Retrieving storage account resource ID..."
STORAGE_ID=$(az resource show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP_NAME" --resource-type "Microsoft.Storage/storageAccounts" --query id -o tsv)
[[ $DEBUG -eq 1 ]] && echo "[debug] STORAGE_ID=$STORAGE_ID"
if [[ -z "$STORAGE_ID" ]]; then
  echo "Failed to retrieve storage account id" >&2; exit 1
fi

echo "Retrieving function app resource ID..."
FUNCTION_APP_ID=$(az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP_NAME" --query id -o tsv)
[[ $DEBUG -eq 1 ]] && echo "[debug] FUNCTION_APP_ID=$FUNCTION_APP_ID"
if [[ -z "$FUNCTION_APP_ID" ]]; then
  echo "Failed to retrieve function app id" >&2; exit 1
fi

TARGET_FUNCTION_NAME=event_grid_blob_trigger
MCP_FUNCTION_RESOURCE_ID="${FUNCTION_APP_ID}/functions/${TARGET_FUNCTION_NAME}"

echo "Verifying target function exists..."
if az functionapp function list --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP_NAME" --query "[].name" -o tsv | grep -E "(^|/)${TARGET_FUNCTION_NAME}$" >/dev/null 2>&1; then
  echo "✅ Function '${TARGET_FUNCTION_NAME}' found"
else
  echo "❌ Function '${TARGET_FUNCTION_NAME}' not found in app '${FUNCTION_APP_NAME}'" >&2
  exit 1
fi

echo "Discovering existing system topics in resource group..."
EXISTING_TOPIC_NAME=""
norm_target=$(echo "$STORAGE_ID" | tr 'A-Z' 'a-z' | sed 's#microsoft.storage.storageaccounts#microsoft.storage/storageaccounts#')
[[ $DEBUG -eq 1 ]] && echo "[debug] norm_target=$norm_target"

if [[ -n "${EXISTING_SYSTEM_TOPIC_NAME:-}" ]]; then
  echo "Using provided existing system topic (override): $EXISTING_SYSTEM_TOPIC_NAME"
  EXISTING_TOPIC_NAME="$EXISTING_SYSTEM_TOPIC_NAME"
else
  # Always enumerate names first (robust across CLI versions)
  mapfile -t _ALL_TOPIC_NAMES < <(az eventgrid system-topic list --resource-group "$RESOURCE_GROUP_NAME" --query "[].name" -o tsv 2>/dev/null || true)
  # Strip any CR characters (Git Bash / Windows line ending artifacts)
  for i in "${!_ALL_TOPIC_NAMES[@]}"; do
    _ALL_TOPIC_NAMES[$i]=$(echo -n "${_ALL_TOPIC_NAMES[$i]}" | tr -d '\r')
  done
  [[ $DEBUG -eq 1 ]] && echo "[debug] discovered topic names: ${_ALL_TOPIC_NAMES[*]:-<none>}"

  for tname in "${_ALL_TOPIC_NAMES[@]}"; do
    [[ -z "$tname" ]] && continue
    # Fetch source with per-topic show (more reliable than list aggregate)
    _src=$(az eventgrid system-topic show --name "$tname" --resource-group "$RESOURCE_GROUP_NAME" --query properties.source -o tsv 2>/dev/null || true)
    _src=$(echo -n "$_src" | tr -d '\r')
    if [[ -z "$_src" || "$_src" == "None" ]]; then
      [[ $DEBUG -eq 1 ]] && echo "[debug] topic $tname has empty source (skipping)"
      continue
    fi
    norm_src=$(echo "$_src" | tr 'A-Z' 'a-z' | sed 's#microsoft.storage.storageaccounts#microsoft.storage/storageaccounts#')
    [[ $DEBUG -eq 1 ]] && echo "[debug] topic $tname source=$_src norm_src=$norm_src"
    if [[ "$norm_src" == "$norm_target" ]]; then
      echo "✅ Found matching existing system topic: $tname"
      EXISTING_TOPIC_NAME="$tname"
      break
    fi
  done

  # Secondary heuristic: name contains storage account name if still not found
  if [[ -z "$EXISTING_TOPIC_NAME" ]]; then
    for tname in "${_ALL_TOPIC_NAMES[@]}"; do
      clean_name=$(echo -n "$tname" | tr -d '\r')
      if [[ "${clean_name,,}" == *"${STORAGE_ACCOUNT_NAME,,}"* ]]; then
        echo "[info] Heuristic name match selecting topic: $clean_name"
        EXISTING_TOPIC_NAME="$clean_name"
        break
      fi
    done
  fi
fi

if [[ -z "$EXISTING_TOPIC_NAME" ]]; then
  echo "[info] No matching existing system topic detected. Diagnostic dump:" >&2
  echo "[info] Listing system topics (name, source) in resource group $RESOURCE_GROUP_NAME:" >&2
  az eventgrid system-topic list --resource-group "$RESOURCE_GROUP_NAME" --query "[].{name:name,source:properties.source}" -o table || true
  echo "[info] Target STORAGE_ID (normalized) => $norm_target" >&2

  # Heuristic 1: name pattern contains storage account name (common for tracked topics)
  mapfile -t _ALL_TOPIC_NAMES < <(az eventgrid system-topic list --resource-group "$RESOURCE_GROUP_NAME" --query "[].name" -o tsv 2>/dev/null || true)
  for tname in "${_ALL_TOPIC_NAMES[@]}"; do
    if [[ "${tname,,}" == *"${STORAGE_ACCOUNT_NAME,,}"* ]]; then
      echo "[info] Heuristic name match -> $tname"
      EXISTING_TOPIC_NAME="$tname"
      break
    fi
  done

  # Heuristic 2: per-topic lookup of properties.source when list returned None
  if [[ -z "$EXISTING_TOPIC_NAME" ]]; then
    for tname in "${_ALL_TOPIC_NAMES[@]}"; do
      _src=$(az eventgrid system-topic show --name "$tname" --resource-group "$RESOURCE_GROUP_NAME" --query properties.source -o tsv 2>/dev/null || true)
      [[ -z "$_src" || "$_src" == "None" ]] && continue
      norm_src=$(echo "$_src" | tr 'A-Z' 'a-z' | sed 's#microsoft.storage.storageaccounts#microsoft.storage/storageaccounts#')
      [[ $DEBUG -eq 1 ]] && echo "[debug] per-topic show name=$tname source=$_src norm_src=$norm_src"
      if [[ "$norm_src" == "$norm_target" ]]; then
        echo "✅ Found existing system topic via per-topic show: $tname"
        EXISTING_TOPIC_NAME="$tname"
        break
      fi
    done
  fi

  if [[ -n "$EXISTING_TOPIC_NAME" ]]; then
    echo "[info] Using detected existing topic: $EXISTING_TOPIC_NAME"
  fi
fi

PARAMS=("prefix=${RESOLVED_PREFIX}" "location=${LOCATION}" "storageAccountId=${STORAGE_ID}" "mcpFunctionResourceId=${MCP_FUNCTION_RESOURCE_ID}" "deadLetterStorageAccountId=${STORAGE_ID}")
if [[ -n "$EXISTING_TOPIC_NAME" ]]; then
  CLEAN_EXISTING_TOPIC_NAME=$(echo -n "$EXISTING_TOPIC_NAME" | tr -d '\r')
  PARAMS+=("existingSystemTopicName=${CLEAN_EXISTING_TOPIC_NAME}")
  echo "Using existing system topic: $CLEAN_EXISTING_TOPIC_NAME"
else
  echo "No existing system topic found (or detection skipped); will create new one."
fi

echo "Deploying Event Grid resources via Bicep..."
set +e
DEPLOY_OUTPUT=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --template-file "infra/event-grid-native.bicep" \
  --parameters "${PARAMS[@]}" -o json 2>&1)
DEPLOY_EXIT=$?
set -e
echo "$DEPLOY_OUTPUT" > deployment_output.json

if [[ $DEPLOY_EXIT -ne 0 ]]; then
  if echo "$DEPLOY_OUTPUT" | grep -qi "existing tracked system topic" && [[ -n "${EXISTING_TOPIC_NAME}" ]]; then
    echo "[warn] Deployment reported existing tracked system topic; proceeding as success using $EXISTING_TOPIC_NAME"
  else
    echo "$DEPLOY_OUTPUT" >&2
    exit $DEPLOY_EXIT
  fi
fi

if command -v jq >/dev/null 2>&1; then
  SYSTEM_TOPIC_NAME=$(jq -r '.properties.outputs.systemTopicName.value' deployment_output.json 2>/dev/null || true)
  SUBSCRIPTION_NAME=$(jq -r '.properties.outputs.subscriptionName.value' deployment_output.json 2>/dev/null || true)
  IS_USING_EXISTING=$(jq -r '.properties.outputs.isUsingExistingTopic.value' deployment_output.json 2>/dev/null || true)
else
  SYSTEM_TOPIC_NAME="(jq not installed)"
  SUBSCRIPTION_NAME="(jq not installed)"
  IS_USING_EXISTING="(jq not installed)"
fi

echo "Deployment complete:"
echo "  System Topic: ${SYSTEM_TOPIC_NAME}"
  echo "  Subscription: ${SUBSCRIPTION_NAME}"
echo "  Using Existing: ${IS_USING_EXISTING}"

rm -f deployment_output.json || true

echo "🎉 Event Grid setup completed (posix)."
