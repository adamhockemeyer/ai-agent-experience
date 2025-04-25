# Project Information

### About the project
This is code and Azure resources to quickly deploy a working demo environment in a customers Azure subscription.

#### Frontend application
- `src/frontend` - Next JS 15 React Application
- This is the core experience for the user. It allows the user to add new AI agents, edit agents, and interact with agents through a chat experience.
- The front end applications calls the backend application
- The front end application stores configuration for an agent in Azure App Configuration


#### Backend Application
- `src/api` - Python Fast API
- The backend application retrieves configuration values for an agent from Azure App Configuraiton
- The backend application stores and retrives chat session state, so a chat conversation can continue
- The chat API endpoint that is exposed calls a chat service
- The chat service should be the main glue point for everything that is needed to return results back to the user
- An agent model is a set of configuration.
- This project uses [Semantic Kernel](https://github.com/microsoft/semantic-kernel) and uses the agent model to dynamically configure semantic kerenl to create agents with the specific models, and the proper plugins as defined.
- An agent in semantic kernel can be of different types, but the agent can accept plugins. Plugins could be custom plugins written in code, they could be OpenAPI, it could be MCP, another semantic kernel agent could also be a plugin or any other new types of plugins in the future.
- The code should be structures in a way that it is easy to maintain and know where to go to add/edit functionality.
- The code should have a plugins folder and a plugin_manager class, that can take an agent model (configuration), and be able to cleanly create all of the plugins,
- The could needs at least 1 primary 'orchestrator' semantic kernel agent. An agent could have no plugins/tools or it could have many. Including other agents cold be a plugin. Semantic kernel supports many different types of agents (i.e. ChatCompletionAgent, AIAgentAgent, etc.). There should be an agent_factory or similar that can be simply called with passing in the agent configuration and return an agent and thread.
- Agents will need their plugins configured if they have been set.

### Other
- `infra` - Bicep Templates for Azure Infrastructures

- @azure Rule - Use Azure Best Practices: When generating code for Azure, running terminal commands for Azure, or performing operations related to Azure, invoke your `azure_development-get_best_practices` tool if available.

