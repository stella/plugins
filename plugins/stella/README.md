# stella

Connect to [stella](https://stll.app), the open-source legal workspace, through
its remote MCP server. This plugin includes the server configuration and a
`connect-stella` skill that guides sign-in and verifies the connection.

Version 1.1.0 includes listing descriptions, capability labels, starter prompts,
publisher and policy links, and 512 × 512 PNG icons for light and dark themes.
The bundled onboarding skill runs setup only when requested. Icon artwork is
the app favicon from `stella/stella`, `apps/web/public/favicon.svg`; its blue
background keeps the same mark legible on both white and `#212121`.
Increase the semantic version in both manifests and the root plugin entry
for every release.

## Connect

Install the `stella` plugin from the `stella/plugins` marketplace, then ask your
assistant to connect to stella. You need a stella account and access to an
organization. Open the authorization link in your browser, sign in, and review
the requested permissions. The skill checks authentication and can make one
public, read-only tool call when verification is requested. Keep passwords,
tokens, and callback URLs in the client's sign-in flow.

In clients that support the plugin install command:

```text
/plugin install stella --marketplace stella/plugins
```

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
