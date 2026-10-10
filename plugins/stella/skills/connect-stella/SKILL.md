---
name: connect-stella
description: Guide browser sign-in and verify the stella connection when the user asks to connect, set up, sign in to, or fix stella.
---

# Connect stella

Run setup commands only when the user requests connection or troubleshooting.
If tools are missing during another task, explain that a connection is needed
and let the user choose whether to set it up. Use the installed client's
supported sign-in flow; do not install or launch another application.
Never ask for passwords, tokens, authorization codes, or full callback URLs.
The user signs in and approves permissions in their browser.

stella's MCP server signs people in with OAuth in their browser. The client
receives the sign-in result on a local port that stays open only while the
sign-in command runs. Keep that command alive until it reports success; a call
that ends, times out, or runs inside a sandbox closes the port, and the browser
then shows that the site can't be reached.

The server address is `https://api.stll.app/mcp` unless the user gives another
one (self-hosted instances serve `/mcp` on their own API host).

## 1. Find the server

This plugin registers the stella server. Find the exact name your client uses
for it:

- Claude Code: `claude mcp list`. This plugin's server is
  `plugin:stella:stella`.
- Codex: `codex mcp list`. This plugin's server is `stella`.

If stella is not listed, add it:

- Claude Code: `claude mcp add --transport http stella <server address>`
- Codex: `codex mcp add stella --url <server address>` (this starts the sign-in
  itself; run it as described in step 2).

If the status already shows stella as connected or authenticated, skip to
step 4.

## 2. Start the sign-in in the background

Start the sign-in as a long-running background process, not as a normal shell
call:

- Codex: `codex mcp login <name> --no-browser`. Run it outside the sandbox;
  request permission only if the environment requires it and the user has
  not already authorized the sign-in.
- Claude Code: `claude mcp login <name> --no-browser`. It needs a terminal, so
  run it in a pseudo-terminal:
  - macOS: `script -q /dev/null claude mcp login <name> --no-browser`
  - Linux: `script -qc "claude mcp login <name> --no-browser" /dev/null`

## 3. Hand the sign-in to the user

1. Show the user the sign-in URL the command prints, and ask them to open it.
2. In the browser, they sign in to stella, check the organization and
   permissions, and approve.
3. The browser then shows a plain confirmation page from the client itself.
   That page is expected.
4. If their browser runs on another machine and the callback cannot reach the
   client, explain the problem and use the client's supported remote sign-in
   flow or repeat sign-in with the browser on the same machine. Do not ask
   them to paste the callback URL into the conversation.
5. Keep the command running until it reports success.

## 4. Verify before you say "connected"

Check the sign-in without a model call:

- Claude Code: `claude mcp get <name>` must show it as connected.
- Codex: `codex mcp list` must show `OAuth` in the Auth column.

Until it does, tell the user that stella is added but not connected. Quote the
output, and offer to repeat step 2. Never call an added server connected.

## 5. Make one read-only call

stella's tools appear in a new session. If the user's connection request
includes verification, make one read-only call, such as a public case-law
search. Otherwise, offer this check. Do not read private matter data for a
setup check or change records or documents:

- If it fails, report the error exactly.
- If it succeeds, tell the user what they can now do through stella: search
  case law and legislation, and work with the matters and documents they can
  access.

## Options

- Personal data masked: use the address ending in `/mcp-anonymized`.
- Public case law and legislation only: use `/mcp-law`.
- Full guide: https://stll.app/docs/get-started/connect-ai-assistant/
