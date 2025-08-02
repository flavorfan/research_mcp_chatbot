

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

### 3. Test Multi MCP Server (Reference MCP Server)

input
```md
**Fetch the content of this website: https://modelcontextprotocol.io/docs/learn/architecture ** and save the content in the file "mcp_summary.md". **Create a visual diagram that summarizes the content of "mcp_summary.md" and save it in a text file**
```


### 4. test: Add prompts, resources and change the chatbot loop

@folders

@computer

/prompts

/prompt generate_search_prompt topic=math

## convert to sse 
```shell
# start the MCP server
uv run research_server.py

# launch the inspector
npx @modelcontextprotocol/inspector

# convir
# Transport type: SSE
# Proxy Address: http://localhost:6277
# Proxy session token: xxx
```

## Ready for Deployment
```shell

git init

echo ".venv" >> .gitignore

# check denpendencies
uv pip compile pyproject.toml

uv pip compile pyproject.toml > requirements.txt

# specify the Python version
echo "python-3.12.10" > runtime.txt
```

### setup render
https://render.com/
github account as account


```text
add github repo to web deployment
https://dashboard.render.com/web/new

start command
    python research_server.py

```
check the url 
https://research-mcp-chatbot.onrender.com/sse

