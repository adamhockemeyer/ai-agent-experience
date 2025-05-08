"""
Module for managing Azure AI Search resources (data sources, indexes, skillsets, indexers).
"""
import logging
import requests
import time
from azure.core.exceptions import ResourceExistsError, HttpResponseError
from config import (
    get_credentials, 
    SEARCH_SERVICE_ENDPOINT, 
    STORAGE_ACCOUNT_NAME,
    BLOB_CONTAINER_NAME,
    OPENAI_ENDPOINT,
    OPENAI_EMBEDDING_DEPLOYMENT,
    SEMANTIC_CONFIG_NAME,
    VECTOR_SEARCH_CONFIG_NAME,
    EMBEDDING_DIMENSIONS,
    generate_index_name,
    generate_datasource_name,
    generate_skillset_name,
    generate_indexer_name
)
from document_explorer import get_folder_blob_prefix

logger = logging.getLogger(__name__)

class SearchResourceManager:
    """Manager for Azure AI Search resources with retry logic."""

    def __init__(self):
        """Initialize with Azure credentials."""
        self.credential = get_credentials()
        self.access_token = self.credential.get_token("https://search.azure.com/.default").token
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        # API version is required for all REST operations
        self.api_version = "2023-11-01"

    def _make_request(self, method, url, json=None, max_retries=3, backoff_factor=2):
        """Make an HTTP request with retry logic."""
        retry_count = 0
        while retry_count <= max_retries:
            try:
                response = requests.request(
                    method, 
                    url, 
                    headers=self.headers, 
                    json=json
                )
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                # Check if we should retry (temporary server error)
                if e.response.status_code in (429, 500, 502, 503, 504) and retry_count < max_retries:
                    retry_count += 1
                    wait_time = backoff_factor ** retry_count
                    logger.warning(f"Request failed with {e.response.status_code}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                logger.error(f"Request failed: {str(e)}")
                raise

    def _resource_exists(self, resource_type, resource_name):
        """Check if a resource exists."""
        url = f"{SEARCH_SERVICE_ENDPOINT}/{resource_type}/{resource_name}?api-version={self.api_version}"
        try:
            response = requests.get(url, headers=self.headers)
            return response.status_code == 200
        except:
            return False

    def create_data_source(self, folder_name):
        """Create a data source for a specific document folder."""
        datasource_name = generate_datasource_name(folder_name)
        
        # Check if data source exists
        if self._resource_exists("datasources", datasource_name):
            logger.info(f"Data source '{datasource_name}' already exists. Updating...")
            method = "PUT"
            url = f"{SEARCH_SERVICE_ENDPOINT}/datasources/{datasource_name}?api-version={self.api_version}"
        else:
            logger.info(f"Creating data source '{datasource_name}'...")
            method = "POST"
            url = f"{SEARCH_SERVICE_ENDPOINT}/datasources?api-version={self.api_version}"
        
        # Data source definition
        data_source_payload = {
            "name": datasource_name,
            "description": f"Documents from {folder_name} folder",
            "type": "azureblob",
            "credentials": {
                "connectionString": f"ResourceId=/subscriptions/${{AZURE_SUBSCRIPTION_ID}}/resourceGroups/${{AZURE_RESOURCE_GROUP}}/providers/Microsoft.Storage/storageAccounts/{STORAGE_ACCOUNT_NAME}"
            },
            "container": {
                "name": BLOB_CONTAINER_NAME,
                "query": get_folder_blob_prefix(folder_name)
            }
        }
        
        try:
            response = self._make_request(method, url, json=data_source_payload)
            logger.info(f"Data source '{datasource_name}' created/updated successfully")
            return response.json()
        except Exception as e:
            logger.error(f"Error creating data source: {str(e)}")
            raise

    def create_search_index(self, folder_name):
        """Create a search index for a specific document folder."""
        index_name = generate_index_name(folder_name)
        
        # Check if index exists
        if self._resource_exists("indexes", index_name):
            logger.info(f"Index '{index_name}' already exists. Updating...")
            method = "PUT"
            url = f"{SEARCH_SERVICE_ENDPOINT}/indexes/{index_name}?api-version={self.api_version}"
        else:
            logger.info(f"Creating index '{index_name}'...")
            method = "POST"
            url = f"{SEARCH_SERVICE_ENDPOINT}/indexes?api-version={self.api_version}"
        
        # Index definition with vector search capabilities
        index_definition = {
            "name": index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "searchable": True, "filterable": True},
                {"name": "metadata_storage_name", "type": "Edm.String", "searchable": True, "filterable": True},
                {"name": "metadata_storage_path", "type": "Edm.String", "searchable": True, "filterable": True},
                {"name": "metadata_content_type", "type": "Edm.String", "searchable": True, "filterable": True},
                {"name": "content", "type": "Edm.String", "searchable": True, "analyzer": "standard.lucene"},
                {"name": "title", "type": "Edm.String", "searchable": True, "analyzer": "standard.lucene"},
                {"name": "chunk_id", "type": "Edm.String", "filterable": True},
                {"name": "parent_id", "type": "Edm.String", "filterable": True},
                {"name": "folder_name", "type": "Edm.String", "filterable": True, "facetable": True},
                {
                    "name": "embedding", 
                    "type": "Collection(Edm.Single)", 
                    "searchable": True, 
                    "dimensions": EMBEDDING_DIMENSIONS, 
                    "vectorSearchConfiguration": VECTOR_SEARCH_CONFIG_NAME
                }
            ],
            "vectorSearch": {
                "algorithmConfigurations": [
                    {
                        "name": VECTOR_SEARCH_CONFIG_NAME,
                        "kind": "hnsw",
                        "hnsw": {
                            "m": 4,
                            "efConstruction": 400,
                            "efSearch": 500,
                            "metric": "cosine"
                        }
                    }
                ]
            },
            "semantic": {
                "configurations": [
                    {
                        "name": SEMANTIC_CONFIG_NAME,
                        "prioritizedFields": {
                            "titleField": {"fieldName": "title"},
                            "contentFields": [{"fieldName": "content"}],
                            "keywordsFields": []
                        }
                    }
                ]
            }
        }
        
        try:
            response = self._make_request(method, url, json=index_definition)
            logger.info(f"Index '{index_name}' created/updated successfully")
            return response.json()
        except Exception as e:
            logger.error(f"Error creating index: {str(e)}")
            raise

    def create_skillset(self, folder_name):
        """Create a skillset for a specific document folder."""
        skillset_name = generate_skillset_name(folder_name)
        
        # Check if skillset exists
        if self._resource_exists("skillsets", skillset_name):
            logger.info(f"Skillset '{skillset_name}' already exists. Updating...")
            method = "PUT"
            url = f"{SEARCH_SERVICE_ENDPOINT}/skillsets/{skillset_name}?api-version={self.api_version}"
        else:
            logger.info(f"Creating skillset '{skillset_name}'...")
            method = "POST"
            url = f"{SEARCH_SERVICE_ENDPOINT}/skillsets?api-version={self.api_version}"
        
        # Skillset definition with document cracking and text embedding skills
        skillset_definition = {
            "name": skillset_name,
            "description": f"Skillset for {folder_name} document processing with embeddings",
            "skills": [
                {
                    "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
                    "name": "split-text",
                    "description": "Split text into pages/chunks",
                    "context": "/document",
                    "textSplitMode": "pages",
                    "maximumPageLength": 4000,
                    "inputs": [
                        {
                            "name": "text",
                            "source": "/document/content"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "textItems",
                            "targetName": "pages"
                        }
                    ]
                },
                {
                    "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
                    "name": "embedding",
                    "description": "Create embeddings for content",
                    "context": "/document/pages/*",
                    "resourceUri": OPENAI_ENDPOINT,
                    "deploymentId": OPENAI_EMBEDDING_DEPLOYMENT,
                    "authenticationKind": "systemAssignedManagedIdentity",
                    "inputs": [
                        {
                            "name": "text",
                            "source": "/document/pages/*"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "embedding",
                            "targetName": "embedding"
                        }
                    ]
                },
                {
                    "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
                    "name": "folder-name-skill",
                    "description": "Add folder name to each document",
                    "context": "/document",
                    "uri": "https://example.com/placeholder", # This is a placeholder - we use inline program in httpHeaders
                    "httpMethod": "POST",
                    "httpHeaders": {
                        "program": f"return {{ 'folder_name': '{folder_name}' }};"
                    },
                    "inputs": [],
                    "outputs": [
                        {
                            "name": "folder_name",
                            "targetName": "folder_name"
                        }
                    ]
                }
            ],
            "cognitiveServices": {
                "@odata.type": "#Microsoft.Azure.Search.DefaultCognitiveServices",
                "description": "Using system assigned managed identity"
            }
        }
        
        try:
            response = self._make_request(method, url, json=skillset_definition)
            logger.info(f"Skillset '{skillset_name}' created/updated successfully")
            return response.json()
        except Exception as e:
            logger.error(f"Error creating skillset: {str(e)}")
            raise

    def create_indexer(self, folder_name):
        """Create an indexer for a specific document folder."""
        indexer_name = generate_indexer_name(folder_name)
        datasource_name = generate_datasource_name(folder_name)
        index_name = generate_index_name(folder_name)
        skillset_name = generate_skillset_name(folder_name)
        
        # Check if indexer exists
        if self._resource_exists("indexers", indexer_name):
            logger.info(f"Indexer '{indexer_name}' already exists. Updating...")
            method = "PUT"
            url = f"{SEARCH_SERVICE_ENDPOINT}/indexers/{indexer_name}?api-version={self.api_version}"
        else:
            logger.info(f"Creating indexer '{indexer_name}'...")
            method = "POST"
            url = f"{SEARCH_SERVICE_ENDPOINT}/indexers?api-version={self.api_version}"
        
        # Indexer definition that ties everything together
        indexer_definition = {
            "name": indexer_name,
            "dataSourceName": datasource_name,
            "targetIndexName": index_name,
            "skillsetName": skillset_name,
            "schedule": {
                "interval": "PT12H"  # Run every 12 hours
            },
            "parameters": {
                "batchSize": 1,
                "maxFailedItems": 10,
                "maxFailedItemsPerBatch": 5,
                "configuration": {
                    "dataToExtract": "contentAndMetadata",
                    "parsingMode": "default",
                    "imageAction": "generateNormalizedImages"
                }
            },
            "fieldMappings": [
                {
                    "sourceFieldName": "metadata_storage_path",
                    "targetFieldName": "metadata_storage_path",
                    "mappingFunction": {"name": "base64Encode"}
                },
                {
                    "sourceFieldName": "metadata_storage_name",
                    "targetFieldName": "metadata_storage_name"
                },
                {
                    "sourceFieldName": "metadata_content_type",
                    "targetFieldName": "metadata_content_type"
                }
            ],
            "outputFieldMappings": [
                {
                    "sourceFieldName": "/document/pages/*",
                    "targetFieldName": "content",
                    "mappingFunction": {"name": "extractFromArray", "parameters": {"elementExtractor": "content"}}
                },
                {
                    "sourceFieldName": "/document/pages/*/embedding",
                    "targetFieldName": "embedding"
                },
                {
                    "sourceFieldName": "/document/folder_name",
                    "targetFieldName": "folder_name"
                }
            ]
        }
        
        try:
            response = self._make_request(method, url, json=indexer_definition)
            logger.info(f"Indexer '{indexer_name}' created/updated successfully")
            return response.json()
        except Exception as e:
            logger.error(f"Error creating indexer: {str(e)}")
            raise

    def run_indexer(self, folder_name):
        """Run the indexer for a specific document folder."""
        indexer_name = generate_indexer_name(folder_name)
        url = f"{SEARCH_SERVICE_ENDPOINT}/indexers/{indexer_name}/run?api-version={self.api_version}"
        
        try:
            response = requests.post(url, headers=self.headers)
            if response.status_code == 202:
                logger.info(f"Indexer '{indexer_name}' is running...")
                return True
            else:
                logger.warning(f"Failed to run indexer: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error running indexer: {str(e)}")
            raise

    def check_indexer_status(self, folder_name):
        """Check the status of the indexer for a specific document folder."""
        indexer_name = generate_indexer_name(folder_name)
        url = f"{SEARCH_SERVICE_ENDPOINT}/indexers/{indexer_name}/status?api-version={self.api_version}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            status = response.json()
            
            logger.info(f"Indexer '{indexer_name}' status: {status.get('status', 'Unknown')}")
            
            last_result = status.get('lastResult', {})
            if last_result:
                logger.info(f"Last result: {last_result.get('status', 'No runs yet')}")
                
            errors = last_result.get('errors', [])
            if errors:
                logger.error(f"Indexer errors: {errors}")
                
            return status
        except Exception as e:
            logger.error(f"Error checking indexer status: {str(e)}")
            raise