import json
import os
import logging
from datetime import datetime
from pathlib import Path

class SAPDataService:
    """Service to access SAP data from local files or Azure Blob Storage"""
    
    def __init__(self):
        self.storage_type = os.environ.get("DATA_STORAGE_TYPE", "local")
        self.data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        logging.info(f"Initializing SAPDataService with storage type: {self.storage_type}")
        
    def load_data(self, data_file):
        """Load data from the specified file"""
        if self.storage_type == "local":
            file_path = os.path.join(self.data_path, data_file)
            try:
                with open(file_path, 'r') as file:
                    return json.load(file)
            except Exception as e:
                logging.error(f"Error loading data from {file_path}: {str(e)}")
                raise
        elif self.storage_type == "blob":
            # Implementation for Azure Blob Storage
            # This is a placeholder for the actual Azure Blob Storage code
            from azure.storage.blob import BlobServiceClient
            connection_string = os.environ["AzureWebJobsStorage"]
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            container_name = "sap-data"
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=data_file)
            
            try:
                download_stream = blob_client.download_blob()
                data = json.loads(download_stream.readall().decode('utf-8'))
                return data
            except Exception as e:
                logging.error(f"Error loading data from blob {data_file}: {str(e)}")
                raise
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    def get_inbound_deliveries(self, filters=None):
        """Get inbound delivery data with optional filtering"""
        data = self.load_data("inbound_delivery.json")
        
        if not filters:
            return data
            
        # Apply filters if specified
        results = data["d"]["results"]
        filtered_results = []
        
        for delivery in results:
            include = True
            
            # Filter by inbound delivery number
            if "delivery_number" in filters and delivery["InboundDeliveryNumber"] != filters["delivery_number"]:
                include = False
                
            # Filter by vendor
            if "vendor" in filters and delivery["Vendor"] != filters["vendor"]:
                include = False
                
            # Filter by plant
            if "plant" in filters and delivery["ReceivingPlant"] != filters["plant"]:
                include = False
                
            # Filter by material - need to check items
            if "material" in filters:
                material_match = False
                for item in delivery["InboundDeliveryHeader_To_Item"]["results"]:
                    if item["Material"] == filters["material"]:
                        material_match = True
                        break
                if not material_match:
                    include = False
            
            # Filter by date range
            if "date_from" in filters and "date_to" in filters:
                delivery_date = self._parse_sap_date(delivery["PlannedDeliveryDate"])
                date_from = datetime.strptime(filters["date_from"], "%Y-%m-%d")
                date_to = datetime.strptime(filters["date_to"], "%Y-%m-%d")
                
                if not (date_from <= delivery_date <= date_to):
                    include = False
            
            if include:
                filtered_results.append(delivery)
        
        # Return filtered data
        filtered_data = {
            "d": {
                "results": filtered_results
            }
        }
        return filtered_data
    
    def get_inventory(self, filters=None):
        """Get inventory data with optional filtering"""
        data = self.load_data("inventory.json")
        
        if not filters:
            return data
            
        # Apply filters if specified
        results = data["d"]["results"]
        filtered_results = []
        
        for item in results:
            include = True
            
            # Filter by material
            if "material" in filters and item["Material"] != filters["material"]:
                include = False
                
            # Filter by plant
            if "plant" in filters and item["Plant"] != filters["plant"]:
                include = False
                
            # Filter by storage location
            if "storage_location" in filters and item["StorageLocation"] != filters["storage_location"]:
                include = False
                
            # Filter by available stock threshold
            if "min_stock" in filters:
                min_stock = float(filters["min_stock"])
                available_stock = float(item["AvailableStock"])
                if available_stock < min_stock:
                    include = False
            
            if include:
                filtered_results.append(item)
        
        # Return filtered data
        filtered_data = {
            "d": {
                "results": filtered_results
            }
        }
        return filtered_data
    
    def get_purchase_orders(self, filters=None):
        """Get purchase order data with optional filtering"""
        data = self.load_data("purchase_orders.json")
        
        if not filters:
            return data
            
        # Apply filters if specified
        results = data["d"]["results"]
        filtered_results = []
        
        for po in results:
            include = True
            
            # Filter by purchase order number
            if "po_number" in filters and po["PurchaseOrder"] != filters["po_number"]:
                include = False
                
            # Filter by vendor
            if "vendor" in filters and po["Vendor"] != filters["vendor"]:
                include = False
                
            # Filter by material - need to check items
            if "material" in filters:
                material_match = False
                for item in po["POHeader_To_Item"]["results"]:
                    if item["Material"] == filters["material"]:
                        material_match = True
                        break
                if not material_match:
                    include = False
            
            # Filter by value range
            if "min_value" in filters and "max_value" in filters:
                po_value = float(po["NetValue"])
                min_value = float(filters["min_value"])
                max_value = float(filters["max_value"])
                
                if not (min_value <= po_value <= max_value):
                    include = False
            
            if include:
                filtered_results.append(po)
        
        # Return filtered data
        filtered_data = {
            "d": {
                "results": filtered_results
            }
        }
        return filtered_data
    
    def _parse_sap_date(self, sap_date):
        """Parse SAP date format (/Date(timestamp)/) to datetime"""
        if not sap_date:
            return None
        
        # Extract timestamp from /Date(1234567890000)/
        timestamp_str = sap_date.replace("/Date(", "").replace(")/", "")
        timestamp_ms = int(timestamp_str)
        
        # Convert milliseconds to seconds for datetime
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt