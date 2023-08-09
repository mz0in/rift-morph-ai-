import * as vscode from "vscode";
import { MorphLanguageClient } from "./client";
import { WebviewProvider } from "./elements/WebviewProvider";
import { ensureRiftHook, checkExtensionVersion } from "./activation/environmentSetup";
export let chatProvider: WebviewProvider;
export let logProvider: WebviewProvider;

export function activate(context: vscode.ExtensionContext) {
    const autostart: boolean | undefined = vscode.workspace
        .getConfiguration("rift")
        .get("autostart");

    checkExtensionVersion();

    if (autostart) {
        ensureRiftHook();
    }

    let morph_language_client = new MorphLanguageClient(context);

    context.subscriptions.push(
        vscode.languages.registerCodeLensProvider("*", morph_language_client)
    );

    chatProvider = new WebviewProvider(
        "Chat",
        context.extensionUri,
        morph_language_client
    );
    logProvider = new WebviewProvider(
        "Logs",
        context.extensionUri,
        morph_language_client
    );

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider("RiftChat", chatProvider, {
            webviewOptions: { retainContextWhenHidden: true },
        })
    );
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider("RiftLogs", logProvider, {
            webviewOptions: { retainContextWhenHidden: true },
        })
    );

    let recentlyOpenedFiles: string[] = [];
    vscode.workspace.onDidOpenTextDocument((document) => {
        const filePath = document.uri.fsPath;
        if (filePath.endsWith(".git")) return; // weirdly getting both file.txt and file.txt.git on every file change

        // Check if file path already exists in the recent files list
        const existingIndex = recentlyOpenedFiles.indexOf(filePath);

        // If the file is found, remove it from the current location
        if (existingIndex > -1) {
            recentlyOpenedFiles.splice(existingIndex, 1);
        }

        // Add the file to the end of the list (top of the stack)
        recentlyOpenedFiles.push(filePath);

        // Limit the history to the last 10 files
        if (recentlyOpenedFiles.length > 10) {
            recentlyOpenedFiles.shift();
        }

        morph_language_client.sendRecentlyOpenedFilesChange(recentlyOpenedFiles);
    });
    console.log('Congratulations, your extension "rift" is now active!');

    let disposablefocusOmnibar = vscode.commands.registerCommand(
        "rift.focus_omnibar",
        async () => {
            // vscode.window.createTreeView("RiftChat", chatProvider)
            vscode.commands.executeCommand("RiftChat.focus");

            morph_language_client.focusOmnibar();
        }
    );

    context.subscriptions.push(
        vscode.commands.registerCommand("rift.reset_chat", () => {
            morph_language_client.restartActiveAgent();
        })
    );

    context.subscriptions.push(disposablefocusOmnibar);
    context.subscriptions.push(morph_language_client);
}

// This method is called when your extension is deactivated
export function deactivate() {}
