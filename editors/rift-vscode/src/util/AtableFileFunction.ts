import * as vscode from "vscode";
import { AtableFile } from "../types";
export const AtableFileFromUri = (Uri: vscode.Uri): AtableFile => {
  return {
    fileName: Uri.path.split("/").pop() ?? Uri.path,
    fullPath: Uri.fsPath,
    fromWorkspacePath: vscode.workspace.asRelativePath(Uri),
  };
};
export const AtableFileFromFsPath = (fsPath: string): AtableFile => {
  const uri = vscode.Uri.file(fsPath);
  return AtableFileFromUri(uri);
};
