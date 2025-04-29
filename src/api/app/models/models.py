from typing import List, Dict, Literal, Optional, Any
from pydantic import BaseModel, ConfigDict, Field

class MsgPayload(BaseModel):
    msg_id: int
    msg_name: str



class Authentication(BaseModel):
    type: Literal["Anonymous", "Header", "EntraID-AppIdentity", "EntraID-OnBehalfOf"] = Field(..., description="Authentication type (e.g., 'Header')")
    headerName: Optional[str] = Field(None, description="Name of the header when type is 'Header'")
    headerValue: Optional[str] = Field(None, description="Value of the header when type is 'Header'")
    
    model_config = ConfigDict(extra="allow")

class Tool(BaseModel):
    id: str
    name: str
    type: str
    specUrl: Optional[str] = None
    authentications: Optional[List[Authentication]] = None
    mcpDefinition: Optional[str] = None
    # Add other tool properties as needed
    
    model_config = ConfigDict(extra="allow")

class ModelSelection(BaseModel):
    provider: Literal["AzureAIInference", "AzureOpenAI"]
    model: str
    
    model_config = ConfigDict(extra="allow")

class Agent(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    systemPrompt: str
    defaultPrompts: List[str]
    agentType: Literal["ChatCompletionAgent", "AzureAIAgent"] = "ChatCompletionAgent"
    foundryAgentId: Optional[str] = None
    modelSelection: ModelSelection
    codeInterpreter: bool
    fileUpload: bool
    maxTurns: int
    tools: List[Tool]
    requireJsonResponse: bool
    displayFunctionCallStatus: bool = Field(False, description="Whether to display function call status in the response stream")
    
    model_config = ConfigDict(extra="allow")

class ChatRequest(BaseModel):
    session_id: str
    agent_id: str
    input: str

class ChatResponse(BaseModel):
    session_id: str
    response: str
    usage: Optional[Dict[str, Any]] = None

