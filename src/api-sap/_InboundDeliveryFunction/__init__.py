import logging
import json
import azure.functions as func
from ..shared_code.data_service import SAPDataService

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for Inbound Deliveries.')
    
    # Parse query parameters
    filters = {}
    delivery_number = req.params.get('deliveryNumber')
    vendor = req.params.get('vendor')
    plant = req.params.get('plant')
    material = req.params.get('material')
    date_from = req.params.get('dateFrom')
    date_to = req.params.get('dateTo')
    
    if delivery_number:
        filters["delivery_number"] = delivery_number
    if vendor:
        filters["vendor"] = vendor
    if plant:
        filters["plant"] = plant
    if material:
        filters["material"] = material
    if date_from and date_to:
        filters["date_from"] = date_from
        filters["date_to"] = date_to
    
    # Get data
    try:
        sap_service = SAPDataService()
        result = sap_service.get_inbound_deliveries(filters)
        
        # Return the result
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error processing inbound delivery request: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )