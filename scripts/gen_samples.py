"""Generate Chinese business sample documents into workspace/samples.

Covers the four main office formats so the parsing pipeline can be verified:
  docx (headings + table + embedded image) / xlsx (two sheets) /
  pptx (slides with bullets, table, notes) / pdf (multi-page with heading levels).

Run: runtime\\python\\python.exe scripts\\gen_samples.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "workspace" / "samples"
SAMPLES.mkdir(parents=True, exist_ok=True)


def make_diagram_png(path: Path) -> None:
    """Simple flow diagram used as an embedded image in the docx."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=420, height=180)
    boxes = [(30, 60, 130, 120, "采集"), (170, 60, 270, 120, "解析"), (310, 60, 410, 120, "入库")]
    for x0, y0, x1, y1, label in boxes:
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=(0.2, 0.4, 0.9), width=1.5)
        page.insert_textbox(fitz.Rect(x0, y0, x1, y1), label, fontsize=14,
                            fontname="china-s", align=1)
    for x in (132, 272):
        page.draw_line(fitz.Point(x, 90), fitz.Point(x + 36, 90), color=(0.2, 0.4, 0.9), width=1.5)
    page.get_pixmap(dpi=110).save(str(path))
    doc.close()


def gen_docx() -> Path:
    from docx import Document

    target = SAMPLES / "智能巡护系统产品手册.docx"
    diagram = SAMPLES / "_diagram.png"
    make_diagram_png(diagram)

    doc = Document()
    doc.add_heading("智能巡护系统产品手册", 0)
    doc.add_paragraph("本文档面向系统集成商与运维人员，介绍智能巡护系统的功能、安装与使用方法。")

    doc.add_heading("产品概述", 1)
    doc.add_paragraph("智能巡护系统是一套面向园区与厂区的无人值守巡护平台，由边缘采集终端、"
                      "巡护调度中心与移动应用三部分组成。")
    doc.add_heading("系统组成", 2)
    doc.add_paragraph("系统采用分层架构，数据流向如下图所示。")
    doc.add_picture(str(diagram), width=None)
    doc.add_paragraph("边缘采集终端负责信号采集与预处理；调度中心负责任务编排与告警联动。")

    doc.add_heading("安装指南", 1)
    doc.add_paragraph("安装前请确认现场供电与网络条件满足要求。")
    doc.add_heading("环境要求", 2)
    table = doc.add_table(rows=4, cols=2)
    table.style = "Table Grid"
    for row, (k, v) in zip(table.rows, [
            ("项目", "要求"),
            ("供电", "AC 220V ±10%，功耗 ≤ 150W"),
            ("网络", "千兆以太网，支持 PoE+"),
            ("工作温度", "-20℃ ~ 60℃")]):
        row.cells[0].text, row.cells[1].text = k, v
    doc.add_heading("安装步骤", 2)
    for step in ["固定设备支架并确认水平。",
                 "接入电源与网线，观察指示灯状态。",
                 "登录调度中心添加设备并下发巡护路线。"]:
        doc.add_paragraph(step, style="List Number")

    doc.add_heading("故障排除", 1)
    doc.add_paragraph("设备离线：检查网线与 PoE 供电；指示灯红色常亮表示供电异常。")
    doc.add_paragraph("无告警推送：确认调度中心的通知渠道配置正确，且设备处于在线状态。")

    doc.save(str(target))
    diagram.unlink()
    return target


def gen_xlsx() -> Path:
    from openpyxl import Workbook

    target = SAMPLES / "巡护任务月度统计.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "任务明细"
    ws.append(["日期", "巡护路线", "任务数", "完成数", "告警数", "负责人"])
    data = [
        ("2026-09-01", "东区环线", 12, 12, 1, "张伟"),
        ("2026-09-02", "西区环线", 10, 9, 0, "李娜"),
        ("2026-09-03", "北区专线", 8, 8, 2, "王强"),
        ("2026-09-04", "南区环线", 11, 10, 1, "赵敏"),
        ("2026-09-05", "东区环线", 12, 11, 0, "张伟"),
    ]
    for row in data:
        ws.append(row)
    ws2 = wb.create_sheet("月度汇总")
    ws2.append(["指标", "数值", "说明"])
    ws2.append(["任务总数", 53, "五条巡护路线合计"])
    ws2.append(["完成率", "94.3%", "完成任务 / 任务总数"])
    ws2.append(["告警总数", 4, "均已闭环处理"])
    wb.save(str(target))
    return target


