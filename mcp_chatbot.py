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
        self.sessions: List[ClientSession] = [] # new
        self.exit_stack = AsyncExitStack() # new
        
        self.llm  = AzureOpenAI(
            api_key = os.getenv("DIAL_API_KEY"), 
            api_version = "2024-02-01",
            azure_endpoint = "https://ai-proxy.lab.epam.com"
            ) 
        self.model_name = "gpt-4o-mini-2024-07-18"
        # self.available_tools: List[dict] = []
        self.available_tools: List[ToolDefinition] = [] # new
        self.tool_to_session: Dict[str, ClientSession] = {} # new

    async def process_query(self, query):
        messages = [{'role':'user', 'content':query}]
        process_query = True
        while process_query:
            # assistant_content = []
            resp = self.llm.chat.completions.create(
                model = self.model_name,
                tools = self.openai_tools,  # convert to OpenAI tool format
                tool_choice = "auto",  # let the LLM decide which tool to use
                messages = messages,
                max_tokens = 2024,
                temperature = 0.0
            )
            msg = resp.choices[0].message
            messages.append(msg)
            # print(f"msg: {msg.model_dump_json(indent=2)}")

            if not msg.tool_calls:
                # If no tool calls, just print the response text
                print(msg.content)
                process_query = False
                continue
            for tc in msg.tool_calls:
                print(f" {tc.function.name} : {tc.function.arguments}")
                # result = await self.session.call_tool(tc.function.name, json.loads(tc.function.arguments))
                session = self.tool_to_session[tc.function.name] # new
                result = await session.call_tool(tc.function.name, json.loads(tc.function.arguments))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.content
                })
                print(f"Tool call result: {result}") 
                
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
        
                if query.lower() == 'quit':
                    break
                    
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
            self.sessions.append(session)

            # List available tools for this session
            response = await session.list_tools()
            tools = response.tools
            print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])

            for tool in tools: # new
                self.tool_to_session[tool.name] = session
                self.available_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })        
            self.openai_tools = [convert_mcp_tool(tool) for tool in self.available_tools] 
        
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

