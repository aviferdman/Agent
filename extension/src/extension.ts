import * as vscode from 'vscode';
import * as http from 'http';
import * as https from 'https';

function readSetting<T>(key: string, defaultValue: T): T {
  const cfg = vscode.workspace.getConfiguration();
  const v = cfg.get<T>(key);
  return (v === undefined ? defaultValue : v) as T;
}

async function sendStreamingRequest(endpoint: string, payload: any, onChunk: (t: string)=>void, token: vscode.CancellationToken) {
  const url = new URL(endpoint);
  const data = JSON.stringify(payload);
  const lib = url.protocol === 'https:' ? https : http;

  return await new Promise<void>((resolve) => {
    const req = lib.request({
      method: 'POST',
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    }, (res: http.IncomingMessage) => {
      res.on('data', (d: Buffer) => {
        if (token.isCancellationRequested) { req.destroy(); return; }
        onChunk(d.toString());
      });
      res.on('end', () => resolve());
    });
    req.on('error', (e: Error) => { onChunk(`\n[error] ${e.message}`); resolve(); });
    req.write(data);
    req.end();
  });
}

export function activate(context: vscode.ExtensionContext) {
  const output = vscode.window.createOutputChannel('InternalAgent');

  // Chat participant id: querypilot (invoke via @querypilot)
  const participant = vscode.chat.createChatParticipant('querypilot', async (
    request: vscode.chat.ChatRequest,
    context: vscode.chat.ChatContext,
    stream: vscode.chat.ChatResponseStream,
    token: vscode.CancellationToken
  ): Promise<vscode.chat.ChatResult> => {
    const endpoint = readSetting('internalAgent.endpoint', 'http://127.0.0.1:8000/chat');
    const maxChars = readSetting('internalAgent.maxPromptChars', 8000);
    const prompt = (request.prompt || '').trim();
    
    if (!prompt) {
      stream.markdown('*(empty prompt)*');
      return {};
    }
    
    if (prompt.length > maxChars) {
      stream.markdown(`Prompt too long (${prompt.length} chars > ${maxChars})`);
      return {};
    }
    
    stream.markdown('_Contacting internal agent..._\n');
    
    await sendStreamingRequest(endpoint, { message: prompt }, (chunk: string) => {
      try { 
        stream.markdown(chunk); 
      } catch { 
        /* ignore stream errors */ 
      }
    }, token);
    
    return {};
  });

  // Set the icon for the participant
  participant.iconPath = new vscode.ThemeIcon('robot');

  const cmd = vscode.commands.registerCommand('internalAgent.askSelection', async () => {
    const editor = vscode.window.activeTextEditor;
    const sel = editor ? editor.document.getText(editor.selection) : '';
    const base = sel || '';
    const question = await vscode.window.showInputBox({ prompt: 'Ask Internal Agent', value: base });
    if (!question) return;
    const chatApi: any = (vscode as any).chat;
    if (chatApi?.requestChatAccess) {
      const access = await chatApi.requestChatAccess('github.copilot');
      await access.sendMessage(`@querypilot ${question}`);
    } else {
      vscode.window.showInformationMessage('Chat access API not available in this VS Code version. Use @querypilot manually.');
    }
  });
  context.subscriptions.push(cmd);

  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  status.text = 'IntAgent';
  status.tooltip = 'Ask Internal Agent (selection aware)';
  status.command = 'internalAgent.askSelection';
  status.show();
  context.subscriptions.push(status);

  output.appendLine('Internal Agent extension activated');
}

export function deactivate() {}
