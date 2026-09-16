![Cover](https://cdn.hashnode.com/res/hashnode/image/upload/v1756804249854/4110fab2-f27a-41a3-be5c-7a406ffaab46.png)

There are many resources on this topic, but I couldn't find a clear overview of MCP servers or a standard method for building one, except for Redditors suggesting to “ask Claude or Windsurf.” I've combined a DevOps perspective, tutorials, and curated lists into this guide, which I hope will clarify the MCP concept and help you implement standard-based MCP servers.

In this article I go through:

1.  MCP Architecture & design:  
    Understand **MCP client-server communication architecture** and **how to design an MPC** (opiniated)
    
2.  Build & deploy TypeScript MCP servers for [Cloudflare Workers](https://github.com/cloudflare/ai/tree/main/demos)
    
3.  Build Python MCP servers with [fastmcp](https://github.com/jlowin/fastmcp)
    
4.  Turn existing agents into MCP servers with [auto-mcp](https://auto-mcp.com/)
    

# MCP architecture & design

As I mentioned in my previous article [How to use MCP servers](https://gloweet.com/blogs/mcp-servers-introduction-guide), the **Model Context Protocol (MCP)** standard sets up a framework for how a tool and an AI agent can interact. An MCP gives the agent a list of tools it can use, and the agent just needs to pick the right one to complete the task.

For example, you want to manage GitHub PRs and get your GitHub repos from your agent.  
→ The GitHub MCP Server wraps GitHubs' features and make them accessible to your IDE’s agent

## **How to design my MCP? Not like APIs.**

Agents that use MCPs are generalists. If you base your MCP on an API specs, the available tools will be atomic/granular and must be used in a specific order to work well together.

Let’s take the image of a **customer support ticket API** that provides the following endpoints:

*   `createTicket`
    
*   `addMessage`
    
*   `assignAgent`
    
*   `updateStatus`
    
*   `closeTicket`
    

For an LLM, this is like being given every screw, wire, and circuit board instead of a "resolve customer issue" button. It has to infer which order matters (should a ticket be assigned before a response is added?), what status transitions are valid (open → pending → resolved vs. open → closed), and when to stop.

In MCP design, you’d expose higher-level tools like:

*   `resolveTicket`: handles assignment, messaging, and closing
    
*   `escalateTicket`: handles routing and notifying supervisors
    
*   `summarizeConversation`: provides a condensed view for the agent
    

This shifts the burden away from orchestration logic toward **goal completion**. The LLM doesn’t need to simulate being a support engineer juggling APIs. It just chooses the right tool for the job.

However, an API is an extremly good starting point.

## **How do AI and MCP servers communicate?**

There are three core components in an MPC communication:

*   **Host**: The environment where AI tasks are executed, such as IDEs or AI-powered applications like Claude Desktop.
    
*   **Client**: Acts as an intermediary, managing communication between the host and MCP servers. It handles requests, retrieves server capabilities, and processes notifications.
    
*   **Server**: Provides access to external tools, resources, and prompts. It enables AI models to perform operations like data retrieval, API invocation, and workflow optimization.
    

[![MCP workflow](https://cdn.prod.website-files.com/6321a7346f73799791d41a39/67f760d5fa47b33e78f7a1c0_AD_4nXdUTtXUiCEJDVbmTV71N740IUTqi7qd06Ih1xOCnhTYa11lh58btM-KqLDuyuabJQUkzpjqY3DpJHzcpSMiy09fL8lOoxJk1RdM-6zVuejkC6cdwFMmFctDExuckhRVnk8Evpw2.avif)](https://arxiv.org/pdf/2503.23278)

### **MCP process**

Your IDE acts as an `MCP Host` by hosting MCP clients that query MCP servers.  
At initialization, your IDE’s agent queries MCP servers to discover available tools with the messages **ListToolsRequest/ListToolsResult**. Then it calls these tools using **CallToolRequest/CallToolResult** messages.

### **MCP Hosting**

MCP servers may be deployed in local as well as remote environments.  
**Local** MCP servers follow a privacy-first approach and uses local Standard IO transport protocol.

Remote MCP servers offer:

*   **Consistency**: One server version, same behavior for all clients.
    
*   **Team integration**: Add a tool once, instantly available to everyone.
    
*   **Centralization**: No duplicated setup on developer machines.
    
*   **Scalability**: Heavy workloads handled by remote infra, many clients supported.
    
*   **Isolation**: Server exposes only the resources and files it’s meant to.
    

If your MCP uses sensitive local files or requires very low latency, I suggest to make the MCP server local only.

You’ll see below how to host a MCP server using Cloudflare workers.  
In addition to that I’ll give more insights about MCP hosting in a dedicated article  
→ [stay tuned](https://antoninmarxer.hashnode.dev/newsletter)

### **MCP Protocols**

MCP is transport agnostic, which means the client and server can communicate over different protocols depending on your setup.

However, it always follow an RPC-style pattern (Remote Procedure Call): Think of it as “on demand” requests. It allows clients to invoke methods on remote servers as if they were local function calls. This hides the complexities of model hosting, resource management, and request handling

In your MCP server, responses should follow JSON-RPC 2.0 specification.

[![Architecture diagram showing the communication flow from Tools to Client applications](https://miro.medium.com/v2/resize:fit:1400/format:webp/1*17aHWZr0VGP7EGwbzB2QXw.png align="center")](https://medium.com/@sanathshetty444/exposing-mcp-servers-as-apis-building-bridges-between-ai-models-and-applications-104ff3803178)

Let’s review available protocols:

*   **Standard IO (Stdio)**: common **local** bidirectional communication, simple, typical for CLI processes or containers.
    
*   **HTTP with two subtypes:**
    
    1.  **SSE (Server-Sent Events)**: unidirectional server-to-client communication. Real-time **push** via HTTP, text-only since it uses the `text/event-stream` MIME type.
        
        It opens a long-lived session in `/sse` endpoint.
        
        It receives messages form the `/messages` endpoint, and replies through the `SSE` session.
        
        This is now deprecated: It doesn’t suit ephemeral servers (serverless) as this protocol keeps the SSE session open.  
        Use Streamable HTTP instead through the `/mcp` endpoint ⬇️
        
    2.  **Streamable HTTP**: unidirectional or bidirectional HTTP communication with chunked transfer encoding. It uses a single endpoint: `/mcp`
        
*   **WebSocket**: A dedicated protocol (`ws://` or `wss://`) enabling interactive bidirectional communication, listening for changes and getting notified when something comes in.
    

**Issues due to remote connections**

To push data to clients as needed, SSE & WebSocket connections are long-lived. If you host your MCP server remotely, the connection may remain open for a long time.

Common issues when using HTTP & WebSocket are:

*   Random connection drop halfway through a response
    
*   Most browsers have a limit of 6 concurrent SSE (EventSource) connections per domain, which may be a problem when musing multiple times.
    
*   Hard to know where the problem is: MCP client, server or network layer.
    

As a solution, you should:

*   Use `/mcp` Streamable HTTP protocol.
    
*   Use snake\_case or dash formats for MCP tool names to maintain client compatibility and avoid subtle request failures.
    
*   Validate incoming and outgoing payloads against strict JSON schemas to catch errors before processing.
    

### **Return common** [**JSON-RPC 2.0**](https://www.jsonrpc.org/specification) **error codes**

As MPC is built on JSON-RPC 2.0 for its error handling, on error you receive such objects:

```json
{
  jsonrpc: "2.0",
  id: string | number | null,
  error: {
    code: number,       
    message: string,
    data?: unknown
  }
}
```

The `code` is the error category type identifier.  
The `message` is a human-readable explanation.

**Standard** **reserved error codes** (from `-32768` to `-32000`) are mostly handled by the MCP framework:

| **Code** | **Name** | **What it Really Means** | **Fix** |
| --- | --- | --- | --- |
| `-32700` | Parse Error | Your JSON syntax is broken | Use standard JSON serialization |
| `-32600` | Invalid Request | Your message structure violates the protocol | Valid JSON format but there may be a missing key, e.g `jsonrpc` |
| `-32601` | Method Not Found | The operation you requested doesn't exist |  |
| `-32602` | Invalid Params | Your parameters failed validation |  |
| `-32603` | Internal Error | The server encountered an implementation issue |  |
| `-32000` to `-32099` | Server Error | Implementation-specific errors |  |

**Custom application error codes** are the interresting part. They help giving meaningful feedback on error:

| Code | Description | Common Cause | How to Handle |
| --- | --- | --- | --- |
| \-32000 | Authentication Error | Missing or invalid token | Return WWW-Authenticate header |
| \-32001 | Invalid Session | Session ID not found | Client should reinitialize |
| \-32002 | Resource Not Found | A file doesn’t exist, or a client called an unknown method | Check method name |
| \-32003 | Invalid Parameters | Missing or invalid parameters | Validate parameters |
| \-32004 | Internal Error | Server-side exception | Log details for debugging |
| \-32005 | Parse Error | Invalid JSON | Validate request format |

### **How to throw MCP error codes in TypeScript?**

Typescript MCP servers depend on the [@modelcontextprotocol](https://github.com/modelcontextprotocol/typescript-sdk/tree/main) TypeScript SDK, which exposes the `ErrorCode` enum:

```typescript
import { McpError, ErrorCode } from "@modelcontextprotocol/sdk";
```

On error, throw an explicit `MCPError` instance:

```typescript
throw new McpError(
  ErrorCode.InvalidRequest,
  "Missing required parameter",
  { parameter: "name" }
);
```

### **How to throw MCP error codes with FastMCP?**

The way FastMCP gives explicit feedback to the end user via error handling is by converting Python exceptions into MCP protocol error responses that get sent back to the client.

This means that if your tool encouters an error, you cna raise a standard Python exception: `ValueError`, `TypeError`, `FileNotFoundError` or custom exceptions. **FastMCP's internal middleware catches it automatically.**  
**However**, exposing error details is risky. You cna disable it using the `mask_error_details=True` parameter when instanciating `FastMCP`:

```python
mcp = FastMCP(name="SecureServer", mask_error_details=True)
```

You can also send a FastMCP `ToolError` which is sent directly back to the client. It allows to **explicitly control what error information** is sent to clients:

```python
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

@mcp.tool
def divide(a: float, b: float) -> float:
    """Divide a by b."""

    if b == 0:
        # Error messages from ToolError are always sent to clients,
        # regardless of mask_error_details setting
        raise ToolError("Division by zero is not allowed.")
    
    # If mask_error_details=True, this message would be masked
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Both arguments must be numbers.")
        
    return a / b
```

For full control over what information is exposed to the client, prefer raising `ToolError` exceptions.

### **Observability and Troubleshooting**

*   Implement detailed structured logging with unique correlation IDs to trace requests, responses, and errors.
    
*   Expose health check endpoints and set up monitoring and alerting on connection errors and abnormal metrics.
    

We’ll see how to do that in the tutorial section.

### **MCP security risks & best practices**

When you’re running an MCP server locally, it’s the same as running any other software, **with unlimited access to all your files**. You should use Docker to run MCP servers securely. I’ll soon make a guide about it.  
For remote MCP servers, you must also limit accessible resources, especially when self-hosting.

Remote frameworks integrate security constraints based on these risks:

*   **Prompt injection & tool poisoning**: Malicious prompts may call harmful MCP tools.  
    → Some IDEs allow to blacklist certain MCP tools, or ask to confirm the action
    
*   **Code injection**: An MCP server running commands (e.g: filesystem) may run `rm -rf /` instead of listing files, because a string wasn’t validated.  
    → Sanitize strings
    
*   **Credentials leakage**: The token you pass to your MCP server may be leaked, exposed in a debug log.  
    → Use MCP frameworks that support OAuth 2.1, JWT tokens, HMAC signatures.
    
    → Log authentication/authorization/activity logs for traceability.
    
*   **Over-permissioning**: Follow the principle of least privilege: no resource should ever have more access that it needs to perform is intended tasks  
    → Use Role-Based-Access-Control (RBAC)  
    → Limit accessible resources
    
*   **Ensure tool integrity**: Legitimate MCP servers can be spoofed. Without integrity validation, your data can be sent to malicious substitute MCP servers.  
    → Notify users whenever tools are updated or replaced.  
    → Require certificate pinning for all TLS connections.  
    → Block endpoints that do not pass TLS or metadata verification.
    

In the next parts of this article, we’ll see which frameworks comply with those requirements.

### **MCP use cases**

Now that the basics are clear, we can review MCP servers main use cases:

1.  **Wrap an existing API**: Expose third-party services (GitHub, Jira, Slack, AWS).
    
    We’ll go through each step using [Tadata](https://tadata.com), which generates MCP servers from OpenAPI specification files.
    
2.  **Framework adapter**: Bridge orchestration or agent frameworks (CrewAI, LangGraph, LlamaIndex, OpenAI).  
    We’ll use [auto-mcp](https://auto-mcp.com/) for that usage.
    
3.  **Connect to a remote host from a local-only MCP client**:  
    Use [mcp-remote](https://github.com/geelen/mcp-remote), a CLI tool that enables existing MCP clients, like Cursor or Windsurf, to connect to remote servers.
    
    > As I mentioned before, Streamable HTTP should be preferred over the SSE protocol. That’s exactly what mcp-remote does:  
    > When running `mcp-remote https://my-mcp.example.com` mcp-remote tries the `/mcp` endpoint first. If it fails wih a 404, it fallbacks to the `/sse` endpoint.
    
4.  **Custom logic**: Implement domain-specific workflows or business rules from scratch. Let’s not reinvent the wheel, but rather use frameworks which have built-in OAuth 2.1 support:
    
    *   Official TypeScript SDK for MCP: [typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk)
        
    *   TypeScript FastMCP framework: punkpeye/[fastmcp](https://github.com/punkpeye/fastmcp)
        
    *   Pythonic way to build MCP servers & clients: [jlowin/fastmcp](https://github.com/jlowin/fastmcp)
        
    
    For an easy-setup, if you use TypeScript, I recommend using cloudflare mcp servers templates, see [cloudflare/ai/demos](https://github.com/cloudflare/ai/tree/main/demos). We'll get to that later in the section below.
    
    *   [remote-mcp-google-oauth](https://github.com/cloudflare/ai/tree/main/demos/remote-mcp-google-oauth): Model Context Protocol (MCP) Server + Google OAuth
        
    *   [remote-mcp-auth0](https://github.com/cloudflare/ai/tree/main/demos/remote-mcp-auth0): Model Context Protocol (MCP) Server + Auth0
        
5.  **Call MCP tools in Python**:
    
    Simply import `MCPClient` from `python_a2a` package and start calling your tools.
    
    > Note: This is MCP communication, not A2A communication as there’s not agent collaboration/negociation here.
    
    ```python
    from python_a2a.mcp import MCPClient
    
    # Create a client connected to the MCP server URL
    client = MCPClient("http://localhost:8000")
    
    # List available tools
    tools = client.list_tools()
    print(f"Available tools: {[tool.name for tool in tools]}")
    
    # Call a specific tool, e.g., add two numbers
    result = client.call_tool("calculator.add", {"a": 5, "b": 3})
    print(f"Result: {result}")  # Output: 8
    ```
    
    `MCPClient` prioritizes Streamable HTTP transport effectively.
    
6.  **Call MCP tools in TypeScript**
    
    Use `mcp-client` to use any MCP servers in your JS app:
    
    ```typescript
    import { MCPConnectionManager } from 'mcp-client';
    const manager = new MCPConnectionManager();
    await manager.initialize('./mcp-config.json');
    const client = manager.getClient('memory');
    const tools = await client?.listTools();
    const result = await client?.callTool('toolName', { /* params */ });
    await manager.cleanup();
    ```
    
7.  **Proxy/gateway**: Aggregate multiple services or enforce access policies. The major tools MCP gateways are:
    

*   [Unla MCP Gateway](https://github.com/AmoyLab/Unla): A lightweight gateway service that instantly transforms existing MCP Servers and APIs into MCP servers with zero code changes. Features Docker deployment and management UI, requiring no infrastructure modifications.
    
*   [Microsoft MCP gateway](https://github.com/microsoft/mcp-gateway/tree/main): reverse proxy and management layer for MCP servers, enabling scalable, session-aware routing and lifecycle management of MCP servers in Kubernetes environments.
    

You know have a broader view on the MCP ecosystem. Now, let’s create your first MPC server ⬇️

# Build & deploy MCP servers for Cloudflare Workers

I suggest using the Cloudflare MCP servers templates, which support OAuth and Streamable-HTTP. They come both in Typescript and Python version, although the Python version cannot be deployed using the Free plan as it goes beyond the size limit. We’ll see another pythonic way in the next secion to share a MCP server.

Streamable-HTTP has been recently added in [Cloudflare templates](https://github.com/cloudflare/ai/tree/main/demos) through the `/mcp` endpoint:

![](https://cdn.hashnode.com/res/hashnode/image/upload/v1756814384051/a51232e7-4183-4225-9a92-fce9539e0e09.png align="center")

`/sse` endpoint is kept as fallback, but if it’s being used by using `mcp-outline —sse-first <your_mcp_server_url>` then your costs may rise high. Hence I suggest to just remove it, which will throw a 404 automatically.

**Start to build your TypeScript-based MCP-Server using Cloudflare Wokers**

Let’s say you want your organization members to connect to your custom MCP. If using Google Workspace, you need Google OAuth, if using Auth0, you need Auth0 Oauth, etc.

Pick the template that suits your use-case, then run:

```bash
npm create cloudflare@latest -- my-mcp-server-google-auth --template=cloudflare/ai/demos/remote-mcp-google-oauth cd my-mcp-server-google-auth npx wrangler@latest deploy
```

The main difference between google and github templates are actually located in the `src/index.ts` file, where the `defaultHandler` is set to the `GithubHandler`:

```typescript
import GitHubHandler from "./github-handler";

export default new OAuthProvider({
    apiHandlers: {
         // Deprecated SSE protocol - use /mcp instead
        "/sse": MyMCP.serveSSE("/sse"),
        "/mcp": MyMCP.serve("mcp") // Streamable-HTTP protocol
    },
    defaultHandler: GitHubHandler,
    authorizeEndpoint: "/authorize",
    tokenEndpoint: "/token",
    clientRegistrationEndpoint: "/register"
});
```

You need to create a Google OAuth app to use Google as an IdP (identity provider): one for local development, and one for production.

1.  Go to [Google Cloud Console](https://console.cloud.google.com)
    
2.  Navigate to **APIs & Services → OAuth consent screen** → configure name, email, scopes.
    
3.  Go to **Credentials → Create Credentials → OAuth Client ID**.
    
    *   Choose **Web Application**.
        
    *   Add **Authorized redirect URIs**:
        
        *   Dev: [`http://localhost:3000/auth/callback`](http://localhost:3000/auth/callback)
            
        *   Prod: [`https://yourdomain.com/auth/callback`](https://yourdomain.com/auth/callback)
            
4.  Set the secrets locally:
    
    ```typescript
    // .dev.vars
    GOOGLE_CLIENT_ID="your-client-id"
    GOOGLE_CLIENT_SECRET="your-client-secret"
    ```
    
5.  Run & test locally
    
    ```bash
    npm start
    ```
    
    This serves your MCP server on `http://localhost:8788/sse`
    
6.  Debug the MCP server (local & remote)
    
    Use [MCP Inspector](https://github.com/modelcontextprotocol/inspector), an interactive MC client that lists discovered tools and invoke them from a web browser.
    
    ```bash
    npx @modelcontextprotocol/inspector@latest
    ```
    
    Go to [http://localhost:5173](http://localhost:5173). In the inspector, enter the URL of your MCP server, [`http://localhost:8788/sse`](http://localhost:8788/sse), and click **Connect**.  
    You should be redirected to a GitHub authorization page. Once authorized, you're redirected to the inspector and can list & invoke tools.
    
7.  Run remotely
    
    If you don’t have a Cloudflare account, you must create one.  
    Then install wrangler and login.  
    Now, configure secrets & deploy your MCP server to Cloudflare Workers (serverless):
    
    ```bash
    # Configure global secrets
    wrangler secret put -e production HCAPTCHA_SITE_KEY
    wrangler secret put -e production GITHUB_CLIENT_SECRET
    # Deploy
    wrangler deploy -e production
    ```
    
8.  Configure your IDE to use the remote MCP Server
    
    ```bash
    // claude_desktop_config.json
    {
      "mcpServers": {
        "my_cloudflare_worker_mcp": {
          "command": "npx",
          "args": ["mcp-remote","https://worker-name.account-name.workers.dev"]
        }
      }
    }
    ```
    

# Build Python MCP servers with [fastmcp](https://github.com/jlowin/fastmcp)

For a more feature-rich experience, you can use [jlowin/fastmcp](https://github.com/jlowin/fastmcp), which offers additional features and a more pythonic approac[h](https://github.com/jlowin/fastmcp).

Start by adding FastMCP as a dependency:

```bash
uv add fastmcp
# or use uv pip install fastmcp
```

Create a FastMCP server by instantiating the `FastMCP` class. Create a `server.py` file:

```python
from fastmcp import FastMCP, Tool # FastMCP 2.0 syntax

mcp = FastMCP("DocumentMCP")
```

To add a tool, write a function and decorate it with `@mcp.tool` to register it with the MCP server.  
Let’s implement a tool that reads a document based on a `doc_id` param. We validate the parameter using `pydantic`:

```python
from fastmcp import FastMCP, Tool # FastMCP 2.0 syntax
from pydantic import BaseModel, Field

class DocumentQuery(BaseModel):
    doc_id: str = Field(description="ID of the document to retrieve")

mcp = FastMCP("DocumentMCP")

@mcp.tool
def read_document(query: DocumentQuery) -> str:
    """
    Read the contents of a document and return it as a string.
    """
    # Implementation here
    return f"Content of document {query.doc_id}"

if __name__ == "__main__":
    mcp.run() # Uses STDIO transport by default
```

### Use Streamable HTTP

Your MCP servers is local only by default as it uses Standard IO (stidio) protocol. Replace that with Streamable HTTP:

```python
mcp.run(transport="http", host="127.0.0.1", port=8000)
```

Run your application with `FastMCP` CLI:

```bash
fastmcp run server.py
```

Your server is now accessible at [`http://localhost:8000/mcp/`](http://localhost:8000/mcp/).

### Use run\_async() inside async functions

`mcp.run()` is actually a synchronous wrapper around our async logic.  
If your application is already running in an async context, use `run_async()`:

```bash
from fastmcp import FastMCP
import asyncio

mcp = FastMCP(name="MyServer")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

async def main():
    # Use run_async() in async contexts
    await mcp.run_async(transport="http", port=8000)

if __name__ == "__main__":
    asyncio.run(main())
```

### Add unit tests

To test your MCP server, create a `pytest` unit test file in `tests/test_server.py` that:

*   Instanciates a `Client` from our MCP. Clients are asynchronous, so we need to use [`asyncio.run`](http://asyncio.run) to run the client.
    
*   To use the client we must enter a client context with `async with client:`
    

Run unit tests by running `pytest`.

```python
import pytest
import asyncio
from fastmcp import Client
from server import mcp

@pytest.mark.asyncio
async def test_read_document():
    client = Client(mcp)
    async with client:
        result = await client.call_tool("read_document", {"doc_id": "123"})
        assert "Content of document 123" in result
```

### Add explicit error feedback

Handle errors by returning JSON-RCP error codes:

```python
@mcp.tool
def update_document(
    doc_id: str = Field(description="ID of the document to update"),
    content: str = Field(description="New content for the document")
):
    try:
        # Implementation here
        return {"success": True, "message": f"Document {doc_id} updated successfully"}
    except KeyError:
        # Return a structured error response
        return {
            "error": {
                "code": -32003,
                "message": f"Document with ID {doc_id} not found",
                "data": {"requested_id": doc_id}
            }
        }
```

### **Package your Python MCP Server**

To make your MCP server easily shareable, you can package it as a Python package:

1.  Create an `__init__.py` module file:
    

```python
                  # src/my_custom_mcp/__init__.py
                  from .server import mcp
```

*   Define your package metadata in `pyproject.toml`
    
*   Build and publish:
    

```python
                  pip install build
                  python -m build
                  # Use Twine, a utility to publish to PyPI
                  pip install twine
                  # Publish to PyPI (this will ask for a PyPI API token)
                  twine upload dist/*
```

*   Users can then integrate your package with their IDE:
    
    ```python
    // claude_desktop_config.json
    {
      "mcpServers": {
        "my_custom_mcp": {
          "command": "uvx",
          "args": [        
            "server"
          ]
        }
      }
    }
    ```
    

### Add Health Checks

To monitor your MCP server, you can add health endpoints through FastMCP custom routes:

```python
from starlette.responses import JSONResponse

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "mcp-server"})
```

This serves the health endpoint `http://localhost:8000/health` and can be used to restart your server in case of failure.

### Add auhentication

If your MCP server is available remotely, you **must** add authentication. This can be done very easily with FastMCP, which supports OAuth, Bearer tokens and JWT.

To implement OAuth 2.1 we’re gonna use the `RemoteAuthProvider` to authenticate to Auth0. This will:

*   Add well known endpoints `/{ISSUER}/.well-known/jwks.json`
    
*   Use proper CORS configuration based on OAuth provider
    

> Note: I see that tadata made the [fastapi\_mcp](https://fastapi-mcp.tadata.com/getting-started/welcome) library to implement those changes.  
> Please keep relying on fastmcp library only, following the framework standards.

A minimal implementation looks like this:

```python
from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from pydantic import AnyHttpUrl
import os

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "your-tenant.us.auth0.com")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "https://your-api-identifier")
RESOURCE_SERVER_URL = os.getenv("RESOURCE_SERVER_URL", "https://your-domain.example.com/mcp")

# Configure JWT verification
token_verifier = JWTVerifier(
    jwks_uri=f"https://{AUTH0_DOMAIN}/.well-known/jwks.json",
    issuer=f"https://{AUTH0_DOMAIN}/",
    audience=AUTH0_AUDIENCE
)

# Wire OAuth to MCP
auth = RemoteAuthProvider(
    token_verifier=token_verifier,
    authorization_servers=[AnyHttpUrl(f"https://{AUTH0_DOMAIN}/")],
    resource_server_url=RESOURCE_SERVER_URL
)

mcp = FastMCP(name="Protected MCP Server", auth=auth)

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
```

#### Configure an Auth0 application

1.  **Create Application** in the Auth0 dashboard.
    
2.  **Register an API** (your MCP server) with identifier matching `AUTH0_AUDIENCE`.
    
3.  **Enable OIDC Dynamic Client Registration**.
    
4.  **Set Default Audience** to your API identifier.
    

This ensures any MCP client can obtain tokens and authenticate correctly.

From Auth0 you can also enable Google Oauth.

*   In the Auth0 Dashboard, go to Authentication → Social → Google OAuth.
    
*   Under Applications, turn on the toggle for your application.
    
*   Save the changes.
    

### Deploy your FastMCP server

Once Auth0 is configured:

*   Deploy the server to your hosting provider (e.g. Render, [Fly.io](http://Fly.io), or your own infrastructure).  
    For example, go to Render, create a new web app and use its GitHub integration by connecting your repo.
    
*   Set the environment variables (`AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `RESOURCE_SERVER_URL`).
    

Your OAuth-protected MCP server is now live. Any MCP client that connects will be redirected through the OAuth flow, retrieve an access token, and then be able to call tools and resources securely.

## Turn existing agents into MCP servers with [auto-mcp](https://auto-mcp.com/)

If you've built an app using an agent framework (CrewAI, OpenAI, etc.), you can use Naphta [auto-mcp](https://auto-mcp.com/) to create an adapter for your existing agent classes.

> **Note:** If you’re using CrewAI, they offer direct MCP integration with the `MCPServerAdapter` from the `crewai-tools`, see this article from [Plaban Nayak](https://medium.com/the-ai-forum/building-an-ai-powered-study-assistant-with-mcp-crewai-and-streamlit-2a3d51d53b38).

Let automcp generate a `run_mcp.py` file to configure your agent:

```bash
uv add naptha-automcp
automcp init -f <framework>
# expected agent flag: crewai, langgraph, llamaindex, openai, pydantic, mcp_agent
```

Update the generated `run_mcp.py` file to use your agent class:

```python
# Replace these imports with your actual agent classes
from your_module import YourCrewClass

# Define the input schema
class InputSchema(BaseModel):
    parameter1: str
    parameter2: str

# Set your agent details
name = "<YOUR_AGENT_NAME>"
description = "<YOUR_AGENT_DESCRIPTION>"

# For CrewAI projects
mcp_crewai = create_crewai_adapter(
    orchestrator_instance=YourCrewClass().crew(),
    name=name,
    description=description,
    input_schema=InputSchema,
)
```

Install dependencies and run your MCP server:

```python
automcp serve -t sse
```

Your MCP server is now up and provides one single MCP tool: Your agent.

## Conclusion

We went through the Model Context Protocol (MPC) fundamentals and ecosystem.  
It shifts the API-centric approach to an agent-interactive approach, in a goal-oriented paradigm.  
This approach is less granular, but more goal-oriented, atomic tools being replaced with *“recipe”* meta-tools.

MCP servers can be written in any language, it’s just an implementation of a protocol. Just look for frameworks to handle the heavy-lifting, e.g: Cloudflare Workers templates for TypeScript, and FastMCP for Python.

Security and observability aren’t a nice-to-have, frameworks help you implement authentication, but you have to explicitly handle errors, and add traceability if your MCP is remote.

**A few words about MCPs evolution**

New tools appear, making curated MCP resources longer and longer.

*   Curated list of MCP tools, platforms & services: [awesome-mcp-enterprise](https://github.com/bh-rat/awesome-mcp-enterprise?tab=readme-ov-file#mcp-directories--marketplaces) GitHub repo
    
*   Curated list of MCP servers: see [awesome-mcp-servers](https://github.com/wong2/awesome-mcp-servers?tab=readme-ov-file#official-servers) GitHub repo
    
*   Security-centered [MCP-Checklists](https://github.com/MCP-Manager/MCP-Checklists/tree/main?tab=readme-ov-file)
    

Best practices emerge and frameworks evolve, improving the overall quality of MCP servers and enforcing standards. Most MCP plugins are coded without frameworks, using tech stacks that are only “Claude” or “Windsurf” based, putting whole communities at risk with, see the article “[We Uregntly Need Privilege Management in MCP: A Measurement of API Usage in MCP Ecosystems](https://arxiv.org/pdf/2507.06250)”.

**I’d love to hear your go-to way for building MCP servers, and if they’re remote, how you share them and let your team use them?**

## Sources

*   Tori Seidenstein. APIs make bad MCPs. Start there anyway. tadata.com \[online\]. Available on: [https://tadata.com/blog/apis-make-bad-mcps-start-there-anyway](https://tadata.com/blog/apis-make-bad-mcps-start-there-anyway)
    
*   Olha Diachuk. The DevOps view on MCP architecture. dysnic.com \[online\]. Available on:  
    [https://dysnix.com/blog/mcp-architecture](https://dysnix.com/blog/mcp-architecture)
    
*   Araving Putrevu. How to host your MCP Server. Dev Shorts \[online\]. Exposing MCP Servers as APIs: Building Bridges Between AI Models and Applications. Available on: [https://www.devshorts.in/p/how-to-host-your-mcp-server](https://www.devshorts.in/p/how-to-host-your-mcp-server)
    
*   Sanath Shetty. Exposing MCP Servers as APIs: Building Bridges Between AI Models and Applications. Medium \[online\]. Available on: [https://medium.com/@sanathshetty444/exposing-mcp-servers-as-apis-building-bridges-between-ai-models-and-applications-104ff3803178](https://medium.com/@sanathshetty444/exposing-mcp-servers-as-apis-building-bridges-between-ai-models-and-applications-104ff3803178)
    
*   Maria Paktiti. The complete guide to MCP security: How to secure MCP servers & clients. workos.com \[online\]. Available on: [https://workos.com/blog/mcp-security-risks-best-practices](https://workos.com/blog/mcp-security-risks-best-practices)
    
*   Aravind Putrevu. How to implement OAuth for MCP Server. Dev Shorts \[online\]. Available on: [https://www.devshorts.in/p/how-to-implement-oauth-for-mcp-server](https://www.devshorts.in/p/how-to-implement-oauth-for-mcp-server)
    
*   FastMCP. Expose functions as executable capabilities for your MCP client. gofastmcp.com \[online\]. Available on: [https://gofastmcp.com/servers/tools](https://gofastmcp.com/servers/tools)