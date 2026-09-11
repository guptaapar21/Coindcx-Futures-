#!/usr/bin/env python3
"""GitHub Actions artifact monitor + release archival/rotation for Futures-only data.

Short-lived raw Actions artifacts are periodically promoted into GitHub Release
assets. Only after every selected asset uploads successfully are the corresponding
Actions artifacts deleted. Repository-wide Actions artifact usage controls when
rotation starts; only Futures raw artifacts are eligible for rotation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

API = "https://api.github.com"
API_VERSION = "2022-11-28"


def headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }


def get_artifacts(session: requests.Session, owner: str, repo: str, token: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        r = session.get(
            f"{API}/repos/{owner}/{repo}/actions/artifacts",
            headers=headers(token),
            params={"per_page": 100, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        items = r.json().get("artifacts", [])
        out.extend(items)
        if len(items) < 100:
            break
        page += 1
    return [x for x in out if not x.get("expired")]


def repo_release_create(
    session: requests.Session,
    owner: str,
    repo: str,
    token: str,
    tag: str,
    name: str,
) -> dict[str, Any]:
    r = session.post(
        f"{API}/repos/{owner}/{repo}/releases",
        headers={**headers(token), "Content-Type": "application/json"},
        json={"tag_name": tag, "name": name, "draft": False, "prerelease": False},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def upload_asset(
    session: requests.Session,
    release: dict[str, Any],
    path: Path,
    token: str,
) -> dict[str, Any]:
    url = release["upload_url"].split("{")[0]
    with path.open("rb") as fh:
        r = session.post(
            url,
            headers={**headers(token), "Content-Type": "application/zip"},
            params={"name": path.name},
            data=fh,
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


def delete_artifact(session: requests.Session, owner: str, repo: str, token: str, artifact_id: int) -> None:
    r = session.delete(
        f"{API}/repos/{owner}/{repo}/actions/artifacts/{artifact_id}",
        headers=headers(token),
        timeout=30,
    )
    if r.status_code not in (204, 404):
        r.raise_for_status()


def download_artifact(
    session: requests.Session,
    artifact: dict[str, Any],
    token: str,
    path: Path,
) -> None:
    r = session.get(
        artifact["archive_download_url"],
        headers=headers(token),
        timeout=120,
        allow_redirects=True,
    )
    r.raise_for_status()
    path.write_bytes(r.content)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_owner_repo() -> tuple[str, str]:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        raise RuntimeError("GITHUB_REPOSITORY is required")
    return tuple(repo.split("/", 1))  # type: ignore[return-value]


def select_artifacts_for_target(
    eligible: list[dict[str, Any]],
    current_total_bytes: int,
    target_total_bytes: float,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Select oldest eligible raw artifacts until total usage reaches target."""
    selected: list[dict[str, Any]] = []
    running = int(current_total_bytes)
    for artifact in sorted(eligible, key=lambda x: x.get("created_at") or ""):
        if running <= target_total_bytes and not force:
            break
        selected.append(artifact)
        running -= int(artifact.get("size_in_bytes", 0))
    return selected


