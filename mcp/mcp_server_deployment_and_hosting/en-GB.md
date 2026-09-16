![Cover](https://cdn.hashnode.com/res/hashnode/image/upload/v1756973827859/a7f446ef-1469-4c75-bc1a-039c507c6bfa.png)

You've built your MCP server and want to deploy it remotely or publish it as a package? This article covers your options from a DevOps viewpoint.

If you don't know what MCP servers are, see my previous articles:

*   [Tips on how to use MCP servers](https://antoninmarxer.hashnode.dev/mcp-servers-explained-your-introductory-guide)
    
*   [Standard methodology and best practices to build your own MCP servers](https://antoninmarxer.hashnode.dev/create-your-own-mcp-servers)
    

> In short, the **Model Context Protocol (MCP)** is an open standard developed by Anthropic, the creators of Claude LLM. It allows AI agents to use external tools to:
> 
> 1.  Get additional context, such as from an external API
>     
> 2.  Not only generate text but also interact with the external world, making actions possible
>     
> 
> MCP connects an AI model to N external services.
> 
> You can also connect M models to N external services, which is for example the case when using GPT-4 for text generation, and DALL·E or Stable Diffusion for image generation.
> 
> In that case, MCP solves this MxN integration problem by reducing the complexity to M+N, where M AI models connecting to N external tools.
> 
> That’s amazing, isn’t it? Well depends if you successfully host your MCP servers or if they remain in the unused shadows.

We’ll go through the following deployment approaches:

*   **Local hosting**: Clone MCP servers on your machine and reference their entrypoint in your IDE’s MCP configuration file.
    
*   **Remote hosting**: Deploy your MCP server to cloud platforms as serverless or long-lived apps.  
    We’ll go through serverless limitations for that use case.  
    This makes your server accessible from anywhere with a public URL → perfect for team collaboration.
    
*   **Containerization & Kubernetes**: For scalability purposes, you can host your MCP remotely on a Kubernetes cluster. We’ll see how to package your MCP server as a Docker container and deploy it.
    
*   **Packaging as libraries**: Publish your MCP server as a Python or npm package.  
    This is the easiest method if you want a privacy-first approach while still making it easy for others to install and use your tools.
    

# Deployment Options

## 1\. Local Hosting

You can reference your Python/JS MCP server entrypoint in your IDE's MCP configuration file.  
Here is an exemple Claude Desktop configuration file:

```bash
// claude_desktop_config.json
{
  "mcpServers": {
    // For a Python MCP server, run with 'uv' or 'poetry'
    "MyPythonMCP": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/server/directory",
        "run",
        "server.py"
      ]
    },
    // For a JavaScript MCP server, run with 'node'
    "MyJavaScriptMCP": {
      "command": "node",
      "args": [
        "/path/to/your/server/index.js"
      ]
    }
  }
}
```

**I recommend containerizing your MCP server** so that **others can run it securely with limited access to the filesystem, CPU, and memory.** **People should not run your Python/JS MCP server without caution**; add safeguards by user Docker. We’ll see how to do that in the steps below.

## 2\. Remote Hosting

A remote MCP can be deployed as any other web service. Two transport protocols are usually used: **Server-Sent Events (SSE)** and **Streamable HTTP**. SSE is legacy and must be replaced by Streamable HTTP.

To set up SSE, two endpoints are served.

*   `/sse`: The client initi
    
*   lizes the connection by making a `GET` request to it. The server keeps the connection open, sending responses using SSE.
    
*   `/messages`: The client sends messages through `POST` requests. The server processes the messages and replies through the SSE connection.
    

This means the connection is kept open (long-lived connections) and cannot be used for ephemeral environments.

However, Streamable HTTP uses short-lived sessions only. It’s served through one unique `/mcp` endpoint, which is perfect to deploy it to serverless environments.

### **2.a. How to use Streamable HTTP?**

For FastMCP, use: [`mcp.run`](http://mcp.run)`(transport="http", host="127.0.0.1", port=8000)`

For [Cloudflare workers templates](https://github.com/cloudflare/ai/tree/main/demos), specify `/mcp` api handler:

```typescript
import GitHubHandler from "./github-handler";

export default new OAuthProvider({
    apiHandlers: {
         // Deprecated SSE protocol - use /mcp instead
        // "/sse": MyMCP.serveSSE("/sse"),
        "/mcp": MyMCP.serve("mcp") // Streamable-HTTP protocol
    },
    defaultHandler: GitHubHandler,
    authorizeEndpoint: "/authorize",
    tokenEndpoint: "/token",
    clientRegistrationEndpoint: "/register"
});
```

### 2.b. Common Remote Hosting Options

You can deploy your MCP using various platforms:

1.  **Render**: Simple deployment with GitHub integration
    
2.  **Vercel**: Great for JavaScript/TypeScript MCPs
    
3.  **Netlify**: Excellent for frontend-focused MCPs
    
4.  **Cloudflare Workers**: Good for JavaScript MCPs without Node dependencies. Python MCPs are also supported, but not on the Free plan due to file size limits.
    

When using these cloud platforms, you host your Python or JavaScript app directly, not the containerized version. The platforms already manage resource limitations for you, no worries.

Before deploying your server, make sure to add logging. It records user activities with unique correlation IDs. **Tracing will be your best friend for debugging**.

### 2.c. Add Tracing to Python MCP servers

You can use [mcp-trace](https://github.com/ContexaAI/mcp-trace) from ContexaAI with FastMCP.  
Log to any of the supported backend: console, file, Contexa, PostgreSQL, Supabase or multiple of them at the same time:

```python
import os

class MultiAdapter:
    def __init__(self, *adapters):
        self.adapters = adapters

    def export(self, trace_data: dict):
        for adapter in self.adapters:
            adapter.export(trace_data)

contexa_adapter = ContexaTraceAdapter(
    api_key=os.getenv("CONTEXA_API_KEY"),
    server_id=os.getenv("CONTEXA_SERVER_ID"),
)

file_adapter = FileTraceAdapter("trace.log")

psql_adapter = PostgresTraceAdapter(
    dsn=os.getenv("POSTGRES_DSN")  # example: postgresql://user:pass@host:port/dbname
)

supabase_adapter = SupabasePostgresTraceAdapter(os.getenv("SUPABASE_URL"))

console_adapter = ConsoleTraceAdapter()

trace_middleware = TraceMiddleware(
    adapter=MultiAdapter(
        contexa_adapter,
        file_adapter,
        psql_adapter,
        supabase_adapter,
        console_adapter,
    )
)
mcp.add_middleware(trace_middleware)
```

If you use PostgreSQL Adapter, create a table to store traces:

```sql
CREATE TABLE mcp_traces (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id TEXT NOT NULL,
    trace_data JSONB NOT NULL
);
```

I strongly advise to configure tracing to **exclude sensitive data** to ensure privacy and avoid leaking others’ data/credentials:

```typescript
trace_middleware = TraceMiddleware(
    adapter=trace_adapter,
    log_fields={
        "entity_name": True,
        "entity_response": True,
        "entity_params": False,  # disables tool arguments
        "client_id": False,      # disables client_id
        # ...add more as needed
    }
)
mcp.add_middleware(trace_middleware)
```

### 2.d. Add tracing to a TypeScript MCP Servers

You can use [mcp-trace-js](https://github.com/ContexaAI/mcp-trace-js) from ContexaAI.

Log to any of the supported backend: console, file, Contexa, PostgreSQL, Supabase or multiple of them at the same time:

```typescript
import {
  ContexaTraceAdapter,
  FileAdapter,
  PostgresTraceAdapter,
  SupabaseTraceAdapter,
  MultiAdapter,
  TraceMiddleware,
} from "mcp-trace-js";

let traceMiddleware;

if (process.env.NODE_ENV === "production") {
  const contexaAdapter = new ContexaTraceAdapter({
    apiKey: process.env.CONTEXA_API_KEY,
    serverId: process.env.CONTEXA_SERVER_ID
    // Optional: apiUrl, bufferSize, flushInterval, maxRetries, retryDelay
  });

  const fileAdapter = new FileAdapter(
    process.env.TRACE_LOG_FILE || "trace.log"
  );

  const psqlAdapter = new PostgresTraceAdapter({
    dsn: process.env.POSTGRES_DSN // e.g. postgresql://user:pass@host:port/dbname
  });

  const supabaseAdapter = new SupabaseTraceAdapter({
    supabaseClient: process.env.SUPABASE_URL // or client object if you init it elsewhere
  });

  const multiAdapter = new MultiAdapter(
    contexaAdapter,
    fileAdapter,
    psqlAdapter,
    supabaseAdapter
  );

  traceMiddleware = new TraceMiddleware({ adapter: multiAdapter });
  app.use("/mcp", traceMiddleware.express());
}
```

Same here, if you use PostgreSQL Adapter, create a table to store traces:

```sql
CREATE TABLE IF NOT EXISTS trace_events (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL,
  type TEXT NOT NULL,
  method TEXT,
  session_id TEXT NOT NULL,
  client_id TEXT,
  duration INTEGER,
  entity_name TEXT,
  arguments JSONB,
  response TEXT,
  error TEXT
);
```

You should aso **exclude sensitive data** here:

```typescript
const traceMiddleware = new TraceMiddleware({
  adapter: traceAdapter,
  logFields: {
    tool_name: true,
    tool_response: true,
    tool_arguments: false, // disables tool arguments
    client_id: false, // disables client_id
    // ...add more as needed
  },
});
```

You can skip tracing for specific requests by adding the `X-Ignore-Traces` header:

```bash
# Skip tracing for this request
curl -H "X-Ignore-Traces: true" http://localhost:8080/mcp
```

### 2.e. Add tracing to Cloudflare Workers MCP Servers

When using Cloudflare Workers, you may pass your MCP handlers to an OAuthProvider. To add tracing, wrap these handlers:

```typescript
import { ConsoleAdapter, TraceMiddleware } from "mcp-trace-js";

const trace = new TraceMiddleware({ adapter: new ConsoleAdapter() });

// Instead of using the middleware, use trace low-level function.
const tracedServe = (path: string) => {
  const handler = MyMCP.serve(path);
  return {
    async fetch(req: Request, env: Env, ctx: ExecutionContext) {
      const span = trace.startSpan({ path });
      try {
        const res = await handler.fetch(req, env, ctx);
        trace.endSpan(span, { status: res.status });
        return res;
      } catch (err) {
        trace.endSpan(span, { error: err });
        throw err;
      }
    }
  };
};

export default new OAuthProvider({
  apiHandlers: {
    "/mcp": tracedServe("/mcp"),
  },
  ...
});
```

### 2.f. Deploying to Render Example

1.  Create a new Web Service on Render using GitHub integration by selecting your code repository.
    
2.  Enter service details:
    
    *   Name: `My-Custom-MCP`
        
    *   Build Command: `npm install && npm run build`
        
    *   Start Command: `npm start`
        

You'll get a public URL like: `https://my-custom-mcp-j3jc.onrender.com`

Configure your IDE to use the remote MCP:

```bash
// claude_desktop_config.json
{
  "mcpServers": {
    "my_custom_mcp": {
      "command": "npx",
      "args": ["mcp-remote","https://my-custom-mcp-j3jc.onrender.com"]
    }
  }
}
```

## 3\. Python MCP Server Containerization

If you self-host your remote MCP, containerize it to:

*   limit its filesystem access
    
*   limit its CPU and memory usage
    

You would also want to containerize your MCP server for scalability.

The basic idea of a Dockerfile is that it’s a list of operations:

1.  Start from a base image
    
    ```dockerfile
    FROM python:3.11-slim
    ```
    
    You start from an initial operations list, which are called base images.
    
    Here we use the slim Python base image `python:3.11-slim` for its light size.
    
2.  Create a non-root user named `mcpuser`
    
    ```dockerfile
    RUN groupadd -g 1000 mcpuser && \
        useradd -u 1000 -g mcpuser -s /bin/bash -m mcpuser
    ```
    
    To prevent the container from accessing all files, we run it as a non-root user.  
    The created user is identified by its UID & GID, here 1000 and 1000 respectively.
    
3.  Install Python dependencies
    
    *   Copy the `requirements.txt` file
        
    *   Install dependencies: `RUN pip install --no-cache-dir -r requirements.txt`
        
4.  Copy your app’s source code
    
    Copy the rest of the files and let the created user modify them:  
    `COPY --chown=mcpuser:mcpuser . .`
    
5.  Run your MCP server entrypoint: `CMD ["python", "server.py"]`
    
6.  Leverage caching by using multi-stage dockerfiles.  
    The first stage installs dependencies in `/install`.  
    Then the second stage copy installed dependencies.  
    → Until `requirements.txt` change, the first stage will not run again.
    

Let’s put all that together into one `Dockerfile` file, next to your `server.py` file:

```dockerfile
# Start with a Python base image
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with UID & GID 1000
RUN groupadd -g 1000 mcpuser && \
    useradd -u 1000 -g mcpuser -s /bin/bash -m mcpuser

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies into /install
RUN python -m venv /install && \
    /install/bin/pip install --no-cache-dir -r requirements.txt

# Final image
FROM python:3.11-slim


WORKDIR /app

# Create a non-root user
RUN groupadd -g 1000 mcpuser && \
    useradd -u 1000 -g mcpuser -s /bin/bash -m mcpuser

# Copy installed dependencies from builder
COPY --from=builder /install /install
ENV PATH="/install/bin:$PATH"

# Copy application code with ownership
COPY --chown=mcpuser:mcpuser . .

# If you have a config file, uncomment the below line
# Mark mounted files as read-only
# VOLUME ["/app/config"]

# Environment variables
ENV PORT=8080
ENV LOG_LEVEL=INFO

# Switch to non-root user
USER mcpuser

# Expose port
EXPOSE 8000

# Run the server
CMD ["python", "server.py"]
```

6.  Let’s build and run your containerized MCP server:
    

```dockerfile
docker build -t my-mcp-server . && docker run -it mcp-server
```

7.  You can use MCP inspector to debug your docker container:
    

```bash
npx @modelcontextprotocol/inspector serve docker run -i my-mcp-server
```

8.  Publish your docker image to an image registry (here Docker Hub)
    

```bash
# Tag and Publish the Docker image to Docker Hub
# Replace 'your_dockerhub_username' and 'your_repository_name' accordingly.
docker tag my-mcp-server your_dockerhub_username/your_repository_name:latest

# Log in to Docker Hub (you'll be prompted for your username and password)
docker login
# Push the Docker image to Docker Hub
docker push your_dockerhub_username/your_repository_name:latest
```

9.  Add health endpoints & self-healing to your container
    
    Docker marks a container as `running` as long as its main process is active. But an active process does not guarantee the application is healthy. A service might be:
    
    *   **Unresponsive** because of an internal error
        
    *   **Waiting** for a dependency such as a database
        
    *   **Still starting up** and not yet ready to handle traffic
        
    
    Let’s solve this with docker-compose, which has a health check built-in mechanism.
    
    > If you’re not familiar with docker-compose, it allows to define and manage multi-container Docker applications using a single YAML file.
    

Create a `docker-compose.yml` file to run your MCP server:

```yaml
services:
  mcp-server:
    image: <your_docker_hub_username>/<repo>:latest
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    restart: unless-stopped

  autoheal:
    restart: always
    image: willfarrell/autoheal
    environment:
      - AUTOHEAL_CONTAINER_LABEL=all
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

The `autoheal` container will ensure unealthy containers get restarted using [willfarrell/autoheal](https://hub.docker.com/r/willfarrell/autoheal/).

Use the following commands to run/build/push:

```yaml
docker-compose up
# Run the image in detached mode:
docker-compose up -d
# Force to rebuild the image:
docker-compose up --build
# Build-only:
docker-compose build
# Push to Docker hub
docker-compose push
```

## 4\. TypeScript MCP Server Containerization

The steps are essentialy the same, except for:

*   the base iamge: use a `node` image from [Docker Hub](https://hub.docker.com/_/node/). Usually, check your current node version using `node —version` and pick the one matching on Docker Hub.
    
*   The dependencies installation: We use `npm ci` to install them from the package files.
    
*   FastMCP listens on port 8000 while @modelcontextprotocol typescript SDK listens on port 3000 by default.
    

```dockerfile
      # Start with node base image
      FROM node:22.12-alpine AS builder
      
      WORKDIR /app
      
      # Create non-root user
      RUN addgroup -g 1000 mcpuser && \
          adduser -D -u 1000 -G mcpuser mcpuser
      
      # Copy package files and leverage npm caching
      COPY package*.json ./
      RUN --mount=type=cache,target=/root/.npm \
          npm ci
      
      # Copy application code
      COPY --chown=mcpuser:mcpuser . .
      
      # Build the app
      RUN npm run build
      
      # === Stage 2: Release image ===
      FROM node:22-alpine AS release
      
      WORKDIR /app
      
      # Copy built files and package info from builder
      COPY --from=builder /app/dist /app/dist
      COPY --from=builder /app/package*.json /app/
      
      # Set environment
      ENV NODE_ENV=production
      
      # Install only production dependencies
      RUN --mount=type=cache,target=/root/.npm \
          npm ci --omit=dev --ignore-scripts
      
      # Create non-root user
      RUN addgroup -g 1000 mcpuser && \
          adduser -D -u 1000 -G mcpuser mcpuser
      USER mcpuser
      
      # Mark mounted files as read-only
      VOLUME ["/app/config"]
      
      # Expose port
      EXPOSE 3000
      
      # Run the server
      ENTRYPOINT ["node", "dist/index.js"]
```

You can also use a docker-compose file for auto-heal:

```yaml
  services:
    mcp-server:
      image: <your_docker_hub_username>/<repo>:latest
      build:
        context: .
        dockerfile: Dockerfile
      ports:
        - "8000:3000"
      environment:
        - LOG_LEVEL=INFO
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 5s
      restart: unless-stopped
  
    autoheal:
      restart: always
      image: willfarrell/autoheal
      environment:
        - AUTOHEAL_CONTAINER_LABEL=all
      volumes:
        - /var/run/docker.sock:/var/run/docker.sock
```

## 5\. Kubernetes Deployment

To ensure scalability, you may want to run your containers on a Kubernetes clusters.  
We’ll create the following Kubernetes manifests:

*   **A deployment**, which describes your application’s lifecycles, how many pods run…  
    A pod is a group of one or more containers.
    
*   **A service**, which allows to access a set of Pods from a stable network endpoint. Even if the pods get removed, the service endpoint remains.
    
*   **An ingress**, in order to route traffic from outside to the internal service.
    

In the below manifests, replace `<MCP Server PORT>` by `3000` for typescript MCP servers, and by `8000` for Python FastMCP servers.

1.  Create a Kubernetes deployment manifest
    
    Create a `deployment.yaml` file which creates 2 replicas of your `mcp-server` Docker image. Note the pods label.
    
    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: mcp-server
      namespace: mcp-server
    spec:
      replicas: 2
      selector:
        matchLabels:
          app: mcp-server
      template:
        metadata:
          labels:
            app: mcp-server
        spec:
          containers:
          - name: mcp-server
            image: your-registry/mcp-server:latest
            ports:
            - containerPort: <MCP Server PORT>
            envFrom:
            - secretRef:
                name: mcp-server-secrets
            volumeMounts:
            - name: config-volume
              mountPath: /app/config
              readOnly: true
          volumes:
          - name: config-volume
            configMap:
              name: mcp-server-config
    ```
    
2.  Monitor your pods
    
    If you use Prometheus operator, you can monitor your pods using PodMonitor or Service Monitor.  
    Implement a custom route `/metrics`, then create a Pod Monitor manifest in `pod-monitor.yaml`:
    
    ```yaml
    apiVersion: monitoring.coreos.com/v1
    kind: PodMonitor
    metadata:
      name: mcp-server-pod-monitor
      namespace: mcp-server
    spec:
      selector:
        matchLabels:
          app: mcp-server
      podMetricsEndpoints:
      - port: metrics
        path: /metrics
    ```
    
3.  Expose your MCP server with a Kubernetes service  
    Create a `service.yaml` file. Define a ClusterIP servie that target our pods label, i.e. `mcp-server`
    
    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: mcp-server
      namespace: mcp-server
    spec:
      selector:
        app: mcp-server
      ports:
      - port: 80
        targetPort: <MCP Server PORT>
      type: ClusterIP
    ```
    
4.  Make your service accessible from outside
    
    Create a `ingress.yaml` file. Define an ingress that uses your Kubernetes Cluster’s ingressClassName.
    
    If you’re using nginx ingress, it will look like this:
    
    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: mcp-server-ingress
      namespace: mcp-server
      annotations:
        nginx.ingress.kubernetes.io/rewrite-target: /
        nginx.ingress.kubernetes.io/ssl-redirect: "true"
        cert-manager.io/cluster-issuer: "{{ cluster_issuer }}"
    spec:
      rules:
        - host: "mcp-server.{{ main_domain }}"
          http:
            paths:
              - backend:
                  service:
                    name: mcp-server
                    port:
                      number: "<MCP Server PORT>"
                path: /
                pathType: Prefix
    ```
    
    I **strongly recommend** to use an OAuth2 proxy setup to add an auth wall and prevent your MCP server from being spammed. That is if you’ve not already implemented OAuth2 in your MCP server.
    
    → If you already have an auth & authorization server, just change your ingress annotations like so:
    
    ```yaml
    nginx.ingress.kubernetes.io/auth-method: 'GET'
    nginx.ingress.kubernetes.io/auth-url: "{{ auth_url }}"
    nginx.ingress.kubernetes.io/auth-signin: "{{ auth_signin }}"
    nginx.ingress.kubernetes.io/auth-response-headers: 'Remote-User,Remote-Name,Remote-Groups,Remote-Email'
    ```
    
    Reference your identity provider service. If using Authelia:
    
    *   auth\_url is [`http://authelia.authelia.svc.cluster.local/api/authz/auth-request`](http://authelia.authelia.svc.cluster.local/api/authz/auth-request)
        
    *   auth\_signin is [`https://<PUBLIC_AUTHELIA_ENDPOINT>?rm=$request_method`](https://auth.antoninmarxer.com?rm=$request_method)
        

#### Managing API Keys Securely

If credentials are needed, store them using Kubernetes secrets in `secret.yml`:

```bash
apiVersion: v1
kind: Secret
metadata:
  name: mcp-server-secrets
type: Opaque
data:
  API_KEY: <base64-encoded-api-key>
  DATABASE_URL: <base64-encoded-db-url>
```

**Apply manifests**

To create your Kubernetes resources effectively:

1.  Make sure you can access to your Kubernetes cluster using kubectl.
    
2.  All your resources will be in an isolated namespace, which you can create like this:
    
    ```bash
    kubectl create namespace mcp-server
    ```
    
3.  Apply all manifest files:
    
    ```bash
    kubectl apply -f ./ -n mcp-server
    # or apply them one by one, e.g:
    # kubectl apply -f deployment.yaml -n mcp-server
    ```
    
    Your MCP server is now online on the `mcp-server.{{ main_domain }}` endpoint. Configure your IDE to use it:
    
    ```json
    // claude_desktop_config.json
    {
      "mcpServers": {
        "my_custom_mcp": {
          "command": "npx",
          "args": ["mcp-remote","https://mcp-server.<YOUR_DOMAIN>"]
        }
      }
    }
    ```
    
    Your team can now connect to your MCP Server remotely!
    

## 6\. Packaging as Libraries

#### Python Package

1.  Create an `__init__.py` module file:
    

```bash
# src/my_custom_mcp/__init__.py
from .server import mcp
```

2.  Define your package metadata in `pyproject.toml`
    
3.  Build and publish:
    

```bash
pip install build
python -m build
pip install twine
twine upload dist/*
```

#### npm Package

1.  Your entrypoint is defined in `index.js` (or `dist/index.js` if using TypeScript)
    
2.  Define package metadata in `package.json`
    
3.  Build & publish:
    

```bash
npm run build
npm login
npm publish
```

## **Conclusion & Recap**

You now have the foundation to deploy MCP servers that are secure, scalable, and production-ready. Here’s a quick recap:

*   **Deployment options:** Local development, containerized services, and Kubernetes orchestration
    
*   **Security best practices:** Protect data and systems on local and remote servers
    
*   **Containerization:** Isolate and manage MCP server resources effectively
    
*   **Monitoring & tracing:** Health endpoints, observability tools, and audit trails
    
*   **AI-agent readiness:** Design MCP tools that can be leveraged by intelligent agents
    

**Next steps in the MCP ecosystem:**

*   Optimize performance for high-throughput servers
    
*   Explore multi-region and multi-tenant deployments
    
*   Implement advanced security measures and access controls
    
*   Set up MCP proxies and gateways for centralized management and team collaboration
    

If you deployed MCP servers infrastructures, how did you manage to do it, and **were your MCP servers effectively adopted by your teams?**

Start deploying, experimenting, and sharing your results today — every improvement helps shape the future of connected AI systems.

## Sources

*   [Araving Putrevu - How to host your MCP Server](https://www.devshorts.in/p/how-to-host-your-mcp-server)
    
*   [Sanath Shetty - Exposing MCP Servers as APIs](https://medium.com/@sanathshetty444/exposing-mcp-servers-as-apis-building-bridges-between-ai-models-and-applications-104ff3803178)
    
*   [fullestop.com - Model Context Protocol (MCP): Connecting AI to Real-World Data](https://www.fullestop.com/blog/model-context-protocol-mcp-bridging-the-gap-between-ai-models-and-real-world-impact)
    
*   [ideausher.com - How MCP Enhances Personalization in AI-powered Apps](https://ideausher.com/blog/mcp-personalization-in-ai-powered-apps/)
    
*   [Tom Vaidyan - Health Checks in Docker Compose: A Practical Guide](https://www.tvaidyan.com/2025/02/13/health-checks-in-docker-compose-a-practical-guide/)
    
*   [Google Cloud - What is Model Context Protocol (MCP)?](https://cloud.google.com/discover/what-is-model-context-protocol)