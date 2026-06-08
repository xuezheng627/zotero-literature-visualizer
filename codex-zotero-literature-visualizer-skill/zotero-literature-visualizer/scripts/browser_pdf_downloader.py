from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote


def wait_json(url: str, timeout: float = 20.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - depends on browser startup timing
            last = exc
            time.sleep(0.3)
    raise RuntimeError(f"Timed out waiting for {url}: {last}")


def websocket_key() -> str:
    return base64.b64encode(os.urandom(16)).decode("ascii")


class WebSocket:
    def __init__(self, ws_url: str) -> None:
        match = re.match(r"ws://([^/:]+):(\d+)(/.*)", ws_url)
        if not match:
            raise ValueError(ws_url)
        host, port, path = match.group(1), int(match.group(2)), match.group(3)
        self.sock = socket.create_connection((host, port), timeout=10)
        key = websocket_key()
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(response[:200])

    def send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def recv_text(self, timeout: float = 30.0) -> str:
        self.sock.settimeout(timeout)
        chunks: list[bytes] = []
        while True:
            first = self.sock.recv(2)
            if not first:
                raise RuntimeError("WebSocket closed")
            b1, b2 = first
            opcode = b1 & 0x0F
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.sock.recv(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.sock.recv(8))[0]
            masked = b2 & 0x80
            mask = self.sock.recv(4) if masked else b""
            payload = b""
            while len(payload) < length:
                payload += self.sock.recv(length - len(payload))
            if masked:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError("WebSocket close frame")
            if opcode in (0x1, 0x0):
                chunks.append(payload)
                if b1 & 0x80:
                    return b"".join(chunks).decode("utf-8", errors="replace")


class CDP:
    def __init__(self, ws_url: str) -> None:
        self.ws = WebSocket(ws_url)
        self.next_id = 1

    def send(self, method: str, params: dict | None = None) -> int:
        ident = self.next_id
        self.next_id += 1
        payload = {"id": ident, "method": method}
        if params is not None:
            payload["params"] = params
        self.ws.send_text(json.dumps(payload, separators=(",", ":")))
        return ident

    def recv(self, timeout: float = 30.0) -> dict:
        return json.loads(self.ws.recv_text(timeout))

    def call(self, method: str, params: dict | None = None, timeout: float = 30.0) -> dict:
        ident = self.send(method, params)
        while True:
            message = self.recv(timeout)
            if message.get("id") == ident:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})


def find_browser(preferred: str) -> Path:
    chrome = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    edge = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    candidates = chrome + edge if preferred == "chrome" else edge + chrome
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit("Could not find Chrome or Edge executable.")


def merge_dict(base: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_dict(base[key], value)
        else:
            base[key] = value
    return base


def write_browser_prefs(profile_dir: Path, download_dir: Path, open_pdf_first: bool) -> None:
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    prefs_path = default_dir / "Preferences"
    prefs = {}
    if prefs_path.exists():
        try:
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
        except Exception:
            prefs = {}
    updates = {
        "download": {
            "default_directory": str(download_dir.resolve()),
            "directory_upgrade": True,
            "prompt_for_download": False,
        },
        "plugins": {
            "always_open_pdf_externally": not open_pdf_first,
        },
        "profile": {
            "default_content_setting_values": {
                "automatic_downloads": 1,
            },
        },
        "safebrowsing": {
            "enabled": True,
        },
    }
    merge_dict(prefs, updates)
    prefs_path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")


def browser_is_running(port: int) -> bool:
    try:
        wait_json(f"http://127.0.0.1:{port}/json/version", timeout=1.5)
        return True
    except Exception:
        return False


def start_browser(
    browser: Path,
    profile_dir: Path,
    download_dir: Path,
    port: int,
    open_pdf_first: bool,
) -> subprocess.Popen | None:
    if browser_is_running(port):
        return None
    profile_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    write_browser_prefs(profile_dir, download_dir, open_pdf_first)
    args = [
        str(browser),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--disable-popup-blocking",
        "--new-window",
        "about:blank",
    ]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def new_tab(port: int, url: str = "about:blank") -> str:
    encoded = quote(url, safe="")
    errors: list[str] = []
    for method in ("PUT", "GET"):
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{encoded}", method=method)
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload["webSocketDebuggerUrl"]
        except Exception as exc:
            errors.append(f"{method}: {exc}")
    tabs = wait_json(f"http://127.0.0.1:{port}/json/list")
    for tab in tabs:
        if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
            return tab["webSocketDebuggerUrl"]
    raise RuntimeError("; ".join(errors))


def target_ids(port: int) -> set[str]:
    try:
        return {target.get("id", "") for target in wait_json(f"http://127.0.0.1:{port}/json/list", timeout=3)}
    except Exception:
        return set()


def browser_targets(port: int) -> list[dict]:
    try:
        return [
            target
            for target in wait_json(f"http://127.0.0.1:{port}/json/list", timeout=5)
            if target.get("type") in {"page", "iframe"}
        ]
    except Exception:
        return []


def read_payload(papers_path: Path) -> dict:
    payload = json.loads(papers_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"papers": payload}
    return payload


def save_payload(papers_path: Path, payload: dict) -> None:
    papers_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_name(paper: dict) -> str:
    title = re.sub(r"[^A-Za-z0-9]+", "-", paper.get("title", "")).strip("-").lower()[:90] or "paper"
    year = str(paper.get("publication_year") or paper.get("publication_date") or "year")[:4]
    doi = paper.get("doi") or paper.get("doi_url") or title
    digest = hashlib.sha1(doi.encode("utf-8")).hexdigest()[:8]
    return f"{year}-{title}-{digest}.pdf"


def evaluate(cdp: CDP, expression: str, timeout: float = 30.0):
    result = cdp.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        },
        timeout=timeout,
    )
    remote = result.get("result", {})
    return remote.get("value")


