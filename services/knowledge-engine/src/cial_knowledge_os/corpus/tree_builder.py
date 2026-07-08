"""Build an in-memory Corpus Tree from scanner output."""

from __future__ import annotations

from .models import CorpusFile, CorpusFolder, CorpusTree, ScanResult


class CorpusTreeBuilder:
    def build(self, scan_result: ScanResult) -> CorpusTree:
        folders_by_path: dict[str, CorpusFolder] = {}
        for scanned in scan_result.folders:
            folders_by_path[scanned.relative_path] = CorpusFolder(
                name=scanned.name,
                relative_path=scanned.relative_path,
                parent_relative_path=scanned.parent_relative_path,
                depth=scanned.depth,
            )

        root = folders_by_path[""]
        for folder in sorted(folders_by_path.values(), key=lambda item: (item.depth, item.relative_path)):
            if folder.relative_path == "":
                continue
            parent = folders_by_path.get(folder.parent_relative_path or "")
            if parent is not None:
                parent.children.append(folder)

        files_by_path: dict[str, CorpusFile] = {}
        for scanned_file in scan_result.files:
            file = CorpusFile(
                name=scanned_file.name,
                relative_path=scanned_file.relative_path,
                folder_relative_path=scanned_file.folder_relative_path,
                extension=scanned_file.extension,
                mime_type=scanned_file.mime_type,
                size_bytes=scanned_file.size_bytes,
                modified_at=scanned_file.modified_at,
                content_hash=scanned_file.content_hash,
            )
            files_by_path[file.relative_path] = file
            folder = folders_by_path.get(file.folder_relative_path)
            if folder is not None:
                folder.files.append(file)

        for folder in folders_by_path.values():
            folder.children.sort(key=lambda item: item.name.casefold())
            folder.files.sort(key=lambda item: item.name.casefold())

        return CorpusTree(
            root=root,
            scanned_at=scan_result.scanned_at,
            folders_by_path=folders_by_path,
            files_by_path=files_by_path,
        )

