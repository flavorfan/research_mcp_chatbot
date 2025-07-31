from contextlib import AsyncExitStack
from dotenv import load_dotenv
# from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import List, TypedDict, Dict
import os
from openai import AzureOpenAI
import json
import asyncio
import nest_asyncio

nest_asyncio.apply()

load_dotenv()

class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict


class FunctionDefinition(TypedDict):
    name: str
    description: str
    parameters: dict

class ToolDefinitionOpenAI(TypedDict):
    type: str
    function: FunctionDefinition

# def convert_mcp_tool(mcp_tool):
#     return {
#         "type": "function",
#         "function": {
#             "name": mcp_tool.__name__,
#             "description": mcp_tool.__doc__ or "",
#             "parameters": getattr(mcp_tool, "parameters", {}) 
#         }
#     }

def convert_mcp_tool(mcp_tool: ToolDefinition) -> ToolDefinitionOpenAI:
    """Convert MCP tool definition to OpenAI function definition."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool["description"],
            "parameters": mcp_tool["input_schema"]
        }
    }

class MCP_ChatBot:

    def __init__(self):
        # Initialize session and client objects
        # self.session: ClientSession = None
        # self.sessions: List[ClientSession] = [] # new
        self.exit_stack = AsyncExitStack() # new
        
        self.llm  = AzureOpenAI(
            api_key = os.getenv("DIAL_API_KEY"), 
            api_version = "2024-02-01",
            azure_endpoint = "https://ai-proxy.lab.epam.com"
            ) 
        self.model_name = "gpt-4o-mini-2024-07-18"
        # self.available_tools: List[dict] = []
        self.available_tools: List[ToolDefinition] = [] # new
        # Session 
        # self.tool_to_session: Dict[str, ClientSession] = {} # new
        self.available_prompts = []
        self.sessions = {}

    async def process_query(self, query):
        print(f"\nProcessing query: {query}")
        messages = [{'role':'user', 'content':query}]
        # process_query = True
        while True:
            # assistant_content = []
            resp = self.llm.chat.completions.create(
                model = self.model_name,
                tools = self.openai_tools,  # convert to OpenAI tool format
                tool_choice = "auto",  # let the LLM decide which tool to use
                messages = messages,
                max_tokens = 2024,
                temperature = 0.0
            )
            has_tool_use = False
            msg = resp.choices[0].message
            messages.append(msg)
            # print(f"msg: {msg.model_dump_json(indent=2)}")

            if not msg.tool_calls:
                # If no tool calls, just print the response text
                print(msg.content)
                # process_query = False
            else:
                for tc in msg.tool_calls:
                    has_tool_use = True
                    print(f" {tc.function.name} : {tc.function.arguments}")
                    # Get session and call tool
                    # session = self.sessions[tc.function.name] # new
                    session = self.sessions.get(tc.function.name)
                    if not session:
                        print(f"Tool {tc.function.name} not found in available sessions.")
                        break

                    result = await session.call_tool(tc.function.name, json.loads(tc.function.arguments))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result.content
                    })
                    print(f"Tool call result: {result}") 
            if not has_tool_use:
                break

    async def get_resource(self, resource_uri):
        session = self.sessions.get(resource_uri)

        # Fallback for papers URIs - try any papers resource session
        if not session and resource_uri.startswith("papers://"):
            for uri, sess in self.sessions.items():
                if uri.startswith("papers://"):
                    session = sess
                    break
        
        if not session:
            print(f"Resource session for {resource_uri} not found.")
            return None
        
        try:
            result = await session.read_resource(uri = resource_uri)
            if result and result.contents:
                print(f"\nResource: {resource_uri}")
                print("Contents:")
                print(result.contents[0].text)
            else:
                print(f"No contents available")
        except Exception as e:
            print(f"Error reading resource {resource_uri}: {e}")

    async def list_prompts(self):
        """List all available prompts."""
        if not self.available_prompts:
            print("No prompts available.")
            return
        
        print("\nAvailable Prompts:")
        for prompt in self.available_prompts:
            print(f"- {prompt['name']}: {prompt['description']}")
            if prompt['arguments']:
                for arg in prompt['arguments']:
                    arg_name = arg.name if hasattr(arg, 'name') else arg.get("name", "")
                    print(f"     - {arg_name}")

    async def execute_prompt(self, prompt_name, args):
        """Execute a prompt with the given arguments."""
        session = self.sessions.get(prompt_name)
        if not session:
            print(f"Prompt {prompt_name} not found in available sessions.")
            return
        
        try:
            result = await session.get_prompt(prompt_name, arguments=args)
            if result and result.messages:
                prompt_content = result.messages[0].content

                # Extract text from content (handles different formats)
                if isinstance(prompt_content, str):
                    text = prompt_content
                elif hasattr(prompt_content, 'text'):
                    text = prompt_content.text
                else:
                    text = " ".join(item.text if hasattr(item, 'text') else str(item) 
                                    for item in prompt_content)
                print(f"\nExecution prompt '{prompt_name}' {text}...")
                await self.process_query(text)

        except Exception as e:
            print(f"Error executing prompt {prompt_name}: {e}")

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queies or 'quit' to exit.")        
        print("Use @folders to see available topics")
        print("Use @<topic> to ssearch papers in that topic")
        print("Use /prompts to list available prompts")
        print("Use /prompt <name> <arg1=value1> to execute a prompt")

        while True:
            try:
                query = input("\nQuery: ").strip()
        
                if query.lower() == 'quit':
                    break

                # check for @resource syntax first
                if query.startswith("@"):
                    # Remove @ sign
                    topic = query[1:].strip()
                    if topic == "folders":
                        resource_uri = "papers://folders"
                    else:
                        resource_uri = f"papers://{topic}"
                    await self.get_resource(resource_uri)
                    continue

                # check for /command syntax
                if query.startswith("/"):
                    parts = query.split()
                    command = parts[0].lower()

                    if command == "/prompts":
                        await self.list_prompts()
                    elif command == "/prompt":
                        if len(parts) < 2:
                            print("Usage: /prompt <name> [arg1=value1 ...]")
                            continue
                        prompt_name = parts[1]
                        args = {}
                        
                        # parase arguments
                        for arg in parts[2:]:
                            if '=' in arg:
                                key, value = arg.split('=', 1)
                                args[key.strip()] = value.strip()
                            else:
                                print(f"Invalid argument format: {arg}")
                                continue
                        await self.execute_prompt(prompt_name, args)
                    else:
                        print(f"Unknown command: {command}")
                    continue

                await self.process_query(query)
                print("\n")
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def connect_to_server(self, server_name: str, server_config: dict)-> None:
        # Create server parameters for stdio connection
        # server_params = StdioServerParameters(
        #     command="uv",  # Executable
        #     args=["run", "research_server.py"],  # Optional command line arguments
        #     env=None,  # Optional environment variables
        # )
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            ) # new
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            ) # new
            await session.initialize()
            # self.sessions.append(session)

            # List available tools for this session
            try:
                response = await session.list_tools()
                tools = response.tools
                print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])

                # List available tools
                for tool in tools: # new
                    # self.tool_to_session[tool.name] = session
                    self.sessions[tool.name] = session
                    self.available_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    })        
                self.openai_tools = [convert_mcp_tool(tool) for tool in self.available_tools] 

                # List available prompts
                prompts_response = await session.list_prompts()
                if prompts_response and prompts_response.prompts:
                    for prompt in prompts_response.prompts:
                        self.sessions[prompt.name] = session
                        self.available_prompts.append({
                            "name": prompt.name,
                            "description": prompt.description,
                            "arguments": prompt.arguments
                        })
                # List available resource
                resources_response = await session.list_resources()
                if resources_response and resources_response.resources:
                    for resource in resources_response.resources:
                        resource_uri = str(resource.uri)
                        self.sessions[resource_uri] = session
                

            except Exception as e:
                print(f"Error: {e}")

        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")
    
    async def connect_to_servers(self): # new
        """Connect to all configured MCP servers."""
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise

    async def cleanup(self): # new
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()

async def main():
    chatbot = MCP_ChatBot()
    # await chatbot.connect_to_server_and_run()
    try:
        await chatbot.connect_to_servers() # new!
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup() # new!


if __name__ == "__main__":
    asyncio.run(main())

