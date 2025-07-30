

## Setup Environment

### 1. Test MCP Server with inspector
- To open the terminal, run the cell below.
- Navigate to the project directory and initiate it with `uv`:
    - `uv init`
-  Create virtual environment and activate it:
    - `uv venv`
    - `source .venv/bin/activate`
- Install dependencies:
    - `uv add mcp arxiv`
- Launch the inspector:
    - `npx @modelcontextprotocol/inspector uv run research_server.py`

### 2. Test MCP Client
- Activate the virtual environment:
    - `source .venv/bin/activate`
- Install the additional dependencies:
    - `uv add anthropic python-dotenv nest_asyncio`
- Run the chatbot:
    - `uv run mcp_chatbot.py`
- To exit the chatbot, type `quit`.

