"""Command line entry: init / import / notes / search / show / log / ops / topics.

Usage (from project root, with runtime python):
  python -m app.core.cli <command> [args]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# runtime must be fully offline: never let the embedding model hit the network
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from . import db, kb, paths, pipeline, retriever


def _lib(args) -> Path:
    return paths.LIBRARIES_DIR / args.library


def _connect(args):
    lib = _lib(args)
    if not lib.exists():
        sys.exit(f"知识库不存在: {lib}（先运行 init）")
    return db.connect(lib)


def cmd_init(args):
    lib = _lib(args)
    kb.create_library(lib, args.library, args.desc or "")
    print(f"知识库已创建: {lib}")


def cmd_import(args):
    conn = _connect(args)
    operator = args.by or db.current_operator(conn) or "系统"
    results = []
    for f in args.files:
        try:
            r = pipeline.import_file(_lib(args), f, operator, args.type, conn)
            results.append(r)
            mark = "（重新导入）" if r["replaced"] else ""
            print(f"[OK] {f} → {len(r['notes'])} 篇笔记{mark}")
            for n in r["notes"]:
                print(f"     - {n['note_id']}  {n['title']}  [{n['topic']}]")
        except Exception as e:  # keep batch going, report per file
            print(f"[FAIL] {f}: {e}")
    conn.close()
    if not results:
        sys.exit(1)


def cmd_notes(args):
    conn = _connect(args)
    rows = conn.execute(
        "SELECT note_id, title, topic, status, updated, updated_by FROM notes ORDER BY topic, note_id"
    ).fetchall()
    for r in rows:
        print(f"{r['note_id']:<36} [{r['topic']:<7}] {r['title']}  ({r['status']}, {r['updated']} by {r['updated_by']})")
    print(f"共 {len(rows)} 篇")


def cmd_search(args):
    conn = _connect(args)
    for r in retriever.search(conn, args.query, args.limit):
        print(f"{r['note_id']:<36} [{r['topic']:<7}] {r['title']}")
        print(f"    {r['snippet']}")


def cmd_show(args):
    conn = _connect(args)
    row = conn.execute("SELECT * FROM notes WHERE note_id=?", (args.note_id,)).fetchone()
    if row is None:
        sys.exit(f"笔记不存在: {args.note_id}")
    print(f"# {row['title']}  [{row['topic']}] {row['status']}")
    print(f"id={row['note_id']}  updated={row['updated']} by {row['updated_by']}  source={row['source_path']}")
    print("-" * 60)
    print(row["content"])


def cmd_log(args):
    conn = _connect(args)
    for r in db.list_changes(conn, operator=args.operator or "", limit=args.limit):
        print(f"{r['ts']}  {r['operator']:<6} {r['action']:<10} {r['target_type']:<8} {r['target_id']}")
        print(f"    {r['title']}  {r['detail']}")


def cmd_ops(args):
    conn = _connect(args)
    if args.add:
        db.ensure_operator(conn, args.add, args.role)
        conn.commit()
        print(f"已添加操作人: {args.add}")
    if args.use:
        db.set_current_operator(conn, args.use)
        conn.commit()
        print(f"当前操作人: {args.use}")
    for r in db.list_operators(conn):
        cur = "*" if r["name"] == db.current_operator(conn) else " "
        state = "" if r["active"] else "（停用）"
        print(f"{cur} {r['name']:<10} {r['role']:<6} {r['created']} {state}")


def cmd_topics(args):
    conn = _connect(args)
    lib = _lib(args)
    operator = args.by or db.current_operator(conn) or "系统"
    if args.new:
        path = pipeline.create_category(lib, args.parent or "", args.new, operator, conn)
        print(f"已新建分类: {path}")
    if args.rename:
        pipeline.rename_category(lib, args.rename[0], args.rename[1], operator, conn)
        print(f"分类 {args.rename[0]} 已重命名为「{args.rename[1]}」")
    if args.move is not None:
        target_parent = args.move[1] if len(args.move) > 1 else ""
        new_path = pipeline.move_category(lib, args.move[0], target_parent, operator, conn)
        print(f"分类已移动: {new_path}")
    if args.delete:
        pipeline.delete_category(lib, args.delete, operator, conn)
        print(f"已删除分类: {args.delete}")
    kb.ensure_categories(conn)
    counts = kb.category_counts(conn)
    for r in db.list_categories(conn):
        depth = r["path"].count("/")
        print(f"{'  ' * depth}{r['path']:<28} {r['name']:<14} {counts.get(r['path'], 0)} 篇")


def cmd_delete(args):
    conn = _connect(args)
    operator = args.by or db.current_operator(conn) or "系统"
    pipeline.delete_note(_lib(args), args.note_id, operator, conn)
    print(f"已删除: {args.note_id}")


def cmd_clear(args):
    conn = _connect(args)
    operator = args.by or db.current_operator(conn) or "系统"
    if not args.yes:
        sys.exit("危险操作：加 --yes 确认清空整个知识库（笔记/文档/分类/索引全部删除）")
    removed = pipeline.clear_library(_lib(args), operator, conn)
    print(f"知识库已清空：删除 {removed['notes']} 篇笔记、{removed['documents']} 个文档、"
          f"{removed['categories']} 个分类（操作人保留）")


def cmd_embed(args):
    from . import semantic
    conn = _connect(args)
    n = semantic.rebuild_embeddings(_lib(args), conn)
    if n:
        print(f"语义索引重建完成：{n} 个知识分块已嵌入（模型 {semantic.MODEL_NAME}）")
    else:
        sys.exit("嵌入失败：fastembed 未安装或模型缓存缺失（models\\fastembed_cache）")


def cmd_serve(args):
    from . import server
    lib = _lib(args)
    if not lib.exists():
        sys.exit(f"知识库不存在: {lib}（先运行 init）")
    server.serve(lib, host=args.host, port=args.port)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kb", description="知识库管理工具 CLI")
    ap.add_argument("--library", default=paths.DEFAULT_LIBRARY, help="知识库名称")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="创建知识库")
    p.add_argument("--desc", default="")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("import", help="导入文档")
    p.add_argument("files", nargs="+")
    p.add_argument("--type", default="misc",
                   help="分类路径，用 / 分层（不存在的层级会自动创建）")
    p.add_argument("--by", default="")
    p.set_defaults(fn=cmd_import)

    p = sub.add_parser("notes", help="列出笔记")
    p.set_defaults(fn=cmd_notes)

    p = sub.add_parser("search", help="检索")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("show", help="查看笔记")
    p.add_argument("note_id")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("delete", help="删除笔记")
    p.add_argument("note_id")
    p.add_argument("--by", default="")
    p.set_defaults(fn=cmd_delete)

    p = sub.add_parser("clear", help="清空知识库全部内容（保留操作人）")
    p.add_argument("--yes", action="store_true", help="确认执行清空")
    p.add_argument("--by", default="")
    p.set_defaults(fn=cmd_clear)

    p = sub.add_parser("log", help="变更记录")
    p.add_argument("--operator", default="")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("ops", help="操作人管理")
    p.add_argument("--add", default="")
    p.add_argument("--role", default="编辑")
    p.add_argument("--use", default="")
    p.set_defaults(fn=cmd_ops)

    p = sub.add_parser("topics", help="分类层级管理（可多级自定义）")
    p.add_argument("--new", metavar="NAME", help="新建分类（配合 --parent）")
    p.add_argument("--parent", metavar="PATH", default="", help="父分类路径，缺省为顶级")
    p.add_argument("--rename", nargs=2, metavar=("PATH", "NAME"), help="重命名分类显示名")
    p.add_argument("--move", nargs="+", metavar=("PATH", "PARENT"), help="移动分类到新的父级（缺省父级=顶级）")
    p.add_argument("--delete", metavar="PATH", help="删除空分类")
    p.add_argument("--by", default="")
    p.set_defaults(fn=cmd_topics)

    p = sub.add_parser("embed", help="重建语义向量索引（混合检索用）")
    p.set_defaults(fn=cmd_embed)

    p = sub.add_parser("serve", help="启动本地 REST 检索服务（供 AI 智能体调用）")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
