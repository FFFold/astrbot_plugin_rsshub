#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate markdown knowledgebase from RSSHub routes.json"
    )
    parser.add_argument("--input", required=True, help="Path to RSSHub routes.json")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument(
        "--source-revision",
        default="unknown",
        help="Revision string for RSSHub source repository",
    )
    parser.add_argument(
        "--source-repo",
        default="https://github.com/DIYgod/RSSHub",
        help="Source repository URL",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("@/", "")
    value = re.sub(r"[{}:+*?()[\],.=]", "-", value)
    value = value.replace("/", "-")
    value = value.replace(":", "")
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    value = value.strip("-_")
    return value or "index"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass
class Document:
    relative_path: str
    title: str
    markdown: str
    namespace: str
    route_path: str
    namespace_name: str
    categories: list[str]
    maintainers: list[str]


def infer_aliases(namespace: str, namespace_name: str, url: str) -> list[str]:
    aliases = {namespace.lower()}
    if namespace_name:
        aliases.add(namespace_name.lower())
    if url and url != "_None_":
        aliases.add(url.lower())
        aliases.add(url.lower().replace("www.", ""))
        aliases.add(url.split(".")[0].lower())
    if namespace == "twitter":
        aliases.update({"twitter", "x", "x-twitter", "推特"})
    return sorted(alias for alias in aliases if alias)


TWITTER_ROUTE_NOTES = """## Route Notes
This namespace has additional official guidance beyond the route index.

### routeParams
Specify options in `routeParams` to control extra tweet rendering features.

| Key | Description | Accepts | Default |
| --- | --- | --- | --- |
| `readable` | Enable readable layout | `0`/`1`/`true`/`false` | `false` |
| `authorNameBold` | Display author name in bold | `0`/`1`/`true`/`false` | `false` |
| `showAuthorInTitle` | Show author name in title | `0`/`1`/`true`/`false` | `false` (`true` in `/twitter/followings`) |
| `showAuthorAsTitleOnly` | Show only author name as title | `0`/`1`/`true`/`false` | `false` |
| `showAuthorInDesc` | Show author name in description | `0`/`1`/`true`/`false` | `false` (`true` in `/twitter/followings`) |
| `showQuotedAuthorAvatarInDesc` | Show quoted tweet author avatar in description | `0`/`1`/`true`/`false` | `false` |
| `showAuthorAvatarInDesc` | Show author avatar in description | `0`/`1`/`true`/`false` | `false` |
| `showEmojiForRetweetAndReply` | Use `🔁` and `↩️`/`💬` symbols | `0`/`1`/`true`/`false` | `false` |
| `showSymbolForRetweetAndReply` | Use ` RT ` / ` Re ` text markers | `0`/`1`/`true`/`false` | `true` |
| `showRetweetTextInTitle` | Show quote comments in title | `0`/`1`/`true`/`false` | `true` |
| `addLinkForPics` | Add clickable links for tweet pictures | `0`/`1`/`true`/`false` | `false` |
| `showTimestampInDescription` | Show timestamp in description | `0`/`1`/`true`/`false` | `false` |
| `showQuotedInTitle` | Show quoted tweet in title | `0`/`1`/`true`/`false` | `false` |
| `widthOfPics` | Width of tweet pictures | Unspecified/Integer | Unspecified |
| `heightOfPics` | Height of tweet pictures | Unspecified/Integer | Unspecified |
| `sizeOfAuthorAvatar` | Size of author avatar | Integer | `48` |
| `sizeOfQuotedAuthorAvatar` | Size of quoted tweet author avatar | Integer | `24` |
| `includeReplies` | Include replies, only for `/twitter/user` | `0`/`1`/`true`/`false` | `false` |
| `includeRts` | Include retweets, only for `/twitter/user` | `0`/`1`/`true`/`false` | `true` |
| `forceWebApi` | Force Web API, only for `/twitter/user` and `/twitter/keyword` | `0`/`1`/`true`/`false` | `false` |
| `count` | `count` parameter passed to Twitter API, only for `/twitter/user` | Unspecified/Integer | Unspecified |
| `onlyMedia` | Only get tweets with media | `0`/`1`/`true`/`false` | `false` |
| `mediaNumber` | Number the medias | `0`/`1`/`true`/`false` | `false` |

### Authentication
Currently supported authentication methods:

- `TWITTER_AUTH_TOKEN` (recommended): configure a comma-separated list of logged-in Twitter Web `auth_token` cookies.
- `TWITTER_CONSUMER_KEY` and `TWITTER_CONSUMER_SECRET`: configure Twitter pay-per-use developer API keys and secrets.
- Optional: `TWITTER_ACCESS_TOKEN` and `TWITTER_ACCESS_SECRET`: provide user-authenticated developer API access.

### Deprecated Authentication
`TWITTER_USERNAME`, `TWITTER_PASSWORD`, and `TWITTER_AUTHENTICATION_SECRET` are no longer usable since Twitter mobile client attestation was implemented in October 2025.
"""


def render_features(features: Any) -> str:
    if not features:
        return "_None_"
    if isinstance(features, dict):
        lines = []
        for key, value in features.items():
            lines.append(f"- `{key}`: {clean_text(value)}")
        return "\n".join(lines)
    return clean_text(features)


def render_parameters(parameters: Any) -> str:
    if not parameters:
        return "_None_"
    if isinstance(parameters, dict):
        lines = []
        for key, value in parameters.items():
            lines.append(f"- `{key}`: {clean_text(value)}")
        return "\n".join(lines)
    return clean_text(parameters)


def render_radar(radar_rules: Any) -> str:
    if not radar_rules:
        return "_None_"
    rendered = []
    for index, rule in enumerate(radar_rules, start=1):
        rendered.append(f"### Rule {index}")
        if not isinstance(rule, dict):
            rendered.append(clean_text(rule))
            continue
        for key, value in rule.items():
            if isinstance(value, list):
                rendered.append(f"- `{key}`:")
                for item in value:
                    rendered.append(f"  - `{clean_text(item)}`")
            else:
                rendered.append(f"- `{key}`: `{clean_text(value)}`")
    return "\n".join(rendered)


def render_route_markdown(
    namespace: str,
    namespace_payload: dict[str, Any],
    route_path: str,
    route_payload: dict[str, Any],
) -> str:
    namespace_name = clean_text(namespace_payload.get("name")) or namespace
    route_name = clean_text(route_payload.get("name")) or route_path
    title = f"{namespace_name} - {route_name}"
    categories = (
        route_payload.get("categories") or namespace_payload.get("categories") or []
    )
    maintainers = route_payload.get("maintainers") or []
    description = clean_text(route_payload.get("description")) or "_None_"
    example = clean_text(route_payload.get("example")) or "_None_"
    url = (
        clean_text(route_payload.get("url") or namespace_payload.get("url")) or "_None_"
    )
    location = clean_text(route_payload.get("location")) or "_None_"
    module = clean_text(route_payload.get("module")) or "_None_"
    lang = clean_text(namespace_payload.get("lang")) or "_None_"
    coverage = "`index-only`"
    route_notes = ""
    if namespace == "twitter":
        coverage = "`partial`"
        route_notes = "\n".join([TWITTER_ROUTE_NOTES, ""])

    return "\n".join(
        [
            f"# {title}",
            "",
            "## Coverage",
            coverage,
            "",
            "## Route",
            f"- Namespace: `{namespace}`",
            f"- Namespace Name: `{namespace_name}`",
            f"- Route Path: `{route_path}`",
            f"- Route Name: `{route_name}`",
            f"- Example: `{example}`",
            f"- URL: `{url}`",
            f"- Language: `{lang}`",
            f"- Categories: `{', '.join(categories) if categories else 'None'}`",
            f"- Maintainers: `{', '.join(maintainers) if maintainers else 'None'}`",
            f"- Source Location: `{location}`",
            f"- Source Module: `{module}`",
            "",
            "## Description",
            description,
            "",
            "## Parameters",
            render_parameters(route_payload.get("parameters")),
            "",
            route_notes,
            "## Features",
            render_features(route_payload.get("features")),
            "",
            "## Radar",
            render_radar(route_payload.get("radar")),
            "",
            "## Raw JSON",
            "```json",
            dump_json(route_payload).rstrip(),
            "```",
            "",
        ]
    )


def iter_documents(routes_payload: dict[str, Any]) -> list[Document]:
    documents: list[Document] = []
    used_paths: set[str] = set()

    for namespace in sorted(routes_payload):
        namespace_payload = routes_payload[namespace]
        namespace_name = clean_text(namespace_payload.get("name")) or namespace
        routes = namespace_payload.get("routes") or {}
        for route_path in sorted(routes):
            route_payload = routes[route_path]
            route_name = clean_text(route_payload.get("name")) or route_path
            slug = slugify(route_path)
            relative_path = f"docs/routes/{slugify(namespace)}/{slug}.md"
            if relative_path in used_paths:
                relative_path = (
                    f"docs/routes/{slugify(namespace)}/{slug}-{len(used_paths)}.md"
                )
            used_paths.add(relative_path)
            title = f"{namespace_name} - {route_name}"
            markdown = render_route_markdown(
                namespace, namespace_payload, route_path, route_payload
            )
            documents.append(
                Document(
                    relative_path=relative_path,
                    title=title,
                    markdown=markdown,
                    namespace=namespace,
                    route_path=route_path,
                    namespace_name=namespace_name,
                    categories=list(
                        route_payload.get("categories")
                        or namespace_payload.get("categories")
                        or []
                    ),
                    maintainers=list(route_payload.get("maintainers") or []),
                )
            )

    return documents


def build_namespace_index_markdown(
    namespace: str, namespace_payload: dict[str, Any], documents: list[Document]
) -> str:
    namespace_name = clean_text(namespace_payload.get("name")) or namespace
    url = clean_text(namespace_payload.get("url")) or "_None_"
    lang = clean_text(namespace_payload.get("lang")) or "_None_"
    aliases = infer_aliases(namespace, namespace_name, url)
    lines = [
        f"# {namespace_name} Route Index",
        "",
        "## Namespace",
        f"- Namespace: `{namespace}`",
        f"- Display Name: `{namespace_name}`",
        f"- URL: `{url}`",
        f"- Language: `{lang}`",
        f"- Aliases: `{', '.join(aliases)}`",
        f"- Route Count: `{len(documents)}`",
        "",
        "## Routes",
        "",
    ]
    for document in documents:
        title = (
            document.title.split(" - ", 1)[1]
            if " - " in document.title
            else document.title
        )
        route_slug = Path(document.relative_path).name
        lines.extend(
            [
                f"### {title}",
                f"- Route ID: `{document.namespace}:{document.route_path}`",
                f"- Route Path: `{document.route_path}`",
                f"- File: `{document.relative_path}`",
                f"- File Name: `{route_slug}`",
                f"- Categories: `{', '.join(document.categories) if document.categories else 'None'}`",
                f"- Maintainers: `{', '.join(document.maintainers) if document.maintainers else 'None'}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_namespaces_index_markdown(
    routes_payload: dict[str, Any], documents: list[Document]
) -> str:
    grouped: dict[str, list[Document]] = {}
    for document in documents:
        grouped.setdefault(document.namespace, []).append(document)

    lines = [
        "# Route Namespace Index",
        "",
        "Use this file to select the target namespace before opening route documents.",
        "",
    ]

    for namespace in sorted(grouped):
        namespace_payload = routes_payload[namespace]
        namespace_name = clean_text(namespace_payload.get("name")) or namespace
        url = clean_text(namespace_payload.get("url")) or "_None_"
        aliases = infer_aliases(namespace, namespace_name, url)
        lines.extend(
            [
                f"## {namespace_name}",
                f"- Namespace: `{namespace}`",
                f"- Aliases: `{', '.join(aliases)}`",
                f"- Route Count: `{len(grouped[namespace])}`",
                f"- Index File: `index/{slugify(namespace)}.md`",
                "",
            ]
        )

    return "\n".join(lines)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def first_markdown_heading(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def build_metadata(
    output_dir: Path,
    *,
    source_repo: str,
    source_revision: str,
    generated_at: str,
    route_count: int,
    namespace_count: int,
) -> dict[str, Any]:
    files = []
    for path in sorted(output_dir.rglob("*.md")):
        relative_path = path.relative_to(output_dir).as_posix()
        if not (
            relative_path == "index/namespaces.md"
            or (
                relative_path.startswith("index/")
                and "/" not in relative_path[len("index/") :]
            )
            or relative_path.startswith("docs/routes/")
        ):
            continue
        content = path.read_text(encoding="utf-8")
        kind = "route"
        if relative_path == "index/namespaces.md":
            kind = "namespace-root-index"
        elif relative_path.startswith("index/"):
            kind = "namespace-index"
        files.append(
            {
                "path": relative_path,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "size": len(content.encode("utf-8")),
                "title": first_markdown_heading(content),
                "kind": kind,
            }
        )

    return {
        "version": source_revision,
        "commit": source_revision,
        "generated_at": generated_at,
        "source_repo": source_repo,
        "route_count": route_count,
        "namespace_count": namespace_count,
        "files": files,
    }


def build_root_readme(
    documents: list[Document], source_repo: str, source_revision: str, generated_at: str
) -> str:
    namespace_count = len({document.namespace for document in documents})
    category_count = len(
        {category for document in documents for category in document.categories}
    )
    return (
        "\n".join(
            [
                "# RSSHub Routes Knowledgebase",
                "",
                "This branch is generated automatically from RSSHub official route metadata.",
                "",
                "## Summary",
                f"- Generated At: `{generated_at}`",
                f"- Source Repo: `{source_repo}`",
                f"- Source Revision: `{source_revision}`",
                f"- Namespaces: `{namespace_count}`",
                f"- Route Documents: `{len(documents)}`",
                f"- Categories: `{category_count}`",
                "",
                "## Files",
                "- `index/namespaces.md`: top-level namespace directory.",
                "- `index/<namespace>.md`: per-namespace route directory.",
                "- `docs/routes/<namespace>/*.md`: per-route markdown documents.",
                "",
                "## Suggested Lookup Flow",
                "1. Read `index/namespaces.md` to identify the target namespace.",
                "2. Read `index/<namespace>.md` to choose the best matching route file.",
                "3. Read the selected `docs/routes/...` file for the full route knowledge.",
                "",
            ]
        )
        + "\n"
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    routes_payload = json.loads(input_path.read_text(encoding="utf-8"))
    documents = iter_documents(routes_payload)
    generated_at = utc_now()

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for document in documents:
        target_path = output_dir / document.relative_path
        write_text(target_path, document.markdown)

    grouped: dict[str, list[Document]] = {}
    for document in documents:
        grouped.setdefault(document.namespace, []).append(document)

    for namespace, namespace_documents in grouped.items():
        namespace_payload = routes_payload[namespace]
        index_markdown = build_namespace_index_markdown(
            namespace, namespace_payload, namespace_documents
        )
        write_text(output_dir / "index" / f"{slugify(namespace)}.md", index_markdown)

    namespaces_index = build_namespaces_index_markdown(routes_payload, documents)
    write_text(output_dir / "index" / "namespaces.md", namespaces_index)

    root_readme = build_root_readme(
        documents, args.source_repo, args.source_revision, generated_at
    )
    write_text(output_dir / "README.md", root_readme)
    metadata = build_metadata(
        output_dir,
        source_repo=args.source_repo,
        source_revision=args.source_revision,
        generated_at=generated_at,
        route_count=len(documents),
        namespace_count=len(routes_payload),
    )
    write_text(output_dir / "metadata.json", dump_json(metadata))

    print(
        json.dumps(
            {
                "generated_at": generated_at,
                "route_count": len(documents),
                "namespace_count": len(routes_payload),
                "output_dir": str(output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
