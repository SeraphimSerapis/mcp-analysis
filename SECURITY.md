# Security Policy

## Trust Model

`mcp-analysis` reads your existing MCP configuration files and interacts with the
servers defined in them. It is important to understand what this means:

### What the tool does

- **Reads config files** from known paths (`~/.gemini/settings.json`, etc.)
- **Spawns local MCP servers** listed in your config via `stdio` transport
- **Connects to remote MCP servers** listed in your config via HTTP
- **Resolves environment variables** referenced in your config (for auth headers)
- **Calls `tools/list`** on each server — this is a read-only MCP method
- **Outputs results** to stdout (never to a remote service)

### What the tool does NOT do

- ❌ Does **not** send telemetry or phone home
- ❌ Does **not** modify any config files
- ❌ Does **not** call any MCP tools (only lists them)
- ❌ Does **not** store or log credentials
- ❌ Does **not** create any files on disk

### Implied trust

When you run `mcp-analysis`, you are trusting the same MCP servers you already
configured in your CLI tools. If a malicious server is in your config, this tool
will connect to it — just as your CLI would.

The tool resolves environment variables (e.g., `$API_KEY`) to authenticate with
remote servers. These resolved values are sent only to the URLs specified in
**your own config files** and are never logged or persisted.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue.
2. **Email** [timmesserschmidt@gmail.com](mailto:timmesserschmidt@gmail.com)
   with a description of the vulnerability.
3. You should receive a response within 48 hours.
4. A fix will be released and credited (unless you prefer anonymity).

Thank you for helping keep this project safe.