def navigate(cdp: CDP, url: str, wait: float = 4.0) -> None:
    cdp.call("Page.navigate", {"url": url}, timeout=25)
    time.sleep(wait)


PAGE_STATE_JS = r"""
(() => {
  const norm = value => (value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 4 && rect.height > 4;
  };
  const nodes = Array.from(document.querySelectorAll('a, button, [role="button"]'));
  const controls = nodes
    .filter(visible)
    .map(el => ({
      text: norm([el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].join(' ')),
      href: el.href || el.getAttribute('href') || '',
    }))
    .filter(x => {
      const haystack = `${x.text} ${x.href}`;
      if (/purchase|buy|rent|get\s+rights|rights\s+and\s+content|subscribe|getaccess/i.test(haystack)) return false;
      if (/supplementary|supplemental|supporting\s+information|additional\s+file|mediaobjects|moesm|esm\.pdf/i.test(haystack)) return false;
      return /View\s*PDF|Download\s*PDF/i.test(x.text) || /pdfft|content\/pdf|\/pdf|\.pdf/i.test(haystack);
    });
  const accessControl = nodes
    .filter(visible)
    .map(el => ({
      text: norm([el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].join(' ')),
      href: el.href || el.getAttribute('href') || '',
    }))
    .find(x => /access\s+through\s+your\s+(organization|institution)|institutional\s+access|sign\s+in/i.test(`${x.text} ${x.href}`));
  const body = norm(document.body ? document.body.innerText : '').slice(0, 3000);
  return {
    url: location.href,
    title: document.title || '',
    body,
    pdfControl: controls[0] || null,
    accessControl: accessControl || null,
    hasLoginPrompt: /sign in|log in|institution|organization|library access|access through your (institution|organization)|get access|shibboleth|single sign/i.test(body),
    hasChallengePrompt: /are you a robot|captcha challenge|confirm you are a human|please confirm you are a human/i.test(body),
    hasDeniedPrompt: /not entitled|no access|purchase|subscribe|access denied|problem providing the content/i.test(body)
  };
})()
"""


CLICK_PDF_CONTROL_JS = r"""
(() => {
  const norm = value => (value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 4 && rect.height > 4;
  };
  const nodes = Array.from(document.querySelectorAll('a, button, [role="button"]'));
  const scored = nodes
    .filter(visible)
    .map(el => {
      const text = norm([el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].join(' '));
      const href = el.href || el.getAttribute('href') || '';
      let score = 0;
      if (/View\s*PDF/i.test(text)) score += 50;
      if (/Download\s*PDF/i.test(text)) score += 50;
      if (/pdfft|content\/pdf|\/pdf|\.pdf/i.test(href)) score += 30;
      if (/purchase|buy|rent|get\s+rights|rights\s+and\s+content|subscribe|getaccess/i.test(`${text} ${href}`)) score = 0;
      if (/supplementary|supplemental|supporting\s+information|additional\s+file|mediaobjects|moesm|esm\.pdf/i.test(`${text} ${href}`)) score = 0;
      return {el, text, href, score};
    })
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score);
  const target = scored[0];
  if (!target) return {clicked: false};
  target.el.scrollIntoView({block: 'center', inline: 'center'});
  target.el.click();
  return {clicked: true, text: target.text, href: target.href};
})()
"""


