# for communication with Llama Stack
from llama_stack_client import LlamaStackClient
from llama_stack_client import Agent
from llama_stack_client.lib.agents.event_logger import EventLogger
from llama_stack_client import RAGDocument
from llama_stack_client.lib.agents.react.agent import ReActAgent
from llama_stack_client.lib.agents.react.tool_parser import ReActOutput

# pretty print of the results returned from the model/agent
from termcolor import cprint
import sys
sys.path.append('..')  
import uuid
import os

from dotenv import load_dotenv
load_dotenv()

base_url = "http://localhost:8321"


# Tavily search API key is required for some of our demos and must be provided to the client upon initialization.
# We will cover it in the agentic demos that use the respective tool. Please ignore this parameter for all other demos.
# tavily_search_api_key = os.getenv("TAVILY_SEARCH_API_KEY")
# if tavily_search_api_key is None:
#     provider_data = None
# else:
#     provider_data = {"tavily_search_api_key": tavily_search_api_key}


client = LlamaStackClient(
    base_url=base_url
)

print(f"Connected to Llama Stack server")

# model_id will later be used to pass the name of the desired inference model to Llama Stack Agents/Inference APIs
model_id = "granite3.2:8b"

temperature = float(os.getenv("TEMPERATURE", 0.0))
if temperature > 0.0:
    top_p = float(os.getenv("TOP_P", 0.95))
    strategy = {"type": "top_p", "temperature": temperature, "top_p": top_p}
else:
    strategy = {"type": "greedy"}

max_tokens = int(os.getenv("MAX_TOKENS", 512))

# sampling_params will later be used to pass the parameters to Llama Stack Agents/Inference APIs
sampling_params = {
    "strategy": strategy,
    "max_tokens": max_tokens,
}

# For this demo, we are using Milvus Lite, which is our preferred solution. Any other Vector DB supported by Llama Stack can be used.

# RAG vector DB settings
VECTOR_DB_EMBEDDING_MODEL = os.getenv("VDB_EMBEDDING")
VECTOR_DB_EMBEDDING_DIMENSION = int(os.getenv("VDB_EMBEDDING_DIMENSION", 384))
VECTOR_DB_CHUNK_SIZE = int(os.getenv("VECTOR_DB_CHUNK_SIZE", 512))
VECTOR_DB_PROVIDER_ID = os.getenv("VDB_PROVIDER")

# Unique DB ID for session
vector_db_id = f"test_vector_db_{uuid.uuid4()}"

stream_env = os.getenv("STREAM", "False")
# the Boolean 'stream' parameter will later be passed to Llama Stack Agents/Inference APIs
# any value non equal to 'False' will be considered as 'True'
stream = "True"

print(f"Inference Parameters:\n\tModel: {model_id}\n\tSampling Parameters: {sampling_params}\n\tstream: {stream}")


# Optional: Enter your MCP server URL here
atlassian_mcp_url = "http://192.168.0.2:8090/messages"

# Cleanup potentially stale/broken toolgroup from previous runs to avoid 500 on list()
try:
    client.toolgroups.unregister(toolgroup_id="mcp::atlassian")
    print("Cleaned up stale mcp::atlassian registration")
except Exception:
    pass

# Get list of registered tools and extract their toolgroup IDs
registered_tools = client.tools.list()
registered_toolgroups = [tool.toolgroup_id for tool in registered_tools]

if  "builtin::rag" not in registered_toolgroups: # Required
    client.toolgroups.register(
        toolgroup_id="builtin::rag",
        provider_id="milvus"
    )

if "mcp::atlassian" not in registered_toolgroups:
    client.toolgroups.register(
        toolgroup_id="mcp::atlassian",
        provider_id="model-context-protocol",
        mcp_endpoint={"uri": atlassian_mcp_url},
    )
# Get list of registered tools and extract their toolgroup IDs
_tools = client.tools.list()
_toolgroups = [tool.toolgroup_id for tool in _tools]

# Log the current toolgroups registered
print(f"Your Llama Stack server is already registered with the following tool groups: {set(_toolgroups)}\n")


# define and register the document collection to be used
client.vector_dbs.register(
    vector_db_id=vector_db_id,
    embedding_model=VECTOR_DB_EMBEDDING_MODEL or "all-MiniLM-L6-v2",
    embedding_dimension=VECTOR_DB_EMBEDDING_DIMENSION,
    provider_id=VECTOR_DB_PROVIDER_ID or "faiss",
)

# ingest the documents into the newly created document collection
urls = [
    ("https://docs.redhat.com/en/documentation/openshift_container_platform/4.11/pdf/support/OpenShift_Container_Platform-4.11-Support-en-US.pdf", "application/pdf"),
]
documents = [
    RAGDocument(
        document_id=f"num-{i}",
        content=url,
        mime_type=url_type,
        metadata={},
    )
    for i, (url, url_type) in enumerate(urls)
]
client.tool_runtime.rag_tool.insert(
    documents=documents,
    vector_db_id=vector_db_id,
    chunk_size_in_tokens=VECTOR_DB_CHUNK_SIZE,
)

model_prompt= """You are a helpful assistant. You have access to a number of tools.
Whenever a tool is called, be sure return the Response in a friendly and helpful tone."""

# Create simple agent with tools
agent = Agent(
    client,
    model=model_id, # replace this with your choice of model
    instructions = model_prompt , # update system prompt based on the model you are using
    tools=[dict(
            name="builtin::rag",
            args={
                "vector_db_ids": [vector_db_id],  # list of IDs of document collections to consider during retrieval
            },
        ), "mcp::atlassian"],
    tool_config={"tool_choice":"auto"},
    sampling_params=sampling_params
)

user_prompts = ["search confluence for any information on Non-compliance & Exceptions "]
session_id = agent.create_session(session_name="OCP_Slack_demo")
for i, prompt in enumerate(user_prompts):
    response = agent.create_turn(
        messages=[
            {
                "role":"user",
                "content": prompt
            }
        ],
        session_id=session_id,
        stream=stream,
    )
    for log in EventLogger().log(response):
        log.print()


