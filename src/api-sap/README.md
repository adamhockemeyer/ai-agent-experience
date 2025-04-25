# SAP Azure Functions API

This repository contains Azure Functions that serve as an API layer for SAP data operations. It includes endpoints for inventory, purchase orders, and inbound deliveries, along with Swagger/OpenAPI documentation.

## Prerequisites

- [Python 3.8+](https://www.python.org/downloads/)
- [Azure Functions Core Tools version 4.x](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local#install-the-azure-functions-core-tools)
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli) (for deployment)
- [Visual Studio Code](https://code.visualstudio.com/) with the Azure Functions extension (recommended but optional)

## Setup Instructions

### 1. Clone the Repository

Clone the repository to your local machine.

### 2. Create a Virtual Environment

Create and activate a Python virtual environment:

#### For Windows:

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate
```

#### For macOS/Linux:

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
source .venv/bin/activate
```

### 3. Install Dependencies

Install the required packages:

```bash
pip install -r requirements.txt
```

### 4. Configure Local Settings

Create a `local.settings.json` file in the root directory with the following content:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
  }
}
```

Update the SAP_API_URL and SAP_API_KEY values as needed.

## Running the Application Locally

Start the Azure Functions runtime:

```bash
# Install Azure Functiosn Core tools if needed
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

```bash
func start
```

This will start the function app locally, and you can access the API endpoints at http://localhost:7071.

## API Documentation

### Swagger/OpenAPI Documentation

The API includes Swagger/OpenAPI documentation, which can be accessed at these endpoints:

- Swagger JSON: `http://localhost:7071/swagger.json`
- Swagger UI: `http://localhost:7071/swagger`

## Available Endpoints

- **Inventory Function**: Retrieve SAP inventory data
- **Purchase Order Function**: Manage purchase orders in SAP
- **Inbound Delivery Function**: Handle inbound deliveries in SAP

## Deployment

### Deploy to Azure

Deploy using Azure Functions Core Tools:

```bash
func azure functionapp publish <your-function-app-name>
```

### Deploy using Azure CLI

```bash
az functionapp deployment source config-zip -g <resource-group> -n <app-name> --src <zip-file-path>
```

## Creating a Dynamic OpenAPI Specification

The function app includes capabilities to generate and serve a Swagger/OpenAPI specification based on your Azure Functions routes. See the swagger.py file for implementation details.

## Contributing

Please follow the project's coding standards and submit pull requests for any changes.

## License

See the LICENSE file for details.