CLICK_COOKIE_CHOICE_JS = r"""
(() => {
  const norm = value => (value || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 4 && rect.height > 4;
  };
  const nodes = Array.from(document.querySelectorAll('button, a, [role="button"]')).filter(visible);
  const choices = nodes
    .map(el => ({el, text: norm([el.textContent, el.getAttribute('aria-label'), el.getAttribute('title')].join(' '))}))
    .filter(x => /reject optional cookies|reject all|only essential|essential cookies|decline/i.test(x.text));
  const target = choices[0];
  if (!target) return false;
  target.el.scrollIntoView({block: 'center', inline: 'center'});
  target.el.click();
  return true;
})()
"""


PDF_VIEWER_DOWNLOAD_JS = r"""
(() => {
  const norm = value => (value || '').replace(/\s+/g, ' ').trim();
  const nodes = [];
  const visit = root => {
    if (!root || !root.querySelectorAll) return;
    for (const el of root.querySelectorAll('*')) {
      nodes.push(el);
      if (el.shadowRoot) visit(el.shadowRoot);
    }
  };
  visit(document);
  const visible = el => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 4 && rect.height > 4;
  };
  const scored = nodes
    .filter(visible)
    .map(el => {
      const text = norm([
        el.textContent,
        el.getAttribute('aria-label'),
        el.getAttribute('title'),
        el.id,
        el.className && String(el.className)
      ].join(' '));
      let score = 0;
      const haystack = `${text} ${el.id || ''}`;
      if (/drive|google|cloud|云端/i.test(haystack)) score = 0;
      else {
        if (/\bdownload\b|file-download|downloads/i.test(haystack)) score += 100;
        if (haystack.includes('下载')) score += 100;
        if (/\bsave\b/i.test(haystack) && !/save-to-drive/i.test(haystack)) score += 20;
      }
      if (/print|rotate|zoom|page|fit|presentation|annotation/i.test(haystack)) score = 0;
      return {el, text, score};
    })
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score);
  const target = scored[0];
  if (!target) return {clicked: false};
  target.el.scrollIntoView({block: 'center', inline: 'center'});
  target.el.click();
  return {clicked: true, text: target.text};
})()
"""


def set_download_behavior(cdp: CDP, download_dir: Path) -> None:
    for method, params in (
        (
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir.resolve()), "eventsEnabled": True},
        ),
        (
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir.resolve())},
        ),
    ):
        try:
            cdp.call(method, params, timeout=10)
        except Exception:
            pass


def click_pdf_viewer_download(port: int, download_dir: Path, before_targets: set[str], timeout: float = 45.0) -> dict:
    """Click the visible download control after the PDF viewer/page has opened."""
    deadline = time.time() + timeout
    last: dict = {"clicked": False}
    while time.time() < deadline:
        targets = browser_targets(port)
        candidates = []
        for target in targets:
            url = target.get("url", "")
            title = target.get("title", "")
            target_id = target.get("id", "")
            haystack = f"{url} {title}"
            is_pdf_like = bool(
                re.search(r"pdf|pdfft|chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai", haystack, re.I)
            )
            if is_pdf_like or target_id not in before_targets:
                candidates.append(target)
        for target in candidates:
            ws_url = target.get("webSocketDebuggerUrl")
            if not ws_url:
                continue
            try:
                viewer = CDP(ws_url)
                for method in ("Page.enable", "Runtime.enable"):
                    try:
                        viewer.call(method, timeout=8)
                    except Exception:
                        pass
                set_download_behavior(viewer, download_dir)
                result = evaluate(viewer, PDF_VIEWER_DOWNLOAD_JS, timeout=12) or {}
                if result.get("clicked"):
                    return result
                last = result if isinstance(result, dict) else {"clicked": False}
            except Exception as exc:
                last = {"clicked": False, "error": str(exc)}
        time.sleep(1.5)
    return last


def is_pdf(path: Path) -> bool:
    try:
        if path.stat().st_size < 10_000:
            return False
        first = path.stat().st_size
        time.sleep(0.6)
        second = path.stat().st_size
        return first == second and path.read_bytes()[:5] == b"%PDF-"
    except Exception:
        return False


