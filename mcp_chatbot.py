from dotenv import load_dotenv
# from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import List
import os
from openai import AzureOpenAI
import json
import asyncio
import nest_asyncio

nest_asyncio.apply()

load_dotenv()

def convert_mcp_tool(mcp_tool):
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.__name__,
            "description": mcp_tool.__doc__ or "",
            "parameters": getattr(mcp_tool, "parameters", {}) 
        }
    }



class MCP_ChatBot:

    def __init__(self):
        # Initialize session and client objects
        self.session: ClientSession = None
        # self.anthropic = Anthropic()
        self.llm  = AzureOpenAI(
            api_key = os.getenv("DIAL_API_KEY"), 
            api_version = "2024-02-01",
            azure_endpoint = "https://ai-proxy.lab.epam.com"
            ) 
        self.model_name = "gpt-4o-mini-2024-07-18"
        self.available_tools: List[dict] = []

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
                result = await self.session.call_tool(tc.function.name, json.loads(tc.function.arguments))
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
    
    async def connect_to_server_and_run(self):
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="uv",  # Executable
            args=["run", "research_server.py"],  # Optional command line arguments
            env=None,  # Optional environment variables
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                # Initialize the connection
                await session.initialize()
    
                # List available tools
                response = await session.list_tools()
                
                tools = response.tools
                print("\nConnected to server with tools:", [tool.name for tool in tools])
                
                self.available_tools = [{
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                } for tool in response.tools]

                self.openai_tools = [{
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                } for tool in response.tools]
            

                await self.chat_loop()


async def main():
    chatbot = MCP_ChatBot()
    await chatbot.connect_to_server_and_run()

if __name__ == "__main__":
    asyncio.run(main())

