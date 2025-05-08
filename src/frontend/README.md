# Frontend Application

This is a Next.js React application that provides the core experience for the AI Agents demo environment. It allows users to add new AI agents, edit agents, and interact with agents through a chat experience.

## Environment Variables

The following environment variables are required to run the frontend application:

| Variable Name | Description | Required |
|---------------|-------------|----------|
| `CHAT_API_ENDPOINT` | URL of the backend API service that handles chat requests. Used to connect the frontend chat UI to the backend service. | Yes |
| `AZURE_APPCONFIG_ENDPOINT` | Endpoint URL for Azure App Configuration service. Used to access agent configurations stored in Azure App Configuration. | Yes* |
| `AZURE_APP_CONFIG_CONNECTION_STRING` | Connection string for Azure App Configuration. Alternative to AZURE_APPCONFIG_ENDPOINT when running outside of Azure. | No** |

\* Either `AZURE_APPCONFIG_ENDPOINT` or `AZURE_APP_CONFIG_CONNECTION_STRING` must be provided.  
\** Required only if `AZURE_APPCONFIG_ENDPOINT` is not set.

## Running the Application

### Local Development

1. Create a `.env.local` file in the app directory with the required environment variables.
2. Install dependencies:
   ```
   cd src/frontend/app
   npm install
   ```
3. Start the development server:
   ```
   npm run dev
   ```

### Docker Container

The application can be run as a Docker container:

```
docker build -t ai-agents-frontend -f src/frontend/Dockerfile .
docker run -p 3000:3000 -e NEXT_PUBLIC_CHAT_API_ENDPOINT=http://your-api-endpoint -e AZURE_APPCONFIG_ENDPOINT=your-appconfig-endpoint ai-agents-frontend
```