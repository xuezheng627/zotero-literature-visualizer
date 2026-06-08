#!/usr/bin/env python3
"""Import downloaded papers into a Zotero personal library through the Web API.

The script intentionally never prints the API key. It supports a JSON manifest
with paper metadata and optional local PDF paths, creates Zotero journalArticle
items, and uploads local PDFs as imported_file child attachments when requested.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request


API_ROOT = "https://api.zotero.org"


class ZoteroAPIError(RuntimeError):
    pass


@dataclass
class ZoteroIdentity:
    user_id: str
    username: str
    access: dict[str, Any]


def read_api_key(path: str | None) -> str:
    if path:
        key_path = Path(path).expanduser()
        if key_path.is_dir():
            files = sorted(item for item in key_path.iterdir() if item.is_file())
            if not files:
                raise SystemExit(f"No key file found in {key_path}")
            key_path = files[0]
        key = key_path.read_text(encoding="utf-8-sig").strip()
    else:
        key = os.environ.get("ZOTERO_API_KEY", "").strip()
    if not key:
        raise SystemExit("No Zotero API key provided. Use --api-key-file or ZOTERO_API_KEY.")
    return key


def api_request(
    method: str,
    url: str,
    key: str | None = None,
    payload: bytes | None = None,
    content_type: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    all_headers = dict(headers or {})
    if key:
        all_headers["Zotero-API-Key"] = key
    if content_type:
        all_headers["Content-Type"] = content_type
    req = request.Request(url, data=payload, headers=all_headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ZoteroAPIError(f"{method} {url} failed with HTTP {exc.code}: {body[:500]}") from exc


def api_json(
    method: str,
    url: str,
    key: str,
    data: Any | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[Any, dict[str, str]]:
    payload = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    status, response_headers, body = api_request(
        method,
        url,
        key=key,
        payload=payload,
        content_type="application/json" if data is not None else None,
        headers=headers,
    )
    if not body:
        return None, response_headers
    return json.loads(body.decode("utf-8")), response_headers


def write_token() -> str:
    return uuid.uuid4().hex


def verify_key(key: str) -> ZoteroIdentity:
    data, _ = api_json("GET", f"{API_ROOT}/keys/current", key)
    access = data.get("access") or {}
    user_access = access.get("user") or {}
    if not user_access.get("library"):
        raise SystemExit("The key cannot access the personal library.")
    return ZoteroIdentity(str(data["userID"]), data.get("username", ""), access)


def require_personal_write(identity: ZoteroIdentity) -> None:
    user_access = (identity.access.get("user") or {})
    if not user_access.get("write"):
        raise SystemExit("The key can read the personal library but does not have write access.")


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        rows = payload.get("papers") or payload.get("items") or payload.get("records")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise SystemExit("Manifest must be a JSON list, or an object with papers/items/records.")
    return [dict(row) for row in rows]


def split_authors(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        names = []
        for item in value:
            if isinstance(item, dict):
                first = item.get("firstName") or item.get("given") or ""
                last = item.get("lastName") or item.get("family") or item.get("name") or ""
                names.append({"creatorType": "author", "firstName": str(first), "lastName": str(last).strip()})
            else:
                names.append({"creatorType": "author", "name": str(item)})
        return [name for name in names if name.get("lastName") or name.get("name")]
    text = str(value or "").strip()
    if not text:
        return []
    parts = [part.strip() for chunk in text.split(";") for part in chunk.split(" and ") if part.strip()]
    creators: list[dict[str, str]] = []
    for name in parts:
        if "," in name:
            last, first = [part.strip() for part in name.split(",", 1)]
            creators.append({"creatorType": "author", "firstName": first, "lastName": last})
        else:
            bits = name.split()
            if len(bits) >= 2:
                creators.append({"creatorType": "author", "firstName": " ".join(bits[:-1]), "lastName": bits[-1]})
            else:
                creators.append({"creatorType": "author", "name": name})
    return creators


def paper_date(row: dict[str, Any]) -> str:
    for key in ("date", "publication_date", "published", "year", "publication_year"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def local_pdf_path(row: dict[str, Any], manifest_dir: Path) -> Path | None:
    value = str(row.get("local_pdf_path") or row.get("local_pdf") or row.get("pdf_path") or "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = manifest_dir / path
    return path if path.exists() and path.is_file() else None


def zotero_item(row: dict[str, Any], collection_key: str | None, tag: str) -> dict[str, Any]:
    doi = str(row.get("doi") or row.get("DOI") or "").strip()
    url = str(row.get("doi_url") or row.get("url") or "").strip()
    if doi and not url:
        url = f"https://doi.org/{doi}"
    item = {
        "itemType": "journalArticle",
        "title": str(row.get("title") or "").strip(),
        "creators": split_authors(row.get("authors") or row.get("creators")),
        "abstractNote": str(row.get("abstract") or row.get("summary") or "").strip(),
        "publicationTitle": str(row.get("journal") or row.get("publicationTitle") or row.get("container_title") or "").strip(),
        "date": paper_date(row),
        "DOI": doi,
        "url": url,
        "language": str(row.get("language") or "").strip(),
        "tags": [{"tag": tag}] if tag else [],
        "collections": [collection_key] if collection_key else [],
    }
    return {key: value for key, value in item.items() if value not in ("", [], None)}


def find_existing_by_doi(key: str, user_id: str, doi: str) -> str | None:
    if not doi:
        return None
    q = parse.urlencode({"q": doi, "qmode": "everything", "format": "json", "limit": "25"})
    data, _ = api_json("GET", f"{API_ROOT}/users/{user_id}/items?{q}", key)
    for item in data:
        item_data = item.get("data") or {}
        if str(item_data.get("DOI") or "").strip().lower() == doi.lower():
            return item_data.get("key")
    return None


def ensure_collection(key: str, user_id: str, name: str | None) -> str | None:
    if not name:
        return None
    query = parse.urlencode({"format": "json", "limit": "100"})
    data, _ = api_json("GET", f"{API_ROOT}/users/{user_id}/collections?{query}", key)
    for collection in data:
        collection_data = collection.get("data") or {}
        if collection_data.get("name") == name:
            return collection_data.get("key")
    payload = [{"name": name, "parentCollection": False}]
    result, _ = api_json(
        "POST",
        f"{API_ROOT}/users/{user_id}/collections",
        key,
        payload,
        headers={"Zotero-Write-Token": write_token()},
    )
    success = result.get("success") or {}
    if "0" not in success:
        raise ZoteroAPIError(f"Could not create collection {name!r}: {result}")
    return success["0"]


def create_item(key: str, user_id: str, item: dict[str, Any]) -> str:
    result, _ = api_json(
        "POST",
        f"{API_ROOT}/users/{user_id}/items",
        key,
        [item],
        headers={"Zotero-Write-Token": write_token()},
    )
    success = result.get("success") or {}
    if "0" not in success:
        raise ZoteroAPIError(f"Could not create item {item.get('title')!r}: {result}")
    return success["0"]


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_attachment_item(key: str, user_id: str, parent_key: str, path: Path) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
    payload = [
        {
            "itemType": "attachment",
            "parentItem": parent_key,
            "linkMode": "imported_file",
            "title": path.name,
            "contentType": content_type,
            "filename": path.name,
        }
    ]
    result, _ = api_json(
        "POST",
        f"{API_ROOT}/users/{user_id}/items",
        key,
        payload,
        headers={"Zotero-Write-Token": write_token()},
    )
    success = result.get("success") or {}
    if "0" not in success:
        raise ZoteroAPIError(f"Could not create attachment for {path.name!r}: {result}")
    return success["0"]


def normalized_attachment_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").lower()


def find_existing_child_attachment(key: str, user_id: str, parent_key: str, path: Path) -> str | None:
    query = parse.urlencode({"format": "json", "limit": "100"})
    data, _ = api_json("GET", f"{API_ROOT}/users/{user_id}/items/{parent_key}/children?{query}", key)
    wanted_path = normalized_attachment_path(str(path))
    wanted_name = path.name.lower()
    for item in data:
        item_data = item.get("data") or {}
        if item_data.get("itemType") != "attachment":
            continue
        item_path = normalized_attachment_path(str(item_data.get("path") or ""))
        item_title = str(item_data.get("title") or "").strip().lower()
        item_filename = str(item_data.get("filename") or "").strip().lower()
        if item_path and item_path == wanted_path:
            return item_data.get("key")
        if item_title == wanted_name or item_filename == wanted_name:
            return item_data.get("key")
    return None


def create_linked_file_attachment_item(key: str, user_id: str, parent_key: str, path: Path) -> tuple[str, str]:
    existing_key = find_existing_child_attachment(key, user_id, parent_key, path)
    if existing_key:
        return existing_key, "already-linked"
    content_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
    payload = [
        {
            "itemType": "attachment",
            "parentItem": parent_key,
            "linkMode": "linked_file",
            "title": path.name,
            "contentType": content_type,
            "path": str(path),
        }
    ]
    result, _ = api_json(
        "POST",
        f"{API_ROOT}/users/{user_id}/items",
        key,
        payload,
        headers={"Zotero-Write-Token": write_token()},
    )
    success = result.get("success") or {}
    if "0" not in success:
        raise ZoteroAPIError(f"Could not create linked-file attachment for {path.name!r}: {result}")
    return success["0"], "linked"


def delete_item(key: str, user_id: str, item_key: str) -> bool:
    data, _ = api_json("GET", f"{API_ROOT}/users/{user_id}/items/{item_key}", key)
    version = ((data or {}).get("data") or {}).get("version")
    if not version:
        return False
    api_request(
        "DELETE",
        f"{API_ROOT}/users/{user_id}/items/{item_key}",
        key=key,
        headers={"If-Unmodified-Since-Version": str(version)},
    )
    return True


def upload_attachment_file(key: str, user_id: str, attachment_key: str, path: Path) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
    form = {
        "md5": file_md5(path),
        "filename": path.name,
        "filesize": str(path.stat().st_size),
        "mtime": str(int(path.stat().st_mtime * 1000)),
        "contentType": content_type,
    }
    auth_payload = parse.urlencode(form).encode("utf-8")
    _, _, body = api_request(
        "POST",
        f"{API_ROOT}/users/{user_id}/items/{attachment_key}/file",
        key=key,
        payload=auth_payload,
        content_type="application/x-www-form-urlencoded",
        headers={"If-None-Match": "*"},
    )
    authorization = json.loads(body.decode("utf-8")) if body else {}
    if authorization.get("exists"):
        return "exists"
    upload_key = authorization.get("uploadKey")
    if not upload_key:
        raise ZoteroAPIError(f"Upload authorization did not include uploadKey: {authorization}")
    prefix = authorization.get("prefix", "").encode("utf-8")
    suffix = authorization.get("suffix", "").encode("utf-8")
    upload_content_type = authorization.get("contentType", content_type)
    binary = path.read_bytes()
    api_request(
        "POST",
        authorization["url"],
        payload=prefix + binary + suffix,
        content_type=upload_content_type,
    )
    register_payload = parse.urlencode({"upload": upload_key}).encode("utf-8")
    api_request(
        "POST",
        f"{API_ROOT}/users/{user_id}/items/{attachment_key}/file",
        key=key,
        payload=register_payload,
        content_type="application/x-www-form-urlencoded",
        headers={"If-None-Match": "*"},
    )
    return "uploaded"


def command_verify(args: argparse.Namespace) -> int:
    key = read_api_key(args.api_key_file)
    identity = verify_key(key)
    user_access = identity.access.get("user") or {}
    summary = {
        "username": identity.username,
        "user_id": identity.user_id,
        "personal_library": bool(user_access.get("library")),
        "personal_write": bool(user_access.get("write")),
        "personal_files": bool(user_access.get("files")),
        "groups": "none" if not identity.access.get("groups") else "configured",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def command_import(args: argparse.Namespace) -> int:
    key = read_api_key(args.api_key_file)
    identity = verify_key(key)
    require_personal_write(identity)
    user_access = identity.access.get("user") or {}
    if args.upload_files and args.link_files:
        raise SystemExit("Use either --upload-files for Zotero cloud storage or --link-files for local linked files, not both.")
    if args.upload_files and not user_access.get("files"):
        raise SystemExit("The key does not have personal file access, so PDFs cannot be uploaded.")
    manifest_path = Path(args.manifest).resolve()
    rows = load_manifest(manifest_path)
    collection_key = None if args.dry_run else ensure_collection(key, identity.user_id, args.collection)
    results: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        title = str(row.get("title") or "").strip()
        doi = str(row.get("doi") or row.get("DOI") or "").strip()
        if not title:
            results.append({"index": index, "status": "skipped", "reason": "missing title"})
            continue
        existing_key = find_existing_by_doi(key, identity.user_id, doi) if args.skip_existing else None
        path = local_pdf_path(row, manifest_path.parent)
        if existing_key:
            result = {"index": index, "status": "exists", "item_key": existing_key, "doi": doi, "title": title}
            if args.link_files and path:
                attachment_key, link_status = create_linked_file_attachment_item(key, identity.user_id, existing_key, path)
                result.update({"attachment_key": attachment_key, "file_status": link_status, "pdf": str(path)})
            elif args.upload_files and path:
                attachment_key = create_attachment_item(key, identity.user_id, existing_key, path)
                try:
                    upload_status = upload_attachment_file(key, identity.user_id, attachment_key, path)
                    result.update({"attachment_key": attachment_key, "file_status": upload_status, "pdf": str(path)})
                except ZoteroAPIError as exc:
                    deleted_placeholder = False
                    try:
                        deleted_placeholder = delete_item(key, identity.user_id, attachment_key)
                    except ZoteroAPIError:
                        deleted_placeholder = False
                    result.update({
                        "attachment_key": attachment_key,
                        "file_status": "failed",
                        "file_error": str(exc),
                        "failed_attachment_placeholder_deleted": deleted_placeholder,
                        "dashboard_local_pdf_overlay": True,
                    })
            elif args.link_files or args.upload_files:
                result["file_status"] = "missing local pdf"
            results.append(result)
            continue
        item = zotero_item(row, collection_key, args.tag)
        if args.dry_run:
            results.append({"index": index, "status": "dry-run", "title": title, "doi": doi})
            continue
        item_key = create_item(key, identity.user_id, item)
        result = {"index": index, "status": "created", "item_key": item_key, "doi": doi, "title": title}
        if args.upload_files and path:
            attachment_key = create_attachment_item(key, identity.user_id, item_key, path)
            try:
                upload_status = upload_attachment_file(key, identity.user_id, attachment_key, path)
                result.update({"attachment_key": attachment_key, "file_status": upload_status, "pdf": str(path)})
            except ZoteroAPIError as exc:
                deleted_placeholder = False
                try:
                    deleted_placeholder = delete_item(key, identity.user_id, attachment_key)
                except ZoteroAPIError:
                    deleted_placeholder = False
                result.update({
                    "attachment_key": attachment_key,
                    "file_status": "failed",
                    "file_error": str(exc),
                    "failed_attachment_placeholder_deleted": deleted_placeholder,
                    "dashboard_local_pdf_overlay": True,
                })
        elif args.upload_files:
            result["file_status"] = "missing local pdf"
        elif args.link_files and path:
            attachment_key, link_status = create_linked_file_attachment_item(key, identity.user_id, item_key, path)
            result.update({"attachment_key": attachment_key, "file_status": link_status, "pdf": str(path)})
        elif args.link_files:
            result["file_status"] = "missing local pdf"
        results.append(result)
        time.sleep(args.delay)

    output = {"username": identity.username, "user_id": identity.user_id, "results": results}
    if args.output:
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "created": sum(1 for item in results if item["status"] == "created"),
        "exists": sum(1 for item in results if item["status"] == "exists"),
        "skipped": sum(1 for item in results if item["status"] == "skipped"),
        "dry_run": sum(1 for item in results if item["status"] == "dry-run"),
        "uploaded_files": sum(1 for item in results if item.get("file_status") == "uploaded"),
        "linked_files": sum(1 for item in results if item.get("file_status") in {"linked", "already-linked"}),
        "failed_files": sum(1 for item in results if item.get("file_status") == "failed"),
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import downloaded papers into Zotero via the official Web API.")
    parser.add_argument("--api-key-file", help="Path to a Zotero API key file. If omitted, ZOTERO_API_KEY is used.")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify-key", help="Validate API key permissions without printing the key.")
    verify.set_defaults(func=command_verify)

    imp = sub.add_parser("import-manifest", help="Create Zotero items from a JSON/CSV manifest.")
    imp.add_argument("--manifest", required=True, help="JSON/CSV manifest with title, DOI, journal, authors, and PDF path fields.")
    imp.add_argument("--collection", default="Codex Imported Papers", help="Zotero collection name to create/use.")
    imp.add_argument("--tag", default="Codex-imported", help="Tag added to imported items.")
    imp.add_argument("--upload-files", action="store_true", help="Upload local PDFs listed in the manifest as Zotero attachments.")
    imp.add_argument("--link-files", action="store_true", help="Attach local PDFs as linked_file attachments without uploading them to Zotero storage.")
    imp.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True, help="Skip items with an existing DOI match.")
    imp.add_argument("--no-skip-existing", dest="skip_existing", action="store_false", help="Do not check Zotero for existing DOI matches before import.")
    imp.add_argument("--dry-run", action="store_true", help="Validate manifest and permissions without writing items.")
    imp.add_argument("--delay", type=float, default=0.2, help="Delay between item writes, in seconds.")
    imp.add_argument("--output", help="Optional JSON log path.")
    imp.set_defaults(func=command_import)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ZoteroAPIError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
