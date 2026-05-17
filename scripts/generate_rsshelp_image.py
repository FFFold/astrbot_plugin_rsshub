#!/usr/bin/env python3
"""Generate rsshelp HTML and PNG from command decorators/docstrings in main.py.

Primary path:
- Parse `main.py` command methods and docstrings with AST.
- Render `assets/help/rsshelp_template.html` via Jinja2.
- Try Playwright screenshot first.
- Fallback to a Pillow renderer if Playwright browser is unavailable.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "main.py"
TEMPLATE_DIR = ROOT / "assets" / "help"
TEMPLATE_NAME = "rsshelp_template.html"
OUTPUT_HTML = ROOT / "assets" / "help" / "rsshelp.html"
OUTPUT_PNG = ROOT / "assets" / "help" / "rsshelp.png"


@dataclass
class CommandDoc:
    command: str
    aliases: list[str]
    summary: str
    method_name: str
    group_name: str = ""
    group_aliases: list[str] | None = None


def _extract_aliases(node: ast.Call) -> list[str]:
    for kw in node.keywords:
        if kw.arg == "alias" and isinstance(kw.value, ast.Set):
            return [
                elt.value
                for elt in kw.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]
    return []


def parse_main_commands(main_py: Path) -> list[CommandDoc]:
    tree = ast.parse(main_py.read_text(encoding="utf-8"))
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RSSHubPlugin"
    )

    group_methods: dict[str, tuple[str, list[str]]] = {}
    for node in cls.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr == "command_group":
                    group_name = ""
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        group_name = str(dec.args[0].value)
                    group_alias = _extract_aliases(dec)
                    if group_name:
                        group_methods[node.name] = (group_name, group_alias)

    docs: list[CommandDoc] = []
    for node in cls.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue

        doc = ast.get_docstring(node) or ""
        summary = doc.strip().splitlines()[0] if doc.strip() else node.name

        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if dec.func.attr != "command":
                continue

            # Only include root commands: @filter.command("...")
            base = dec.func.value
            if not isinstance(base, ast.Name) or base.id != "filter":
                continue

            cmd = ""
            if dec.args and isinstance(dec.args[0], ast.Constant):
                cmd = str(dec.args[0].value)
            aliases = _extract_aliases(dec)
            docs.append(
                CommandDoc(
                    command=cmd,
                    aliases=aliases,
                    summary=summary,
                    method_name=node.name,
                )
            )

        # parse group subcommand decorators: @group_method.command("set", ...)
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if dec.func.attr != "command":
                continue
            base = dec.func.value
            if not isinstance(base, ast.Name):
                continue
            group_meta = group_methods.get(base.id)
            if not group_meta:
                continue
            sub_cmd = ""
            if dec.args and isinstance(dec.args[0], ast.Constant):
                sub_cmd = str(dec.args[0].value)
            aliases = _extract_aliases(dec)
            group_name, group_aliases = group_meta
            docs.append(
                CommandDoc(
                    command=f"{group_name} {sub_cmd}",
                    aliases=aliases,
                    summary=summary,
                    method_name=node.name,
                    group_name=group_name,
                    group_aliases=group_aliases,
                )
            )

    # Remove duplicates (plain command decorators on grouped methods should not occur,
    # but keep this robust for future edits)
    uniq: dict[tuple[str, str], CommandDoc] = {}
    for d in docs:
        uniq[(d.method_name, d.command)] = d
    return list(uniq.values())


def _group_commands(cmds: list[CommandDoc]) -> list[dict]:
    groups = {
        "订阅管理": [],
        "推送任务": [],
        "配置命令": [],
        "数据导入导出": [],
        "管理员": [],
    }
    for c in sorted(cmds, key=lambda x: x.command):
        if c.command.startswith("sub_status") or c.command.startswith("sub_stop"):
            groups["推送任务"].append(c)
        elif c.command.startswith("sub_profile") or c.command.startswith("sub_session"):
            groups["配置命令"].append(c)
        elif c.command.startswith("sub_export") or c.command.startswith("sub_import"):
            groups["数据导入导出"].append(c)
        elif c.command.startswith("sub_test"):
            groups["管理员"].append(c)
        else:
            groups["订阅管理"].append(c)
    return [
        {"title": k, "commands": v}
        for k, v in groups.items()
        if v
    ]


def render_html(commands: list[CommandDoc], output_html: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(TEMPLATE_NAME)
    grouped = _group_commands(commands)
    html = template.render(
        groups=grouped,
        total_commands=len(commands),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")


def render_png_with_playwright(html_path: Path, output_png: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1360, "height": 2000})
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            height = page.evaluate(
                "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
            )
            page.set_viewport_size({"width": 1360, "height": max(1000, int(height) + 20)})
            page.screenshot(path=str(output_png), full_page=True)
            browser.close()
        return True
    except Exception:
        return False


def _font(size: int) -> ImageFont.ImageFont:
    for name in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]:
        p = Path(name)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_png_fallback(commands: list[CommandDoc], output_png: Path) -> None:
    width = 1360
    padding = 40
    line_h = 28

    grouped = _group_commands(commands)
    row_heights: list[int] = []
    for g in grouped:
        h = 60
        for c in g["commands"]:
            h += 58 + (20 if c.aliases else 0)
        row_heights.append(h + 12)
    total_h = 120 + sum(row_heights) + 60
    total_h = max(total_h, 900)

    im = Image.new("RGB", (width, total_h), "#f4f7fb")
    draw = ImageDraw.Draw(im)
    font_title = _font(48)
    font_h2 = _font(30)
    font_cmd = _font(22)
    font_text = _font(18)
    font_meta = _font(16)

    draw.rectangle((20, 20, width - 20, total_h - 20), fill="#ffffff", outline="#dce6f2", width=2)
    draw.text((50, 45), "RSSHub 命令帮助", font=font_title, fill="#10243d")
    draw.text(
        (50, 105),
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  命令数：{len(commands)}",
        font=font_meta,
        fill="#5e738f",
    )

    y = 150
    box_w = width - padding * 2
    for idx, g in enumerate(grouped):
        x = padding
        box_y = y
        h = row_heights[idx]
        draw.rounded_rectangle(
            (x, box_y, x + box_w, box_y + h),
            radius=16,
            fill="#fcfeff",
            outline="#dce6f2",
            width=2,
        )
        draw.text((x + 16, box_y + 14), g["title"], font=font_h2, fill="#10243d")
        inner_y = box_y + 58
        for c in g["commands"]:
            draw.text((x + 16, inner_y), f"/{c.command}", font=font_cmd, fill="#0b76d1")
            inner_y += line_h
            draw.text((x + 16, inner_y), c.summary, font=font_text, fill="#10243d")
            inner_y += line_h
            if c.aliases:
                alias_text = "别名: " + " / ".join(c.aliases)
                draw.text((x + 16, inner_y), alias_text, font=font_meta, fill="#5e738f")
                inner_y += 24
        y += h + 16

    output_png.parent.mkdir(parents=True, exist_ok=True)
    im.save(output_png, format="PNG")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", default=str(MAIN_PY))
    parser.add_argument("--output-html", default=str(OUTPUT_HTML))
    parser.add_argument("--output-png", default=str(OUTPUT_PNG))
    args = parser.parse_args()

    main_py = Path(args.main)
    output_html = Path(args.output_html)
    output_png = Path(args.output_png)

    commands = parse_main_commands(main_py)
    render_html(commands, output_html)

    ok = render_png_with_playwright(output_html, output_png)
    if not ok:
        render_png_fallback(commands, output_png)

    print(f"generated html: {output_html}")
    print(f"generated png:  {output_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
