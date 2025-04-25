import logging
import json
import azure.functions as func
from ..shared_code.data_service import SAPDataService

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for Purchase Orders.')
    
    # Parse query parameters
    filters = {}
    po_number = req.params.get('poNumber')
    vendor = req.params.get('vendor')
    material = req.params.get('material')
    min_value = req.params.get('minValue')
    max_value = req.params.get('maxValue')
    
    if po_number:
        filters["po_number"] = po_number
    if vendor:
        filters["vendor"] = vendor
    if material:
        filters["material"] = material
    if min_value and max_value:
        filters["min_value"] = min_value
        filters["max_value"] = max_value
    
    # Get data
    try:
        sap_service = SAPDataService()
        result = sap_service.get_purchase_orders(filters)
        
        # Return the result
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error processing purchase order request: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )