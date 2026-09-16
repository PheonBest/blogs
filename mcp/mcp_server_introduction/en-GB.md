![Cover](https://cdn.hashnode.com/res/hashnode/image/upload/v1756715162805/d07c3f42-5f82-49e4-8a36-b11224206424.png)

In this article, I explain how MCPs (Model Context Protocols) work and how to integrate them into your IDEs to connect external tools to your agent.  
Let’s transform your IDE becomes a true all-in-one tool.

---

In 2023, Anthropic published the **Model Context Protocol (MCP)**, an open standard often described as a *“universal USB-C for AI”*. This protocol enables AI systems to connect to external tools, APIs, and data sources, in a bidirectional way.

My take on MCPs:

> MCPs can use any third-party service, including those from IDE agent interfaces. Does this mean services will be developed specifically for this interface? No, it doesn't replace APIs or GUIs. However, it is a significant advantage for service interoperability and greatly enhances the developer experience in IDEs that support MCPs.

## **Any tool can be used by an AI**

The MCP standard defines a framework for possible interactions between the tool and the AI. An MCP provides the AI with a catalogue of available `tools`, from which it only needs to select the right one to solve the given task.

*Example:* you’re a developer with around twenty tasks listed in Jira. You ask your IDE agent:

> Fetch the Jira tasks for the current project, define today’s priorities for me. Create an action plan for each priority, and save it in [tasks.md](http://tasks.md).

You edit the generated action plan, then write:

> Execute task X from the action plan in @[tasks.md](http://tasks.md). Update the status of completed tasks in @[tasks.md](http://tasks.md) and summarise the changes made.

We’ll mainly focus on MCP server usage by LLM agents (chatbots), though any AI system can use them.

**How does a Large Language Model work?** The user provides a prompt in text form, which is then tokenised (split into smaller word units called tokens) before being processed by the model. The model is trained on millions or even billions of examples to predict the best possible response, based on the **context** provided.

## Which MCPs to use?

They exist for almost every use case. I mostly use the following:

| **MCP** | **Usage** |
| --- | --- |
| [filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | Read, create, edit, and search files and directories |
| [sequentialthinking](https://github.com/arben-adm/mcp-sequential-thinking) | Facilitates structured, progressive thinking through defined stages. |
| [memory-bank-mcp](https://github.com/alioshr/memory-bank-mcp) | Centralized memory-bank with multi-project support |
| [github](https://github.com/modelcontextprotocol/servers/tree/main/src/github) | Fetch GitHub issues and manage pull requests. **→ see end of article for integration** |
| [google calendar](https://github.com/nspady/google-calendar-mcp) | List your availability for the current week, for example **→ see end of article for integration** |
| [tavily](https://github.com/tavily-ai/tavily-mcp) | Search factual information on the web. 1000 free searches per month |
| [fetch](https://github.com/tavily-ai/fetche-mcp) | Extract structured data from web APIs |
| [firecrawl](https://www.firecrawl.dev/app) | General-purpose web crawler. Free tier offers up to 500 scrapes **→ see end of article for integration** |
| [playwright](https://github.com/microsoft/playwright-mcp) | Automate tasks in a web browser |
| [shadcn](https://www.shadcn.io/mcp) | Integrates Shadcn library components, reducing hallucinations on props |

I tested [Figma-Context-MCP MCP to convert o](https://github.com/GLips/Figma-Context-MCP)nline mockups into a React application, but the results were not satisfactory.

For those looking to turn [a design into cod](https://github.com/GLips/Figma-Context-MCP)e, an alternative approach exists, though it is not particularly recommended:

1. Capture the mockup.
    
2. Use [an LLM to descri](https://github.com/GLips/Figma-Context-MCP)be the [typography, colo](https://github.com/GLips/Figma-Context-MCP)rs, and spacing based on a 12-column grid (desktop), 8-column grid (tablet), and 4-column grid (mobile).
    
3. Generate the React page al[ong with the asso](https://github.com/GLips/Figma-Context-MCP)ciated design system using Shadcn and Tailwind.
    

## Security risks regarding MCPs usage

When you’re running an MCP server locally, it’s the same as running any other software, **with unlimited access to all your files**.

Instead of running them natively, MCP servers should be containerized and run using Docker with restricted access:

* to the filesystem bu running as a non-root user.
    
* to the memory & CPU, e.g in docker-compose:
    
    ```yaml
    deploy:
      resources:
        limits:
          cpus: '0.001'
          memory: 50M
    ```
    

I’ll soon make a guide about using Docker. For the moment, please check out this guide made with strong regard to MCP security: [MCP-Checklists](https://github.com/MCP-Manager/MCP-Checklists/blob/main/infrastructure/docs/how-to-run-mcp-servers-securely.md)

## **Focus on web MCPs: Fetch vs Firecrawl vs Browserbase vs StageHand vs Playwright**

* **Need to fetch online site content?** → Use [**Firecrawl**](https://www.firecrawl.dev/app). It’s an abstract crawler with rules you can configure. Open-source, cloud-based headless browser you can self-host. It loads sites, executes JavaScript, and retrieves client-side dynamic content, which Fetch cannot do. → No browser automation (no page interaction). → Runs in the cloud and can be **integrated into CI/CD pipelines**.
    
* **Need to automate actions in a cloud browser?** For CI/CD environments, use Browserbase and Stagehand to interact with websites. **Difference?** [Browserbase](https://www.browserbase.com/) is `imperative`: you specify each step. [Stagehand](https://www.stagehand.dev/) is `declarative`: you specify the outcome, it figures out the steps.
    
* **Need to crawl or interact with a local or authenticated site?** Two tools help: [Puppeteer](https://pptr.dev/) and [Playwright](https://playwright.dev/). Both support `headful` and `headless` modes. In headful mode, the browser opens, so you can watch interactions. → Prefer Playwright. It uses the local browser with the current user session, ideal for authenticated sites.
    
    > Playwright sessions can be isolated with the `--isolated` flag. See [Playwright GitHub page](https://github.com/microsoft/playwright-mcp?tab=readme-ov-file#configuration).
    

## **Setting up MCPs on Cursor**

### Connect the Firecrawl MCP server

**Goal**: Crawl anonymous public websites.

1. Go to [https://www.firecrawl.dev/](https://www.firecrawl.dev/)
    
2. Create a Free plan account (up to 500 scrapes).
    
3. Copy the MCP configuration from the dashboard’s API key section, selecting the latest Cursor integration.
    
4. Paste it into Cursor settings &gt; MCP &gt; Add new MCP.
    

### Connect the GitHub MCP server

**Goal**: Access GitHub issues and manage pull requests.

Add this config to your file:

```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "<YOUR_GITHUB_PERSONAL_ACCESS_TOKEN>"
  }
}
```

1. Get a Personal Access Token from [GitHub](https://github.com/?utm_source=chatgpt.com)
    
2. Create a new **fine-grained token** with permissions (all repos or selected ones):
    
    * **Commit statuses**: Read and write
        
    * **Contents**: Read and write
        
    * **Issues**: Read and write
        
    * **Merge queues**: Read and write
        
    * **Metadata**: Read-only
        
    * **Pull requests**: Read and write
        
    * **Secret scanning alerts**: Read-only
        
    * **Events**: Read-only
        

### Connect the Google Calendar MCP server

**Goal**: Easily list your availability.

1. Create a new OAuth client ID and secret in **Google Cloud Console**.
    
2. Go to **APIs & Services** &gt; **Credentials** &gt; **Create OAuth ID**.
    
3. Select **Desktop app**.
    
4. Download credentials, save as **credentials.json** at the root of **google-calendar-mcp**.
    
5. In **Data access**, add permissions manually: [`https://www.googleapis.com/auth/calendar.events`](https://www.googleapis.com/auth/calendar.events)
    

```json
"google-calendar": {
  "command": "node",
  "args": ["<absolute path to /google-calendar-mcp/build/index.js"]
},
```

## Recap

**MCPs** are a standard that deliver strong interoperability between AI and external services, to:

* Enhance development environments.
    
* Enrich workflows by connecting external tools.
    

Installation is straightforward, and your agent becomes an intelligent hub.

**Do you also feel MCPs save you time? If so, which MCP servers do you find most relevant?**