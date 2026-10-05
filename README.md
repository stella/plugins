<p align="center">
  <img src=".github/assets/banner.png" alt="stella plugins" width="100%" />
</p>

# stella plugins

Plugins that connect AI coding agents to [stella](https://stll.app), the
open-source legal workspace. The `stella` plugin adds stella's MCP server and a
`connect-stella` skill that signs in and verifies the connection.

## Claude Code

```sh
claude plugin marketplace add stella/plugins
claude plugin install stella@stella
```

## Codex

```sh
codex plugin marketplace add stella/plugins
codex plugin add stella@stella
```

Then ask your agent to connect to stella. It starts the sign-in, shows you a
link to open in your browser, and confirms the connection once the sign-in
succeeds.

Self-hosted instances and the other MCP addresses (`/mcp-anonymized`,
`/mcp-law`) are covered in the
[connection guide](https://stll.app/docs/get-started/connect-ai-assistant/).

## License

Apache-2.0