def archive_artifacts(
    session: requests.Session,
    selected: list[dict[str, Any]],
    owner: str,
    repo: str,
    token: str,
    max_mb: int,
) -> list[dict[str, Any]]:
    if not selected:
        return []

    max_bytes = max_mb * 1024 * 1024
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        downloaded: list[tuple[dict[str, Any], Path]] = []
        for art in selected:
            dest = root / f"artifact_{art['id']}.zip"
            download_artifact(session, art, token, dest)
            downloaded.append((art, dest))

        # Keep each release asset safely below the configured release-asset ceiling.
        parts: list[list[tuple[dict[str, Any], Path]]] = []
        current: list[tuple[dict[str, Any], Path]] = []
        current_size = 0
        soft = int(max_bytes * 0.98)
        for item in downloaded:
            size = item[1].stat().st_size
            if current and current_size + size > soft:
                parts.append(current)
                current = []
                current_size = 0
            current.append(item)
            current_size += size
        if current:
            parts.append(current)

        tag = "futures-data-archive-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        release = repo_release_create(
            session,
            owner,
            repo,
            token,
            tag,
            f"CoinDCX Futures data archive {tag[-16:]}",
        )
        uploads: list[dict[str, Any]] = []

        for idx, part in enumerate(parts, start=1):
            asset = root / f"coindcx_futures_raw_archive_{tag}_part{idx:02d}.zip"
            manifest = {
                "archive_tag": tag,
                "market_mode": "FUTURES_ONLY",
                "part": idx,
                "artifacts": [
                    {
                        k: art.get(k)
                        for k in (
                            "id",
                            "name",
                            "size_in_bytes",
                            "created_at",
                            "expires_at",
                            "workflow_run",
                        )
                    }
                    for art, _ in part
                ],
            }
            with zipfile.ZipFile(asset, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr("archive_manifest.json", json.dumps(manifest, indent=2))
                for art, zpath in part:
                    zf.write(zpath, arcname=f"artifacts/{art['name']}.zip")

            upload = upload_asset(session, release, asset, token)
            uploads.append(
                {
                    "asset": upload.get("name"),
                    "size": upload.get("size"),
                    "sha256": sha256(asset),
                }
            )

        # Deletion is deliberately last: a partial upload must never destroy raw data.
        for art in selected:
            delete_artifact(session, owner, repo, token, int(art["id"]))

        return [{"release": release.get("html_url"), "tag": tag, "uploads": uploads}]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")

    owner, repo = parse_owner_repo()
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads(root.joinpath("config.json").read_text(encoding="utf-8"))
    storage = cfg["storage"]

    session = requests.Session()
    artifacts = get_artifacts(session, owner, repo, token)
    raw = [
        a
        for a in artifacts
        if str(a.get("name", "")).startswith(storage["raw_artifact_prefix"])
    ]
    total_all = sum(int(a.get("size_in_bytes", 0)) for a in artifacts)
    total_raw = sum(int(a.get("size_in_bytes", 0)) for a in raw)
    budget = int(storage["artifact_budget_mb"]) * 1024 * 1024
    pct = 100.0 * total_all / budget if budget else 0.0
    now = datetime.now(timezone.utc)

    protected_path = root / storage["protected_file"]
    protected: set[str] = set()
    if protected_path.exists():
        try:
            protected = set(json.loads(protected_path.read_text(encoding="utf-8")).get("batch_ids", []))
        except Exception:
            protected = set()

    def is_protected(artifact: dict[str, Any]) -> bool:
        name = str(artifact.get("name", ""))
        return any(str(x) in name for x in protected)

    eligible = [a for a in raw if not is_protected(a)]
    eligible.sort(key=lambda x: x.get("created_at") or "")

    should_archive = args.force or pct >= float(storage["archive_trigger_percent"])
    max_age_h = float(cfg["research"]["raw_archive_after_hours"])
    oldest_age_h = None
    if eligible:
        oldest = eligible[0].get("created_at")
        if oldest:
            try:
                oldest_age_h = (
                    now - datetime.fromisoformat(oldest.replace("Z", "+00:00"))
                ).total_seconds() / 3600
                should_archive = should_archive or oldest_age_h >= max_age_h
            except Exception:
                pass

    report: dict[str, Any] = {
        "checked_utc": now.isoformat(),
        "repository": f"{owner}/{repo}",
        "market_mode": "FUTURES_ONLY",
        "raw_artifact_prefix": storage["raw_artifact_prefix"],
        "raw_artifact_count": len(raw),
        "all_artifact_count": len(artifacts),
        "all_artifact_bytes": total_all,
        "raw_artifact_bytes": total_raw,
        "artifact_budget_bytes": budget,
        "all_artifact_storage_percent": pct,
        "raw_storage_percent": (100.0 * total_raw / budget if budget else 0.0),
        "oldest_eligible_age_hours": oldest_age_h,
        "archive_trigger_percent": storage["archive_trigger_percent"],
        "archive_target_percent": storage["archive_target_percent"],
        "should_archive": should_archive,
        "selected": [],
        "archives": [],
        "deletion_policy": "Delete selected Actions artifacts only after every archive asset upload succeeds.",
    }

    if should_archive and eligible:
        target = budget * float(storage["archive_target_percent"]) / 100.0
        selected = select_artifacts_for_target(
            eligible,
            total_all,
            target,
            force=args.force,
        )
        report["selected"] = [a["name"] for a in selected]
        if selected:
            report["archives"] = archive_artifacts(
                session,
                selected,
                owner,
                repo,
                token,
                int(storage["release_asset_max_mb"]),
            )

    out = Path("storage_report.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
