# updated_swagger.py

import json
import os
import functools
from pathlib import Path

@functools.lru_cache(maxsize=1)
def generate_updated_swagger_definition():
    """
    Generate updated OpenAPI (Swagger) definition for SAP Data API
    with authentication parameters included
    """
    # Determine the server URL based on the environment
    function_app_name = os.environ.get("WEBSITE_HOSTNAME")
    
    # If running in Azure Functions, use the Azure URL
    if function_app_name:
        # Azure Functions URL format
        base_url = f"https://{function_app_name}/api"
        local_url = "http://localhost:7071/api"
        
        servers = [
            {
                "url": base_url,
                "description": "Production server"
            },
            {
                "url": local_url,
                "description": "Local development server"
            }
        ]
    else:
        # Running locally
        servers = [
            {
                "url": "http://localhost:7071/api",
                "description": "Local development server"
            }
        ]
    
    swagger_definition = {
        "openapi": "3.0.1",
        "info": {
            "title": "SAP Data API",
            "description": "API for accessing SAP data including inbound deliveries, inventory, and purchase orders",
            "version": "1.0.0"
        },
        "servers": servers,
        "components": {
            "securitySchemes": {
                "functionCode": {
                    "type": "apiKey",
                    "name": "code",
                    "in": "query"
                }
            },
            "schemas": {
                "Metadata": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string"
                        }
                    }
                },
                "InboundDeliveryItem": {
                    "type": "object",
                    "properties": {
                        "__metadata": {
                            "$ref": "#/components/schemas/Metadata"
                        },
                        "InboundDeliveryNumber": {
                            "type": "string"
                        },
                        "InboundDeliveryItem": {
                            "type": "string"
                        },
                        "Material": {
                            "type": "string"
                        },
                        "Quantity": {
                            "type": "string"
                        },
                        "Unit": {
                            "type": "string"
                        },
                        "Batch": {
                            "type": "string"
                        },
                        "PlannedGoodsReceiptDate": {
                            "type": "string"
                        }
                    }
                },
                "InboundDeliveryItems": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/InboundDeliveryItem"
                            }
                        }
                    }
                },
                "InboundDeliveryHeader": {
                    "type": "object",
                    "properties": {
                        "__metadata": {
                            "$ref": "#/components/schemas/Metadata"
                        },
                        "InboundDeliveryNumber": {
                            "type": "string"
                        },
                        "Vendor": {
                            "type": "string"
                        },
                        "PlannedDeliveryDate": {
                            "type": "string"
                        },
                        "ReceivingPlant": {
                            "type": "string"
                        },
                        "InboundDeliveryHeader_To_Item": {
                            "$ref": "#/components/schemas/InboundDeliveryItems"
                        }
                    }
                },
                "InboundDeliveryData": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/InboundDeliveryHeader"
                            }
                        }
                    }
                },
                "InboundDeliveryResponse": {
                    "type": "object",
                    "properties": {
                        "d": {
                            "$ref": "#/components/schemas/InboundDeliveryData"
                        }
                    }
                },
                "InventoryItem": {
                    "type": "object",
                    "properties": {
                        "__metadata": {
                            "$ref": "#/components/schemas/Metadata"
                        },
                        "Material": {
                            "type": "string"
                        },
                        "Plant": {
                            "type": "string"
                        },
                        "StorageLocation": {
                            "type": "string"
                        },
                        "AvailableStock": {
                            "type": "string"
                        },
                        "BaseUoM": {
                            "type": "string"
                        },
                        "PlantStreet": {
                            "type": "string"
                        },
                        "PlantCity": {
                            "type": "string"
                        },
                        "PlantZipCode": {
                            "type": "string"
                        },
                        "PlantRegion": {
                            "type": "string"
                        }
                    }
                },
                "InventoryData": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/InventoryItem"
                            }
                        }
                    }
                },
                "InventoryResponse": {
                    "type": "object",
                    "properties": {
                        "d": {
                            "$ref": "#/components/schemas/InventoryData"
                        }
                    }
                },
                "PurchaseOrderItem": {
                    "type": "object",
                    "properties": {
                        "__metadata": {
                            "$ref": "#/components/schemas/Metadata"
                        },
                        "PurchaseOrder": {
                            "type": "string"
                        },
                        "PurchaseOrderItem": {
                            "type": "string"
                        },
                        "Material": {
                            "type": "string"
                        },
                        "OrderQuantity": {
                            "type": "string"
                        },
                        "NetPrice": {
                            "type": "string"
                        },
                        "DeliveryDate": {
                            "type": "string"
                        }
                    }
                },
                "PurchaseOrderItems": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/PurchaseOrderItem"
                            }
                        }
                    }
                },
                "PurchaseOrderHeader": {
                    "type": "object",
                    "properties": {
                        "__metadata": {
                            "$ref": "#/components/schemas/Metadata"
                        },
                        "PurchaseOrder": {
                            "type": "string"
                        },
                        "Vendor": {
                            "type": "string"
                        },
                        "DocumentDate": {
                            "type": "string"
                        },
                        "Currency": {
                            "type": "string"
                        },
                        "NetValue": {
                            "type": "string"
                        },
                        "POHeader_To_Item": {
                            "$ref": "#/components/schemas/PurchaseOrderItems"
                        }
                    }
                },
                "PurchaseOrderData": {
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/PurchaseOrderHeader"
                            }
                        }
                    }
                },
                "PurchaseOrderResponse": {
                    "type": "object",
                    "properties": {
                        "d": {
                            "$ref": "#/components/schemas/PurchaseOrderData"
                        }
                    }
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "string"
                        }
                    }
                }
            }
        },
        "security": [
            {
                "functionCode": []
            }
        ],
        "paths": {
            "/inbound-deliveries": {
                "get": {
                    "summary": "Get inbound deliveries",
                    "description": "Returns inbound delivery data from SAP with optional filtering",
                    "operationId": "getInboundDeliveries",
                    "parameters": [
                        {
                            "name": "deliveryNumber",
                            "in": "query",
                            "description": "Filter by delivery number",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "vendor",
                            "in": "query",
                            "description": "Filter by vendor",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "plant",
                            "in": "query",
                            "description": "Filter by receiving plant",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "material",
                            "in": "query",
                            "description": "Filter by material",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "dateFrom",
                            "in": "query",
                            "description": "Filter by start date (YYYY-MM-DD)",
                            "schema": {
                                "type": "string",
                                "format": "date"
                            }
                        },
                        {
                            "name": "dateTo",
                            "in": "query",
                            "description": "Filter by end date (YYYY-MM-DD)",
                            "schema": {
                                "type": "string",
                                "format": "date"
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful operation",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/InboundDeliveryResponse"
                                    }
                                }
                            }
                        },
                        "500": {
                            "description": "Server error",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/inventory": {
                "get": {
                    "summary": "Get inventory data",
                    "description": "Returns inventory data from SAP with optional filtering",
                    "operationId": "getInventory",
                    "parameters": [
                        {
                            "name": "material",
                            "in": "query",
                            "description": "Filter by material",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "plant",
                            "in": "query",
                            "description": "Filter by plant",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "storageLocation",
                            "in": "query",
                            "description": "Filter by storage location",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "minStock",
                            "in": "query",
                            "description": "Filter by minimum available stock",
                            "schema": {
                                "type": "number",
                                "format": "float"
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful operation",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/InventoryResponse"
                                    }
                                }
                            }
                        },
                        "500": {
                            "description": "Server error",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/purchase-orders": {
                "get": {
                    "summary": "Get purchase order data",
                    "description": "Returns purchase order data from SAP with optional filtering",
                    "operationId": "getPurchaseOrders",
                    "parameters": [
                        {
                            "name": "poNumber",
                            "in": "query",
                            "description": "Filter by purchase order number",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "vendor",
                            "in": "query",
                            "description": "Filter by vendor",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "material",
                            "in": "query",
                            "description": "Filter by material",
                            "schema": {
                                "type": "string"
                            }
                        },
                        {
                            "name": "minValue",
                            "in": "query",
                            "description": "Filter by minimum PO value",
                            "schema": {
                                "type": "number",
                                "format": "float"
                            }
                        },
                        {
                            "name": "maxValue",
                            "in": "query",
                            "description": "Filter by maximum PO value",
                            "schema": {
                                "type": "number",
                                "format": "float"
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful operation",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PurchaseOrderResponse"
                                    }
                                }
                            }
                        },
                        "500": {
                            "description": "Server error",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    return swagger_definition

def save_updated_swagger_file():
    """
    Save the updated OpenAPI definition to a file in the project root
    """
    swagger_definition = generate_updated_swagger_definition()
    
    # Convert to JSON and save to the project root
    output_path = Path(__file__).parent.absolute / "swagger.json"
    
    with open(output_path, "w") as f:
        json.dump(swagger_definition, f, indent=2)
    
    print(f"Updated OpenAPI definition saved to {output_path}")
    return output_path

if __name__ == "__main__":
    save_updated_swagger_file()