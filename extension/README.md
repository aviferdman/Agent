# Internal AI Agent (Local Test)

Minimal VS Code extension to forward `@agent` chat messages to a local FastAPI service at `http://127.0.0.1:8000/chat`.

## Dev Setup

```bash
npm install
npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=dist/extension.js --sourcemap
```

Launch: Press F5 in VS Code (Extension Development Host).

In Copilot Chat: type `@agent your question`.

Command Palette: `Internal Agent: Ask (Selection or Prompt)` to send selected text.

## Settings
- `internalAgent.endpoint` (string) – chat endpoint
- `internalAgent.maxPromptChars` (number) – local prompt limit

## Later Enhancements
- Auth header
- SSE / JSON chunk protocol
- Tool/task indicators

