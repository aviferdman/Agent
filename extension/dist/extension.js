"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/extension.ts
var extension_exports = {};
__export(extension_exports, {
  activate: () => activate,
  deactivate: () => deactivate
});
module.exports = __toCommonJS(extension_exports);
var vscode = __toESM(require("vscode"));
var http = __toESM(require("http"));
var https = __toESM(require("https"));
function readSetting(key, defaultValue) {
  const cfg = vscode.workspace.getConfiguration();
  const v = cfg.get(key);
  return v === void 0 ? defaultValue : v;
}
async function sendStreamingRequest(endpoint, payload, onChunk, token) {
  const url = new URL(endpoint);
  const data = JSON.stringify(payload);
  const lib = url.protocol === "https:" ? https : http;
  return await new Promise((resolve) => {
    const req = lib.request({
      method: "POST",
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(data)
      }
    }, (res) => {
      res.on("data", (d) => {
        if (token.isCancellationRequested) {
          req.destroy();
          return;
        }
        onChunk(d.toString());
      });
      res.on("end", () => resolve());
    });
    req.on("error", (e) => {
      onChunk(`
[error] ${e.message}`);
      resolve();
    });
    req.write(data);
    req.end();
  });
}
function activate(context) {
  const output = vscode.window.createOutputChannel("InternalAgent");
  const participant = vscode.chat.createChatParticipant("querypilot", async (request, context2, stream, token) => {
    const endpoint = readSetting("internalAgent.endpoint", "http://127.0.0.1:8000/chat");
    const maxChars = readSetting("internalAgent.maxPromptChars", 8e3);
    const prompt = (request.prompt || "").trim();
    if (!prompt) {
      stream.markdown("*(empty prompt)*");
      return {};
    }
    if (prompt.length > maxChars) {
      stream.markdown(`Prompt too long (${prompt.length} chars > ${maxChars})`);
      return {};
    }
    stream.markdown("_Contacting internal agent..._\n");
    await sendStreamingRequest(endpoint, { message: prompt }, (chunk) => {
      try {
        stream.markdown(chunk);
      } catch {
      }
    }, token);
    return {};
  });
  participant.iconPath = new vscode.ThemeIcon("robot");
  const cmd = vscode.commands.registerCommand("internalAgent.askSelection", async () => {
    const editor = vscode.window.activeTextEditor;
    const sel = editor ? editor.document.getText(editor.selection) : "";
    const base = sel || "";
    const question = await vscode.window.showInputBox({ prompt: "Ask Internal Agent", value: base });
    if (!question)
      return;
    const chatApi = vscode.chat;
    if (chatApi?.requestChatAccess) {
      const access = await chatApi.requestChatAccess("github.copilot");
      await access.sendMessage(`@querypilot ${question}`);
    } else {
      vscode.window.showInformationMessage("Chat access API not available in this VS Code version. Use @querypilot manually.");
    }
  });
  context.subscriptions.push(cmd);
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  status.text = "IntAgent";
  status.tooltip = "Ask Internal Agent (selection aware)";
  status.command = "internalAgent.askSelection";
  status.show();
  context.subscriptions.push(status);
  output.appendLine("Internal Agent extension activated");
}
function deactivate() {
}
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  activate,
  deactivate
});
//# sourceMappingURL=extension.js.map