def normalize_match_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def title_tokens(paper: dict) -> list[str]:
    text = normalize_match_text(paper.get("title", ""))
    stop = {
        "a",
        "an",
        "and",
        "based",
        "for",
        "in",
        "of",
        "on",
        "the",
        "to",
        "using",
        "with",
    }
    return [token for token in text.split() if len(token) >= 4 and token not in stop]


def pdf_matches_paper(path: Path, paper: dict) -> bool:
    """Best-effort guard against adopting a delayed PDF from the previous paper."""
    tokens = title_tokens(paper)
    if len(tokens) < 3:
        return True
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return True
    try:
        reader = PdfReader(str(path))
        page_text = " ".join((reader.pages[i].extract_text() or "") for i in range(min(2, len(reader.pages))))
    except Exception:
        return True
    haystack = normalize_match_text(page_text)
    hits = sum(1 for token in tokens[:12] if token in haystack)
    required = min(4, max(3, len(tokens[:12]) // 3))
    return hits >= required


def file_snapshot(folders: list[Path]) -> set[Path]:
    files: set[Path] = set()
    for folder in folders:
        if not folder.exists():
            continue
        files.update(path.resolve() for path in folder.glob("*.pdf"))
    return files


def wait_for_download(folders: list[Path], before: set[Path], timeout: float) -> Path | None:
    deadline = time.time() + timeout
    partial_suffixes = ("*.crdownload", "*.tmp", "*.download")
    while time.time() < deadline:
        partials = []
        for folder in folders:
            if not folder.exists():
                continue
            for suffix in partial_suffixes:
                partials.extend(folder.glob(suffix))
        if partials:
            time.sleep(1)
            continue
        candidates = []
        for folder in folders:
            if not folder.exists():
                continue
            candidates.extend(path.resolve() for path in folder.glob("*.pdf"))
        new_files = sorted(
            [path for path in set(candidates) - before if path.exists()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for path in new_files:
            if is_pdf(path):
                return path
        time.sleep(1)
    return None


def adopt_recent_pdf(
    download_dir: Path,
    watch_dirs: list[Path],
    before: set[Path],
    since: float,
    target: Path,
    paper: dict,
) -> Path | None:
    primary = []
    if download_dir.exists():
        primary = [
            path.resolve()
            for path in download_dir.glob("*.pdf")
            if (
                path.resolve() not in before
                and path.exists()
                and path.stat().st_mtime >= since - 5
                and is_pdf(path)
                and pdf_matches_paper(path, paper)
            )
        ]
    if primary:
        return move_downloaded_file(sorted(primary, key=lambda item: item.stat().st_mtime, reverse=True)[0], target)

    fallback = []
    for folder in watch_dirs:
        if folder.resolve() == download_dir.resolve() or not folder.exists():
            continue
        fallback.extend(
            path.resolve()
            for path in folder.glob("*.pdf")
            if (
                path.resolve() not in before
                and path.exists()
                and path.stat().st_mtime >= since - 5
                and is_pdf(path)
                and pdf_matches_paper(path, paper)
            )
        )
    fallback = sorted(set(fallback), key=lambda item: item.stat().st_mtime, reverse=True)
    if len(fallback) == 1:
        return move_downloaded_file(fallback[0], target)
    return None


def article_url(paper: dict) -> str:
    for key in ("landing_page_url", "doi_url", "publisher_url", "url"):
        url = paper.get(key) or ""
        if url and "openalex.org" not in url:
            return url
    doi = paper.get("doi") or ""
    if doi:
        return "https://doi.org/" + doi.removeprefix("https://doi.org/")
    return ""


def already_downloaded(paper: dict) -> Path | None:
    for key in ("local_pdf", "local_pdf_path"):
        value = paper.get(key)
        if not value:
            continue
        path = Path(value)
        if path.exists() and is_pdf(path):
            return path
    return None


def move_downloaded_file(downloaded: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if downloaded.resolve() == target.resolve():
        return target
    if target.exists():
        target.unlink()
    shutil.move(str(downloaded), str(target))
    return target


def download_one(
    cdp: CDP,
    paper: dict,
    rank: int,
    download_dir: Path,
    watch_dirs: list[Path],
    port: int,
    open_pdf_first: bool,
    login_timeout: float,
    download_timeout: float,
) -> dict:
    existing = already_downloaded(paper)
    if existing:
        return {"rank": rank, "status": "already-downloaded", "path": str(existing.resolve())}
    url = article_url(paper)
    if not url:
        paper["access_status"] = "needs manual PDF"
        return {"rank": rank, "status": "missing-article-url"}
    target = download_dir / safe_name(paper)
    attempt_started = time.time()
    first_snapshot = file_snapshot(watch_dirs)
    print(f"Opening #{rank:02d}: {paper.get('title')}", flush=True)
    print(f"  Article page: {url}", flush=True)
    navigate(cdp, url, wait=5)
    set_download_behavior(cdp, download_dir)
    deadline = time.time() + login_timeout
    login_notice_printed = False
    challenge_notice_printed = False
    cookie_choice_clicked = False
    last_state: dict | None = None
    while time.time() < deadline:
        try:
            state = evaluate(cdp, PAGE_STATE_JS, timeout=15) or {}
        except Exception as exc:
            last_state = {"error": str(exc)}
            time.sleep(3)
            continue
        last_state = state
        if state.get("hasLoginPrompt") and not login_notice_printed:
            print("  Login or institution prompt is visible. Complete school/library login in Chrome.", flush=True)
            login_notice_printed = True
        if state.get("hasChallengePrompt") and not challenge_notice_printed:
            print("  Human verification is visible. Complete it manually in Chrome; the script will keep waiting.", flush=True)
            challenge_notice_printed = True
        if state.get("hasDeniedPrompt") and not state.get("pdfControl"):
            print("  Access issue is visible; waiting in case login is still in progress.", flush=True)
        if not cookie_choice_clicked and re.search(r"reject optional cookies|your privacy, your choice", state.get("body", ""), re.I):
            try:
                cookie_choice_clicked = bool(evaluate(cdp, CLICK_COOKIE_CHOICE_JS, timeout=10))
                if cookie_choice_clicked:
                    print("  Closed cookie/privacy prompt with the essential-only choice.", flush=True)
                    time.sleep(2)
                    continue
            except Exception:
                pass
        if state.get("pdfControl"):
            before = file_snapshot(watch_dirs)
            before_targets = target_ids(port)
            clicked = evaluate(cdp, CLICK_PDF_CONTROL_JS, timeout=15) or {}
            if not clicked.get("clicked"):
                time.sleep(3)
                continue
            print(f"  Clicked visible PDF control: {clicked.get('text') or clicked.get('href')}", flush=True)
            viewer_result = {}
            if open_pdf_first:
                viewer_result = click_pdf_viewer_download(port, download_dir, before_targets, timeout=45)
                if viewer_result.get("clicked"):
                    print(f"  Clicked visible PDF-viewer download control: {viewer_result.get('text')}", flush=True)
            downloaded = wait_for_download(watch_dirs, before, download_timeout)
            if not downloaded:
                adopted = adopt_recent_pdf(download_dir, watch_dirs, first_snapshot, attempt_started, target, paper)
                if adopted:
                    downloaded = adopted
            if downloaded:
                if not pdf_matches_paper(downloaded, paper):
                    print("  Downloaded PDF did not match the current paper title; waiting for the correct file.", flush=True)
                    time.sleep(5)
                    continue
                saved = move_downloaded_file(downloaded, target)
                paper["local_pdf"] = str(saved.resolve())
                paper["local_pdf_path"] = str(saved.resolve())
                paper["access_status"] = "full-text pdf downloaded"
                paper["pdf_access_workflow"] = (
                    "Official article page opened in authorized browser; visible PDF page opened; "
                    "visible PDF-viewer/download control clicked; browser-native download captured."
                    if open_pdf_first
                    else "Official article page opened in authorized browser; visible PDF control clicked; "
                    "browser-native download captured."
                )
                return {
                    "rank": rank,
                    "status": "downloaded",
                    "path": str(saved.resolve()),
                    "bytes": saved.stat().st_size,
                    "clicked": clicked,
                    "viewer_download": viewer_result,
                }
            print("  Visible PDF control clicked, but Chrome did not create a PDF file yet; retrying.", flush=True)
            time.sleep(5)
            continue
        time.sleep(3)
    adopted = adopt_recent_pdf(download_dir, watch_dirs, first_snapshot, attempt_started, target, paper)
    if adopted:
        paper["local_pdf"] = str(adopted.resolve())
        paper["local_pdf_path"] = str(adopted.resolve())
        paper["access_status"] = "full-text pdf downloaded"
        paper["pdf_access_workflow"] = (
            "Official article page opened in authorized browser; visible PDF page opened; "
            "visible PDF-viewer/download control clicked; browser-native download captured after publisher delay."
            if open_pdf_first
            else "Official article page opened in authorized browser; visible PDF control clicked; "
            "browser-native download captured after publisher delay."
        )
        return {
            "rank": rank,
            "status": "downloaded-after-delay",
            "path": str(adopted.resolve()),
            "bytes": adopted.stat().st_size,
        }
    paper["access_status"] = "needs school/library login or manual PDF save"
    return {
        "rank": rank,
        "status": "not-downloaded",
        "article_url": url,
        "last_state": last_state,
    }


def parse_ranks(value: str | None) -> set[int] | None:
    if not value:
        return None
    ranks: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            ranks.update(range(int(start), int(end) + 1))
        else:
            ranks.add(int(part))
    return ranks


def main() -> int:
    parser = argparse.ArgumentParser(description="Download publisher PDFs through a visible authorized browser workflow.")
    parser.add_argument("--run-dir", default=".", help="Literature review run folder.")
    parser.add_argument("--browser", choices=["chrome", "edge"], default="chrome")
    parser.add_argument("--port", type=int, default=9244)
    parser.add_argument("--profile-dir", default="", help="Dedicated browser profile folder.")
    parser.add_argument("--download-dir", default="", help="PDF download folder.")
    parser.add_argument("--papers", default="", help="Path to papers.json; defaults to <run-dir>/metadata/papers.json.")
    parser.add_argument("--status", default="", help="Status JSON path.")
    parser.add_argument("--start-rank", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="Number of papers to try; 0 means all from start rank.")
    parser.add_argument("--ranks", default="", help="Comma/range list, e.g. 1,3,5-8.")
    parser.add_argument("--login-timeout", type=int, default=600, help="Seconds to wait for manual login/PDF control.")
    parser.add_argument("--download-timeout", type=int, default=150, help="Seconds to wait after each PDF click.")
    parser.add_argument("--delay", type=float, default=8.0, help="Polite delay between papers.")
    parser.add_argument(
        "--direct-pdf-download",
        action="store_true",
        help="Download immediately after the article-page PDF control. Default opens the PDF first, then clicks the PDF-viewer download control.",
    )
    parser.add_argument("--watch-user-downloads", action="store_true", help="Also watch the user's Downloads folder.")
    parser.add_argument("--close-browser", action="store_true", help="Close the launched browser process when done.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    papers_path = Path(args.papers).resolve() if args.papers else run_dir / "metadata" / "papers.json"
    download_dir = Path(args.download_dir).resolve() if args.download_dir else run_dir / "pdfs"
    profile_dir = Path(args.profile_dir).resolve() if args.profile_dir else run_dir / f"{args.browser}-download-profile"
    status_path = Path(args.status).resolve() if args.status else run_dir / "metadata" / f"{args.browser}-browser-download-status.json"
    download_dir.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)

    browser = find_browser(args.browser)
    open_pdf_first = not args.direct_pdf_download
    browser_proc = start_browser(browser, profile_dir, download_dir, args.port, open_pdf_first)
    wait_json(f"http://127.0.0.1:{args.port}/json/version", timeout=30)
    ws_url = new_tab(args.port)
    cdp = CDP(ws_url)
    for method in ("Page.enable", "Runtime.enable", "Network.enable"):
        try:
            cdp.call(method, timeout=15)
        except Exception:
            pass
    set_download_behavior(cdp, download_dir)

    payload = read_payload(papers_path)
    papers = payload.get("papers", [])
    selected_ranks = parse_ranks(args.ranks)
    if selected_ranks is None:
        end_rank = len(papers) if args.limit <= 0 else min(len(papers), args.start_rank + args.limit - 1)
        selected_ranks = set(range(args.start_rank, end_rank + 1))
    watch_dirs = [download_dir]
    if args.watch_user_downloads:
        watch_dirs.append(Path.home() / "Downloads")
    results = []
    try:
        for rank, paper in enumerate(papers, start=1):
            if rank not in selected_ranks:
                continue
            result = download_one(
                cdp=cdp,
                paper=paper,
                rank=rank,
                download_dir=download_dir,
                watch_dirs=watch_dirs,
                port=args.port,
                open_pdf_first=open_pdf_first,
                login_timeout=args.login_timeout,
                download_timeout=args.download_timeout,
            )
            results.append(result)
            save_payload(papers_path, payload)
            status_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, ensure_ascii=True), flush=True)
            if args.delay > 0:
                time.sleep(args.delay)
    finally:
        save_payload(papers_path, payload)
        status_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.close_browser and browser_proc:
            browser_proc.terminate()
    print(f"Status written: {status_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
