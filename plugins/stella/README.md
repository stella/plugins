# stella

Connect to [stella](https://stll.app), the open-source legal workspace, through
its remote MCP server. This plugin includes the server configuration and a
`connect-stella` skill that guides sign-in and verifies the connection.

## Connect

Install the `stella` plugin from the `stella/plugins` marketplace, then ask your
assistant to connect to stella. You need a stella account and access to an
organization. Open the authorization link in your browser, sign in, and review
the requested permissions. The skill checks authentication and asks for one
read-only tool call to verify access.

## Commands and connections

The plugin registers an HTTP MCP connection to `https://api.stll.app/mcp`.
The skill uses your installed client's `mcp list`, `mcp get`, `mcp add`, and
`mcp login` commands as applicable. On macOS or Linux it can use `script` to
keep an interactive sign-in terminal open. OAuth sign-in temporarily listens
on a local callback port; your client stores the resulting authorization.
The skill links to the connection guide below for setup details.

MCP calls send the selected tool's arguments to the configured stella server
and return its results to your assistant. These arguments and results can
include legal-source text and the matter, document, or contact data your
account can access. Available tools depend on your permissions and enabled
features; write tools can change records and documents. The plugin bundles
no hooks, package downloads, or local server executable.

For self-hosted instances, use your own server address. The connection guide
also describes the `/mcp-anonymized` and `/mcp-law` endpoints.

## Documentation and privacy

- [Connection guide](https://stll.app/docs/get-started/connect-ai-assistant/)
- [Privacy policy](https://stll.app/privacy/)
- [Source and issue tracker](https://github.com/stella/plugins)

## License

Apache-2.0; see [LICENSE](LICENSE).