def gen_pptx() -> Path:
    from pptx import Presentation
    from pptx.util import Inches, Pt

    target = SAMPLES / "三季度巡护方案评审.pptx"
    prs = Presentation()

    def add_slide(title, bullets, note=""):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = title
        body = slide.placeholders[1].text_frame
        body.text = bullets[0]
        for b in bullets[1:]:
            p = body.add_paragraph()
            p.text = b
        if note:
            slide.notes_slide.notes_text_frame.text = note
        return slide

    add_slide("三季度巡护方案评审", ["汇报人：运营部", "2026 年 10 月"], "开场强调评审目标。")
    add_slide("上季度运行情况", ["巡护任务完成率 94.3%，环比提升 2.1%。",
                                "告警平均响应时长 3.8 分钟，达标。",
                                "东区环线误报率偏高，需重点治理。"], "误报问题展开说明。")
    add_slide("三季度优化方案", ["调整东区巡护路线，避开施工区域。",
                              "升级边缘终端固件，优化告警阈值。",
                              "新增夜间无人巡护时段。"])
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "资源需求"
    table = slide.shapes.add_table(3, 3, Inches(1), Inches(1.5), Inches(8), Inches(1.6)).table
    for j, h in enumerate(["项目", "数量", "预算（万元）"]):
        table.cell(0, j).text = h
    for i, row in enumerate([("边缘采集终端", "6 台", "18.0"), ("巡护无人机", "2 架", "24.0")], 1):
        for j, v in enumerate(row):
            table.cell(i, j).text = v
    prs.save(str(target))
    return target


def gen_pdf() -> Path:
    import fitz

    target = SAMPLES / "园区出入管理制度.pdf"
    TITLE, H1, BODY = 20, 15, 10.5
    content = [
        (TITLE, "园区出入管理制度"),
        (BODY, "（2026 年修订版）"),
        (H1, "第一章 总则"),
        (BODY, "第一条 为加强园区出入管理，保障园区人员与财产安全，维护正常生产生活秩序，"
               "结合园区实际情况，制定本制度。"),
        (BODY, "第二条 本制度适用于所有进入园区的人员与车辆，包括员工、访客、施工人员及货运车辆。"),
        (H1, "第二章 人员出入管理"),
        (BODY, "第三条 员工凭有效工作证件刷卡入园；证件遗失应立即向综合管理部报失并补办。"),
        (BODY, "第四条 访客须由接待部门提前在访客系统登记，入园时出示有效身份证件，"
               "领取访客证后方可进入；离园时交回访客证。"),
        (BODY, "第五条 施工人员实行备案管理，由用工部门统一办理临时出入证，有效期不超过三十天。"),
        (H1, "第三章 车辆与物品管理"),
        (BODY, "第六条 机动车辆凭车辆通行证按指定通道进出，货运车辆须接受门岗查验。"),
        (BODY, "第七条 携带大件物品出园，须持综合管理部开具的物品放行单，门岗核对无误后放行。"),
        (H1, "第四章 附则"),
        (BODY, "第八条 违反本制度的，视情节给予批评教育直至禁止入园处理；构成违法的移交司法机关。"),
        (BODY, "第九条 本制度由综合管理部负责解释，自 2026 年 11 月 1 日起施行。"),
    ]
    doc = fitz.open()
    page, y = None, 0
    for size, text in content:
        height = 30 if size >= H1 else max(24, (len(text) // 40 + 1) * 15 + 10)
        if page is None or y + height > 780:
            page = doc.new_page()
            y = 60
        rc = page.insert_textbox(fitz.Rect(60, y, 535, y + height), text,
                                 fontsize=size, fontname="china-s")
        if rc < 0:  # text did not fit: retry with extra height
            page.insert_textbox(fitz.Rect(60, y, 535, y + height + 40), text,
                                fontsize=size, fontname="china-s")
            height += 40
        y += height + (14 if size >= H1 else 10)
    doc.save(str(target))
    doc.close()
    return target


if __name__ == "__main__":
    for fn in (gen_docx, gen_xlsx, gen_pptx, gen_pdf):
        path = fn()
        print(f"[OK] {path.name}  ({path.stat().st_size} bytes)")
