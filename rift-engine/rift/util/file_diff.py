import os
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Any

import rift.lsp.types as lsp

from diff_match_patch import diff_match_patch

from rift.lsp import (
    CreateFile,
    Range,
    TextDocumentEdit,
    TextDocumentIdentifier,
    TextEdit,
    WorkspaceEdit,
)
from rift.lsp.types import ChangeAnnotation


@dataclass
class FileChange:
    uri: TextDocumentIdentifier
    old_content: str
    new_content: str
    description: Optional[str] = None
    is_new_file: bool = False


def get_file_change(path: str, new_content: str) -> FileChange:
    uri = TextDocumentIdentifier(uri="file://" + path, version=0)
    if os.path.isfile(path):
        with open(path, "r") as f:
            old_content = f.read()
            return FileChange(uri=uri, old_content=old_content, new_content=new_content)
    else:
        return FileChange(uri=uri, old_content="", new_content=new_content, is_new_file=True)


def edits_from_file_change(file_change: FileChange, user_confirmation: bool = False) -> WorkspaceEdit:
    dmp = diff_match_patch()
    diff = dmp.diff_main(file_change.old_content, file_change.new_content)

    line = 0  # current line number
    char = 0  # current character position within the line
    edits = []  # list of TextEdit objects

    for op, text in diff:
        # count the number of lines in `text` and the number of characters in the last line
        lines = text.split("\n")
        last_line_chars = len(lines[-1])
        line_count = len(lines) - 1  # don't count the current line

        end_line = line + line_count
        end_char = (
            char + last_line_chars if line_count == 0 else last_line_chars
        )  # if we moved to a new line, start at char 0

        if op == -1:
            # text was deleted
            edits.append(TextEdit(Range.mk(line, char, end_line, end_char), "", annotationId="rift"))
        elif op == 1:
            # text was added
            edits.append(
                TextEdit(Range.mk(line, char, line, char), text, annotationId="rift")
            )  # new text starts at the current position

        # update position
        line = end_line
        char = end_char

    documentChanges = []

    changeAnnotations: dict[lsp.ChangeAnnotationIdentifier, lsp.ChangeAnnotation] = dict()
    if file_change.is_new_file:
        documentChanges.append(CreateFile(kind="create", uri=file_change.uri.uri, annotationId="rift"))
    documentChanges.append(TextDocumentEdit(textDocument=file_change.uri, edits=edits))
    changeAnnotations["rift"] = lsp.ChangeAnnotation(label="rift", needsConfirmation=user_confirmation, description=None)
    return WorkspaceEdit(documentChanges=documentChanges, changeAnnotations=changeAnnotations)


def edits_from_file_changes(file_changes: List[FileChange], user_confirmation: bool = False) -> WorkspaceEdit:
    documentChanges: List[Union[lsp.TextDocumentEdit, lsp.CreateFile, lsp.RenameFile, lsp.DeleteFile]] = []
    changeAnnotations: Dict[ChangeAnnotationIdentifier, ChangeAnnotation] = dict()
    for file_change in file_changes:
        edit = edits_from_file_change(file_change=file_change, user_confirmation=user_confirmation)
        documentChanges += edit.documentChanges
        if edit.changeAnnotations is not None:
            changeAnnotations.update(edit.changeAnnotations)
    return WorkspaceEdit(documentChanges=documentChanges, changeAnnotations=changeAnnotations)


if __name__ == "__main__":
    file1 = "tests/diff/file1.txt"
    file2 = "tests/diff/file2.txt"
    with open(file1, "r") as f1, open(file2, "r") as f2:
        uri = TextDocumentIdentifier(uri="file://" + file1, version=0)
        file_change = get_file_change(path=file1, new_content=f2.read())
        workspace_edit = edits_from_file_change(file_change=file_change)
        print(f"\nworkspace_edit: {workspace_edit}\n")
        dummy_path = "dummy.txt"
        dummy_content = "dummy content"
        file_change = get_file_change(path=dummy_path, new_content=dummy_content)
        workspace_edit = edits_from_file_change(file_change=file_change)
        print(f"\ntest_new_file: {workspace_edit}\n")
