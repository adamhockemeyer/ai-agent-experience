"""
Main script to set up Azure AI Search with vector capabilities for multiple document folders.
"""
import os
import sys
import time
import logging
import argparse
from document_explorer import get_document_folders, get_local_document_folders
from search_resource_manager import SearchResourceManager

logger = logging.getLogger(__name__)

def setup_search_resources_for_folder(search_manager, folder_name, wait_time=0):
    """Set up all search resources for a specific folder."""
    try:
        # 1. Create the data source connection
        logger.info(f"Creating data source for '{folder_name}'...")
        data_source = search_manager.create_data_source(folder_name)
        logger.info(f"Data source for '{folder_name}' created successfully")
        
        # 2. Create the search index
        logger.info(f"Creating search index for '{folder_name}'...")
        index = search_manager.create_search_index(folder_name)
        logger.info(f"Search index for '{folder_name}' created successfully")
        
        # 3. Create the AI skillset
        logger.info(f"Creating AI skillset for '{folder_name}'...")
        skillset = search_manager.create_skillset(folder_name)
        logger.info(f"AI skillset for '{folder_name}' created successfully")
        
        # 4. Create and run the indexer
        logger.info(f"Creating and running indexer for '{folder_name}'...")
        indexer = search_manager.create_indexer(folder_name)
        search_manager.run_indexer(folder_name)
        logger.info(f"Indexer for '{folder_name}' created and running")
        
        # 5. Check indexer status if wait time specified
        if wait_time > 0:
            logger.info(f"Waiting {wait_time} seconds to check indexer status...")
            time.sleep(wait_time)
            status = search_manager.check_indexer_status(folder_name)
            logger.info(f"Indexer status: {status.get('status', 'Unknown')}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to set up search resources for '{folder_name}': {str(e)}")
        return False

def setup_all_search_resources(storage_mode='cloud', local_documents_path=None, wait_time=0):
    """Set up search resources for all document folders."""
    try:
        search_manager = SearchResourceManager()
        
        # Get list of folders to process
        if storage_mode == 'local' and local_documents_path:
            folders = get_local_document_folders(local_documents_path)
        else:
            folders = get_document_folders()
            
        if not folders:
            logger.warning("No document folders found. Nothing to index.")
            return True
            
        logger.info(f"Found {len(folders)} document folders: {', '.join(folders)}")
        
        # Process each folder
        results = {}
        for folder in folders:
            logger.info(f"Processing folder: {folder}")
            success = setup_search_resources_for_folder(search_manager, folder, wait_time=wait_time)
            results[folder] = "Success" if success else "Failed"
        
        # Print summary
        logger.info("=== Search Setup Summary ===")
        for folder, status in results.items():
            logger.info(f"{folder}: {status}")
            
        # Check if any failures occurred
        return all(status == "Success" for status in results.values())
        
    except Exception as e:
        logger.error(f"Failed to set up search resources: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Set up Azure AI Search resources for document indexing')
    parser.add_argument('--mode', choices=['cloud', 'local'], default='cloud',
                      help='Mode of operation: cloud (use blob storage) or local (use local files)')
    parser.add_argument('--documents-path', default=None,
                      help='Path to local documents folder (only used in local mode)')
    parser.add_argument('--wait', type=int, default=0, 
                      help='Time in seconds to wait for indexers to complete')
    args = parser.parse_args()
    
    success = setup_all_search_resources(
        storage_mode=args.mode, 
        local_documents_path=args.documents_path,
        wait_time=args.wait
    )
    
    sys.exit(0 if success else 1)