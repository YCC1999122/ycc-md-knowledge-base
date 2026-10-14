"""Knowledge base organization: library layout, note files, INDEX.md / llms.txt."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import db

# No preset categories: a library starts empty and users define their own
# tree (any depth) via GUI / CLI / import. Paths are slash-joined pinyin
# slugs, e.g. "manual" or "gong-si/bu-men"; display names live in the
# categories table.
STATUSES = {"draft": "草稿", "verified": "已核验", "archived": "已归档"}

LIB_SUBDIRS = ["topics", "sources", "assets", "chunks", "index", "exports"]


def create_library(lib_path: Path, name: str, description: str = "", parent: str = "") -> None:
    lib_path = Path(lib_path)
    for sub in LIB_SUBDIRS:
        (lib_path / sub).mkdir(parents=True, exist_ok=True)
    (lib_path / "kb.yaml").write_text(
        f"name: {name}\ndescription: {description}\nparent: {parent}\n", encoding="utf-8")
    conn = db.connect(lib_path)
    db.ensure_operator(conn, "系统", "系统")
    db.set_current_operator(conn, "系统")
    conn.commit()
    rebuild_indexes(lib_path, conn)
    conn.close()


def library_meta(lib_path: Path) -> dict:
    """kb.yaml -> {name, description, parent}. parent reserves kb-level
    hierarchy (a library may belong to another, e.g. a room's AC base under
    the room base); relation features build on this later."""
    meta = {"name": Path(lib_path).name, "description": "", "parent": ""}
    kb_yaml = Path(lib_path) / "kb.yaml"
    if kb_yaml.exists():
        for line in kb_yaml.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(name|description|parent):\s*(.*)$", line)
            if m:
                meta[m.group(1)] = m.group(2).strip()
    return meta


def library_name(lib_path: Path) -> str:
    return library_meta(lib_path)["name"]


def set_library_parent(lib_path: Path, parent: str) -> None:
    """Update the parent field in kb.yaml (kb-level hierarchy).

    Guards against self-reference and cycles (a descendant cannot become the
    parent of its ancestor).
    """
    from . import paths
    lib_path = Path(lib_path)
    meta = library_meta(lib_path)
    parent = parent.strip()
    if parent == meta["name"]:
        raise ValueError("父知识库不能是自身")
    if parent and not (paths.LIBRARIES_DIR / parent / "kb.yaml").exists():
        raise KeyError(f"父知识库不存在: {parent}")
    # walk the candidate's ancestor chain: meeting our own name means a cycle
    anc, seen = parent, set()
    while anc and anc not in seen:
        seen.add(anc)
        if anc == meta["name"]:
            raise ValueError("不能把子知识库设为自己的父级（会形成循环）")
        anc = library_meta(paths.LIBRARIES_DIR / anc)["parent"]
    (lib_path / "kb.yaml").write_text(
        f"name: {meta['name']}\ndescription: {meta['description']}\nparent: {parent}\n",
        encoding="utf-8")


def library_children(name: str) -> list[Path]:
    """Direct child libraries of `name` (by kb.yaml parent registration)."""
    from . import paths
    return [lib for lib in paths.list_libraries()
            if library_meta(lib)["parent"] == name]


# ---------------- naming ----------------

def slugify(title: str) -> str:
    """Chinese titles -> pinyin kebab-case; ASCII -> kebab-case."""
    try:
        from pypinyin import lazy_pinyin
        parts = lazy_pinyin(title)
        slug = "-".join(p for p in parts if re.match(r"^[a-z0-9]+$", p))
    except Exception:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "note"


def unique_note_id(conn, title: str) -> str:
    base = f"{db.today_compact()}-{slugify(title)}"
    note_id, n = base, 1
    while conn.execute("SELECT 1 FROM notes WHERE note_id=?", (note_id,)).fetchone():
        n += 1
        note_id = f"{base}-{n}"
    return note_id


# ---------------- category tree (user-defined, any depth) ----------------

def ensure_categories(conn) -> None:
    """Seed the categories table on first use of a legacy library.

    Only libraries that already have notes (from before the categories table
    existed) get one top-level node per distinct topic; new libraries stay
    empty — no presets.
    """
    if db.list_categories(conn):
        return
    rows = conn.execute("SELECT DISTINCT topic FROM notes ORDER BY topic").fetchall()
    for r in rows:
        top = r["topic"].split("/")[0]
        db.ensure_category(conn, top, top, "")
    conn.commit()


def ensure_category_path(conn, path: str, display_name: str | None = None) -> str:
    """Make sure every level of 'a/b/c' exists; returns the normalized path.

    Known segments are kept; new segments are slugified (display text defaults
    to the segment itself), with a -2/-3 suffix on slug collision.
    """
    parts = [p for p in str(path).replace("\\", "/").split("/") if p.strip()]
    cur = ""
    for i, seg in enumerate(parts):
        seg = seg.strip()
        cand = f"{cur}/{seg}" if cur else seg
        if db.get_category(conn, cand) is not None:
            cur = cand
            continue
        # typed display name? reuse the sibling with that exact name (if unique)
        sibs = [r for r in db.list_categories(conn) if r["parent"] == cur]
        match = [r for r in sibs if r["name"] == seg]
        if len(match) == 1:
            cur = match[0]["path"]
            continue
        name = display_name if (display_name and i == len(parts) - 1) else seg
        cur = unique_category_path(conn, cur, name)
        parent = cur.rsplit("/", 1)[0] if "/" in cur else ""
        db.ensure_category(conn, cur, name, parent)
    return cur


def unique_category_path(conn, parent: str, name: str) -> str:
    base = slugify(name)
    path = f"{parent}/{base}" if parent else base
    candidate, n = path, 1
    while db.get_category(conn, candidate) is not None:
        n += 1
        candidate = f"{path}-{n}"
    return candidate


def category_counts(conn) -> dict[str, int]:
    """Note count per category, including all descendants."""
    counts: dict[str, int] = {}
    rows = conn.execute("SELECT topic, COUNT(*) AS c FROM notes GROUP BY topic").fetchall()
    for r in rows:
        parts = r["topic"].split("/")
        for i in range(len(parts)):
            prefix = "/".join(parts[: i + 1])
            counts[prefix] = counts.get(prefix, 0) + r["c"]
    return counts


# ---------------- note file rendering ----------------

def _y(value: str) -> str:
    """YAML-safe scalar via JSON encoding (JSON is a YAML subset)."""
    return json.dumps(value, ensure_ascii=False)


def render_note_file(note: dict) -> str:
    tags = ", ".join(_y(t) for t in note.get("tags", []))
    fm = [
        "---",
        f"id: {note['note_id']}",
        f"title: {_y(note['title'])}",
        f"tags: [{tags}]",
        f"created: {note['created']}",
        f"updated: {note['updated']}",
        f"status: {note['status']}",
        f"summary: {_y(note.get('summary', ''))}",
        "source:",
        f"  file: {_y(note.get('source_path', ''))}",
        f"  type: {_y(note.get('ext', ''))}",
        "---",
        "",
    ]
    return "\n".join(fm) + note["content"].strip() + "\n"


def write_note_file(lib_path: Path, note: dict) -> str:
    rel = f"topics/{note['topic']}/{note['note_id'].split('-', 1)[1]}.md"
    target = Path(lib_path) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_note_file(note), encoding="utf-8")
    return rel


def make_summary(content: str, limit: int = 60) -> str:
    for line in content.splitlines():
        line = line.strip().strip(">").strip()
        if not line or line.startswith(("#", "!", "<!--", "|", "---")):
            continue
        return line[:limit] + ("…" if len(line) > limit else "")
    return ""


# ---------------- splitting a parsed document into atomic notes ----------------

def split_into_units(markdown: str, doc_title: str) -> list[dict]:
    """Split at H1 (if >=2) else at H2 (if >=2); otherwise a single note."""
    lines = markdown.splitlines()
    h1 = [i for i, l in enumerate(lines) if re.match(r"^#\s+", l)]
    h2 = [i for i, l in enumerate(lines) if re.match(r"^##\s+", l)]
    if len(h1) >= 2:
        level, idxs = 1, h1
    elif len(h2) >= 2:
        level, idxs = 2, h2
    else:
        return [{"title": doc_title, "content": _normalize_headings(markdown.strip(), 1)}]

    units = []
    preamble = lines[: idxs[0]]
    for j, start in enumerate(idxs):
        end = idxs[j + 1] if j + 1 < len(idxs) else len(lines)
        seg = lines[start:end]
        title = re.sub(r"^#+\s+", "", seg[0]).strip()
        body = _normalize_headings("\n".join(seg).strip(), level)
        if j == 0 and preamble:
            # keep the document preamble (e.g. doc title) as an H2 lead-in of the first unit
            demoted = []
            for l in preamble:
                m = re.match(r"^#{1,6}\s+(.*)", l)
                demoted.append("## " + m.group(1) if m else l)
            first, *rest = body.splitlines()
            body = "\n".join([first, "", *demoted, "", *rest])
        units.append({"title": title, "content": body})
    return [u for u in units if u["content"]]


def _normalize_headings(text: str, split_level: int) -> str:
    """Make the unit title H1 and shift deeper headings accordingly."""
    out = []
    for i, line in enumerate(text.splitlines()):
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            new_level = 1 if i == 0 else min(level - split_level + 1, 6)
            out.append("#" * max(new_level, 1) + " " + m.group(2))
        else:
            out.append(line)
    return "\n".join(out)


# ---------------- index files (INDEX.md / _topic.md / llms.txt) ----------------

def rebuild_indexes(lib_path: Path, conn) -> None:
    lib_path = Path(lib_path)
    name = library_name(lib_path)
    ensure_categories(conn)
    notes = conn.execute(
        "SELECT note_id, title, topic, summary, rel_path, tags, updated FROM notes ORDER BY topic, note_id"
    ).fetchall()

    topics: dict[str, list] = {}
    all_tags: set[str] = set()
    for n in notes:
        topics.setdefault(n["topic"], []).append(n)
        all_tags.update(json.loads(n["tags"] or "[]"))
    for t in topics:  # notes may point at categories missing from the table
        ensure_category_path(conn, t)

    cat_rows = db.list_categories(conn)
    counts = category_counts(conn)

    # INDEX.md — registry as a nested list (indent = depth)
    lines = [
        f"# 知识库索引 — {name}",
        "",
        "## 使用说明（给智能体）",
        "1. 先读本索引，凭描述挑选笔记，只打开需要的 1-3 篇。",
        "2. 引用信息时注明笔记 id。",
        "3. 语义检索可调用检索接口（REST `/search` 或 MCP `kb_search`）。",
        "",
        "## 受控标签",
        " ".join(f"`{t}`" for t in sorted(all_tags)) or "（暂无）",
        "",
        "## 登记簿（分类层级可自定义）",
    ]
    for r in cat_rows:
        path = r["path"]
        indent = "  " * path.count("/")
        lines.append(f"{indent}- **{r['name']}**（`{path}`，共 {counts.get(path, 0)} 篇）")
        for n in topics.get(path, []):
            lines.append(f"{indent}  - `{n['note_id']}` — **{n['title']}** — `{n['rel_path']}` — {n['summary'] or '（无摘要）'}")
    (lib_path / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # per-category MOC; drop stale ones
    topics_root = lib_path / "topics"
    if topics_root.exists():
        for moc in topics_root.rglob("_topic.md"):
            rel = moc.parent.relative_to(topics_root).as_posix()
            if rel not in {r["path"] for r in cat_rows}:
                moc.unlink()
    for r in cat_rows:
        path, label = r["path"], r["name"]
        own = topics.get(path, [])
        d = topics_root / path
        d.mkdir(parents=True, exist_ok=True)
        tlines = [f"# {label}（{path}）", "",
                  f"本分类收录 {len(own)} 篇笔记（含子分类共 {counts.get(path, 0)} 篇）。", ""]
        children = [c for c in cat_rows if c["parent"] == path]
        if children:
            tlines.append("## 子分类")
            for c in children:
                tlines.append(f"- [{c['name']}]({c['path'][len(path) + 1:]}/_topic.md)（{counts.get(c['path'], 0)} 篇）")
            tlines.append("")
        if own:
            tlines.append("## 笔记")
            for n in own:
                tlines.append(f"- [{n['title']}]({Path(n['rel_path']).name}) — {n['summary'] or '（无摘要）'}")
        (d / "_topic.md").write_text("\n".join(tlines) + "\n", encoding="utf-8")

    # llms.txt — tree of category links
    ll = [f"# {name}", "",
          f"> 标准化 Markdown 知识库：{len(notes)} 篇笔记，{len(cat_rows)} 个分类（层级可自定义）。先读 INDEX.md 挑选笔记。",
          "", "## 导航", "- [INDEX.md](INDEX.md)：使用说明、受控标签、全量登记簿", "", "## 分类"]
    for r in cat_rows:
        path = r["path"]
        ll.append(f"{'  ' * path.count('/')}- [{r['name']}](topics/{path}/_topic.md)：`{path}`，{counts.get(path, 0)} 篇")
    (lib_path / "llms.txt").write_text("\n".join(ll) + "\n", encoding="utf-8")
