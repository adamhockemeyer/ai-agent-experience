import logging
import json
import azure.functions as func
from ..shared_code.data_service import SAPDataService

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for Inventory.')
    
    # Parse query parameters
    filters = {}
    material = req.params.get('material')
    plant = req.params.get('plant')
    storage_location = req.params.get('storageLocation')
    min_stock = req.params.get('minStock')
    
    if material:
        filters["material"] = material
    if plant:
        filters["plant"] = plant
    if storage_location:
        filters["storage_location"] = storage_location
    if min_stock:
        filters["min_stock"] = min_stock
    
    # Get data
    try:
        sap_service = SAPDataService()
        result = sap_service.get_inventory(filters)
        
        # Return the result
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error processing inventory request: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )