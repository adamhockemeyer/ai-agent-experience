#!/bin/bash
set -e

# Default values
BLOB_CONTAINER_NAME="documents"
EMBEDDING_DEPLOYMENT_NAME="embedding"
WAIT_FOR_INDEXER=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --storage-account-name) STORAGE_ACCOUNT_NAME="$2"; shift ;;
        --search-service-name) SEARCH_SERVICE_NAME="$2"; shift ;;
        --openai-endpoint) OPENAI_ENDPOINT="$2"; shift ;;
        --blob-container-name) BLOB_CONTAINER_NAME="$2"; shift ;;
        --embedding-deployment-name) EMBEDDING_DEPLOYMENT_NAME="$2"; shift ;;
        --wait-for-indexer) WAIT_FOR_INDEXER=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo "Setting up Azure AI Search indexes for document folders..."

# If parameters are not provided, try to get them from AZD environment
if [ -z "$STORAGE_ACCOUNT_NAME" ]; then
    # Get and trim any quotes
    STORAGE_ACCOUNT_NAME=$(azd env get-values --no-prompt | grep AZURE_STORAGE_ACCOUNT_NAME | cut -d '=' -f2 | tr -d '"' | tr -d "'")
fi

if [ -z "$SEARCH_SERVICE_NAME" ]; then
    # Try multiple possible environment variable names
    SEARCH_SERVICE_NAME=$(azd env get-values --no-prompt | grep AZURE_SEARCH_SERVICE_NAME | cut -d '=' -f2 | tr -d '"' | tr -d "'")
    if [ -z "$SEARCH_SERVICE_NAME" ]; then
        SEARCH_SERVICE_NAME=$(azd env get-values --no-prompt | grep AI_AGENTS_SEARCH_NAME | cut -d '=' -f2 | tr -d '"' | tr -d "'")
    fi
    if [ -z "$SEARCH_SERVICE_NAME" ]; then
        SEARCH_SERVICE_NAME=$(azd env get-values --no-prompt | grep AI_SEARCH_SERVICE | cut -d '=' -f2 | tr -d '"' | tr -d "'")
    fi
fi

if [ -z "$OPENAI_ENDPOINT" ]; then
    # Try to get full endpoint first
    OPENAI_ENDPOINT=$(azd env get-values --no-prompt | grep AZURE_OPENAI_ENDPOINT | cut -d '=' -f2 | tr -d '"' | tr -d "'")
    
    if [ -z "$OPENAI_ENDPOINT" ]; then
        # Fall back to constructing from service name
        OPENAI_SERVICE_NAME=$(azd env get-values --no-prompt | grep AZURE_OPENAI_SERVICE_NAME | cut -d '=' -f2 | tr -d '"' | tr -d "'")
        if [ -n "$OPENAI_SERVICE_NAME" ]; then
            OPENAI_ENDPOINT="https://${OPENAI_SERVICE_NAME}.openai.azure.com/"
        fi
    fi
fi

# Check if embedding deployment name is in environment
ENV_EMBEDDING_NAME=$(azd env get-values --no-prompt | grep AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME | cut -d '=' -f2 | tr -d '"' | tr -d "'")
if [ -n "$ENV_EMBEDDING_NAME" ]; then
    EMBEDDING_DEPLOYMENT_NAME=$ENV_EMBEDDING_NAME
fi

echo "Using Storage Account: $STORAGE_ACCOUNT_NAME"
echo "Using Search Service: $SEARCH_SERVICE_NAME"
echo "Using OpenAI Endpoint: $OPENAI_ENDPOINT"
echo "Using Blob Container: $BLOB_CONTAINER_NAME"
echo "Using Embedding Deployment: $EMBEDDING_DEPLOYMENT_NAME"

# Set up environment variables for the Python scripts
export AZURE_SEARCH_SERVICE_NAME=$SEARCH_SERVICE_NAME
export AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT_NAME
export AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT
export BLOB_CONTAINER_NAME=$BLOB_CONTAINER_NAME
export AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=$EMBEDDING_DEPLOYMENT_NAME

# Path to search setup scripts
SCRIPT_DIR="$(dirname "$0")"
SEARCH_SETUP_PATH="$SCRIPT_DIR/search_setup"

# Install dependencies
echo "Installing dependencies for search setup..."
pip install -r "$SEARCH_SETUP_PATH/requirements.txt"

# Run the search setup script
echo "Running search setup..."
WAIT_TIME=0
if [ "$WAIT_FOR_INDEXER" = true ]; then
    WAIT_TIME=60
fi
python "$SEARCH_SETUP_PATH/main.py" --wait $WAIT_TIME

echo "Search index setup completed!"