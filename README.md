
### AI Agents Experience
---






### Appendix
---


### `--reload` Flag for MCP on Windows

The `--reload` flag seems to cause issues on Windows when trying to run MCP plugins. Remove the flag. 

[Remove --reload flag, for FastAPI](https://github.com/modelcontextprotocol/python-sdk/issues/359#issuecomment-2761351547)

### App Configuration Limits

Azure App Configuration (we use it to store configuration data for the agents), as a 10KB limit for the value of a key. If you are trying to store a very large system prompt (i.e. >8,000 characters or so), its possible you will hit a limit on value being saved. Ideally break down agents into smaller units of work, and keep their prompts focused. If it is still an issue, you would need to consider storing the prompts elsewhere (hardcoded in code, or CosmosDB, or file for example).


### Assigning Data Permissions for Cosmos DB

To assign data permissions for Azure Cosmos DB to a principal ID, follow these steps:

1. Create a Role Definition: Use the Azure CLI to create a custom role definition for your Cosmos DB account. This role will define the permissions needed for accessing data.

1. Assign the Role to a Principal: Use the az cosmosdb sql role assignment create command to assign the role to a principal ID. Replace <aad-principal-id> with the Object ID of the principal and <role-definition-id> with the ID of the role definition.

```bash
az cosmosdb sql role assignment create --resource-group "apichat-rg" --account-name "***" --role-definition-id "/subscriptions/******/resourceGroups/apichat-rg/providers/Microsoft.DocumentDB/databaseAccounts/******/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002" --principal-id "******" --scope "/subscriptions/******/resourceGroups/apichat-rg/providers/Microsoft.DocumentDB/databaseAccounts/******"
```

1. Validate Access: Ensure that the principal has the correct access by testing with application code using the Azure SDK.

For more detailed instructions, refer to the [official documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/security/how-to-grant-data-plane-role-based-access).

