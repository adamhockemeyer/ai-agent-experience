# function_app.py
from pathlib import Path
import azure.functions as func
import logging
import json
import os
from azure.core.exceptions import AzureError

# Create the Function App
app = func.FunctionApp()

@app.route(route="swagger.json", auth_level=func.AuthLevel.ANONYMOUS)
def serve_swagger_json(req: func.HttpRequest) -> func.HttpResponse:
    """Serves the dynamic OpenAPI (Swagger) definition as JSON"""
    try:
        # Import the swagger generator module and generate the dynamic definition
        from swagger import generate_updated_swagger_definition
        swagger_definition = generate_updated_swagger_definition()
        swagger_json = json.dumps(swagger_definition, indent=2)
        
        # Return the Swagger JSON
        return func.HttpResponse(
            body=swagger_json,
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error generating Swagger definition: {str(e)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": f"Error serving Swagger definition: {str(e)}"}),
            mimetype="application/json",
            status_code=500
        )

@app.route(route="swagger", auth_level=func.AuthLevel.ANONYMOUS)
def serve_swagger_ui(req: func.HttpRequest) -> func.HttpResponse:
    """Serves the Swagger UI with authentication examples"""
    
    # Get the host based on the environment
    host = os.environ.get("WEBSITE_HOSTNAME")
    if host:
        # Azure Functions URL format
        base_url = f"https://{host}/api"
    else:
        # Running locally
        base_url = "http://localhost:7071/api"
    
    swagger_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SAP Data API - Swagger UI</title>
    <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui.min.css" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        
        *,
        *:before,
        *:after {{
            box-sizing: inherit;
        }}
        
        body {{
            margin: 0;
            background: #fafafa;
        }}
        
        .topbar {{
            display: none;
        }}
        
        .swagger-ui .info .title {{
            color: #3b4151;
        }}
        
        .auth-info-box {{
            margin: 20px 0;
            padding: 15px;
            background-color: #e8f4f8;
            border-left: 5px solid #1890ff;
            border-radius: 3px;
        }}
        
        .auth-examples {{
            margin: 10px 0;
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 3px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div id="custom-auth-info" class="auth-info-box" style="display: none;">
        <h3>Authentication Information</h3>
        <p>This API requires authentication using the Azure Function key as a query parameter.</p>
        
        <h4>How to use:</h4>
        <p>Add the <code>code</code> parameter to your requests:</p>
        
        <div class="auth-examples">
            <p>{base_url}/inbound-deliveries?code=YOUR_FUNCTION_KEY</p>
        </div>
        
        <h4>Adding filters:</h4>
        <p>Append additional filter parameters after the code parameter:</p>
        
        <div class="auth-examples">
            <p>{base_url}/inbound-deliveries?code=YOUR_FUNCTION_KEY&vendor=STEEL-VEND-01</p>
            <p>{base_url}/inventory?code=YOUR_FUNCTION_KEY&material=MAT-HR-COIL&plant=1010</p>
        </div>
        
        <p>For local testing, you can omit the code parameter:</p>
        <div class="auth-examples">
            <p>http://localhost:7071/api/inbound-deliveries?vendor=STEEL-VEND-01</p>
        </div>
    </div>
    
    <div id="swagger-ui"></div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui-bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui-standalone-preset.min.js"></script>
    <script>
        window.onload = function() {{
            // Get the current URL to determine the path to swagger.json
            var url = window.location.href;
            var basePath = url.substring(0, url.lastIndexOf('/'));
            var swaggerJsonUrl = basePath + "/swagger.json";
            
            // Show our custom auth info box
            document.getElementById('custom-auth-info').style.display = 'block';
            
            // Initialize Swagger UI
            const ui = SwaggerUIBundle({{
                url: swaggerJsonUrl,
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout"
            }});
            
            window.ui = ui;
        }};
    </script>
</body>
</html>
    """
    
    return func.HttpResponse(
        body=swagger_html,
        mimetype="text/html",
        status_code=200
    )

# Define routes using decorators with explicit method specification
@app.route(route="inbound-deliveries", methods=["GET"])
def inbound_deliveries(req: func.HttpRequest) -> func.HttpResponse:
    """Returns inbound delivery data from SAP with optional filtering"""
    from shared_code.data_service import SAPDataService
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
            body=json.dumps(result, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
    except AzureError as ae:
        logging.error(f"Azure error processing inbound delivery request: {str(ae)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": f"Azure error: {str(ae)}"}),
            mimetype="application/json",
            status_code=500
        )
    except Exception as e:
        logging.error(f"Error processing inbound delivery request: {str(e)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": f"Error: {str(e)}"}),
            mimetype="application/json",
            status_code=500
        )

@app.route(route="inventory")
def inventory(req: func.HttpRequest) -> func.HttpResponse:
    """Returns inventory data from SAP with optional filtering"""
    from shared_code.data_service import SAPDataService
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
            body=json.dumps(result, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
    except AzureError as ae:
        logging.error(f"Azure error processing inventory request: {str(ae)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": f"Azure error: {str(ae)}"}),
            mimetype="application/json",
            status_code=500
        )
    except Exception as e:
        logging.error(f"Error processing inventory request: {str(e)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": f"Error: {str(e)}"}),
            mimetype="application/json",
            status_code=500
        )

@app.route(route="purchase-orders", methods=["GET"])
def purchase_orders(req: func.HttpRequest) -> func.HttpResponse:
    """Returns purchase order data from SAP with optional filtering"""
    from shared_code.data_service import SAPDataService
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
            body=json.dumps(result, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
    except AzureError as ae:
        logging.error(f"Azure error processing purchase order request: {str(ae)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": f"Azure error: {str(ae)}"}),
            mimetype="application/json",
            status_code=500
        )
    except Exception as e:
        logging.error(f"Error processing purchase order request: {str(e)}", exc_info=True)
        return func.HttpResponse(
            body=json.dumps({"error": f"Error: {str(e)}"}),
            mimetype="application/json",
            status_code=500
        )