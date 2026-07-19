from pathlib import Path
import re
from datetime import datetime

SOUL_PATH = Path(__file__).parent.parent / "soul.md"

def read_soul() -> str:
    if not SOUL_PATH.exists():
        return ""
    return SOUL_PATH.read_text().strip()


def get_section(content: str, section: str) -> str:
    m = re.search(
        rf"^## {re.escape(section)}\s*\n(.*?)(?=^## |\Z)",
        content, re.MULTILINE | re.DOTALL
    )
    return m.group(1).strip() if m else ""


def add_or_update_bullet(section_content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^- \*\*{re.escape(key)}\*\*: .*", re.MULTILINE)
    new_line = f"- **{key}**: {value}"
    if pattern.search(section_content):
        return pattern.sub(new_line, section_content)
    if section_content.endswith(":"):
        return f"{section_content}\n{new_line}"
    return f"{section_content}\n{new_line}"


def update_user_context(facts: dict):
    content = SOUL_PATH.read_text()
    section = get_section(content, "User Context")
    if not section:
        return
    for key, val in facts.items():
        section = add_or_update_bullet(section, key, val)
    content = _replace_section(content, "User Context", section)
    SOUL_PATH.write_text(content)


def append_log(summary: str):
    content = SOUL_PATH.read_text()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = content.splitlines()
    insert_at = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## Conversation Log"):
            insert_at = i + 2
            break
    if insert_at is None:
        return
    indent = "  "
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    new_lines = (
        lines[:insert_at]
        + [f"{indent}- [{ts}] {summary}"]
        + lines[insert_at:]
    )
    SOUL_PATH.write_text("\n".join(new_lines) + "\n")
    _trim_log()


def _trim_log(max_entries: int = 20):
    content = SOUL_PATH.read_text()
    lines = content.splitlines()
    in_log = False
    log_start = None
    log_end = None
    entries = []
    for i, line in enumerate(lines):
        if line.strip().startswith("## Conversation Log"):
            in_log = True
            log_start = i
            continue
        if in_log and line.startswith("## "):
            log_end = i
            break
        if in_log and line.strip().startswith("- ["):
            entries.append(i)
    if len(entries) <= max_entries:
        return
    keep = sorted(entries)[-max_entries:]
    remove = set(entries) - set(keep)
    new_lines = [l for i, l in enumerate(lines) if i not in remove]
    SOUL_PATH.write_text("\n".join(new_lines) + "\n")


def _replace_section(content: str, section: str, new_body: str) -> str:
    pattern = rf"(^## {re.escape(section)}\s*\n).*?(?=^## |\Z)"
    return re.sub(
        pattern,
        rf"\1{new_body}\n\n",
        content, count=0, flags=re.MULTILINE | re.DOTALL
    )
