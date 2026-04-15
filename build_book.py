from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
ORDERED_RE = re.compile(r"^\d+\.\s+(.*)$")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
CHAPTER_RE = re.compile(r"(\d+)")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return slug.strip("-") or "section"


def apply_inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = INLINE_CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = ITALIC_RE.sub(r"<em>\1</em>", escaped)
    return escaped


def apply_inline_markup_pdf(text: str) -> str:
  escaped = html.escape(text)
  escaped = INLINE_CODE_RE.sub(r'<font face="Courier">\1</font>', escaped)
  escaped = BOLD_RE.sub(r"<b>\1</b>", escaped)
  escaped = ITALIC_RE.sub(r"<i>\1</i>", escaped)
  return escaped


def markdown_to_html(markdown: str, anchor_prefix: str = "") -> tuple[str, list[tuple[int, str, str]]]:
    lines = markdown.splitlines()
    blocks: list[str] = []
    headings: list[tuple[int, str, str]] = []
    paragraph: list[str] = []
    in_ul = False
    in_ol = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph).strip()
            if text:
                blocks.append(f"<p>{apply_inline_markup(text)}</p>")
            paragraph = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            blocks.append("</ul>")
            in_ul = False
        if in_ol:
            blocks.append("</ol>")
            in_ol = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            close_lists()
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            flush_paragraph()
            close_lists()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            anchor = slugify(title)
            if anchor_prefix:
              anchor = f"{anchor_prefix}-{anchor}"
            headings.append((level, title, anchor))
            blocks.append(
                f"<h{level} id=\"{anchor}\">{apply_inline_markup(title)}</h{level}>"
            )
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            if in_ol:
                blocks.append("</ol>")
                in_ol = False
            if not in_ul:
                blocks.append("<ul>")
                in_ul = True
            blocks.append(f"<li>{apply_inline_markup(stripped[2:].strip())}</li>")
            continue

        ordered_match = ORDERED_RE.match(stripped)
        if ordered_match:
            flush_paragraph()
            if in_ul:
                blocks.append("</ul>")
                in_ul = False
            if not in_ol:
                blocks.append("<ol>")
                in_ol = True
            blocks.append(f"<li>{apply_inline_markup(ordered_match.group(1).strip())}</li>")
            continue

        close_lists()
        paragraph.append(stripped)

    flush_paragraph()
    close_lists()
    return "\n".join(blocks), headings


def chapter_sort_key(path: Path) -> tuple[int, str]:
    if path.name == "conclusion.md":
        return 10**9, path.name

    match = CHAPTER_RE.search(path.stem)
    number = int(match.group(1)) if match else 10**9
    return number, path.name


def discover_chapters(pattern: str, include_conclusion: bool = True) -> list[Path]:
    files = [path for path in Path.cwd().glob(pattern) if path.is_file()]
    if include_conclusion:
        conclusion_path = Path.cwd() / "conclusion.md"
        if conclusion_path.is_file() and conclusion_path not in files:
            files.append(conclusion_path)
    return sorted(files, key=chapter_sort_key)


def extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def build_pdf_styles() -> dict[str, ParagraphStyle]:
  base = getSampleStyleSheet()
  styles: dict[str, ParagraphStyle] = {
    "CoverEyebrow": ParagraphStyle(
      "CoverEyebrow",
      parent=base["Normal"],
      fontName="Helvetica-Bold",
      fontSize=9,
      leading=11,
      alignment=TA_CENTER,
      textColor=colors.HexColor("#8c3d2e"),
      spaceAfter=8,
    ),
    "CoverTitle": ParagraphStyle(
      "CoverTitle",
      parent=base["Title"],
      fontName="Helvetica-Bold",
      fontSize=21,
      leading=26,
      alignment=TA_CENTER,
      textColor=colors.HexColor("#22201c"),
      spaceAfter=12,
    ),
    "CoverSubtitle": ParagraphStyle(
      "CoverSubtitle",
      parent=base["Normal"],
      fontSize=11,
      leading=15,
      alignment=TA_CENTER,
      textColor=colors.HexColor("#6a6258"),
      spaceAfter=14,
    ),
    "CoverAuthor": ParagraphStyle(
      "CoverAuthor",
      parent=base["Normal"],
      fontName="Helvetica-Bold",
      fontSize=10,
      leading=12,
      alignment=TA_CENTER,
      textColor=colors.HexColor("#4a362c"),
      spaceAfter=8,
    ),
    "Credits": ParagraphStyle(
      "Credits",
      parent=base["Normal"],
      fontSize=8.5,
      leading=11,
      alignment=TA_CENTER,
      textColor=colors.HexColor("#6a6258"),
      spaceAfter=3,
    ),
    "ContentsHeading": ParagraphStyle(
      "ContentsHeading",
      parent=base["Heading2"],
      fontName="Helvetica-Bold",
      fontSize=14,
      leading=18,
      textColor=colors.HexColor("#2d251f"),
      spaceAfter=10,
    ),
    "ContentsItem": ParagraphStyle(
      "ContentsItem",
      parent=base["Normal"],
      fontSize=10,
      leading=13,
      leftIndent=8,
      textColor=colors.HexColor("#4a362c"),
      spaceAfter=4,
    ),
    "ChapterKicker": ParagraphStyle(
      "ChapterKicker",
      parent=base["Normal"],
      fontName="Helvetica-Bold",
      fontSize=9,
      leading=11,
      textColor=colors.HexColor("#8c3d2e"),
      spaceAfter=8,
    ),
    "Body": ParagraphStyle(
      "Body",
      parent=base["BodyText"],
      fontName="Times-Roman",
      fontSize=9.5,
      leading=13,
      textColor=colors.HexColor("#22201c"),
      spaceAfter=6,
    ),
    "ListBody": ParagraphStyle(
      "ListBody",
      parent=base["BodyText"],
      fontName="Times-Roman",
      fontSize=9.5,
      leading=13,
      textColor=colors.HexColor("#22201c"),
    ),
    "Heading1": ParagraphStyle(
      "Heading1",
      parent=base["Heading1"],
      fontName="Helvetica-Bold",
      fontSize=17,
      leading=21,
      textColor=colors.HexColor("#2d251f"),
      spaceAfter=10,
    ),
    "Heading2": ParagraphStyle(
      "Heading2",
      parent=base["Heading2"],
      fontName="Helvetica-Bold",
      fontSize=13,
      leading=16,
      textColor=colors.HexColor("#2d251f"),
      spaceBefore=6,
      spaceAfter=6,
    ),
    "Heading3": ParagraphStyle(
      "Heading3",
      parent=base["Heading3"],
      fontName="Helvetica-Bold",
      fontSize=11,
      leading=14,
      textColor=colors.HexColor("#2d251f"),
      spaceBefore=5,
      spaceAfter=5,
    ),
  }
  return styles


def markdown_to_pdf_story(markdown: str, styles: dict[str, ParagraphStyle]) -> list:
  story: list = []
  lines = markdown.splitlines()
  paragraph: list[str] = []
  list_items: list[str] = []
  list_type: str | None = None

  def flush_paragraph() -> None:
    nonlocal paragraph
    if paragraph:
      text = " ".join(part.strip() for part in paragraph).strip()
      if text:
        story.append(Paragraph(apply_inline_markup_pdf(text), styles["Body"]))
      paragraph = []

  def flush_list() -> None:
    nonlocal list_items, list_type
    if not list_items:
      return

    flowable_items = [
      ListItem(Paragraph(apply_inline_markup_pdf(item), styles["ListBody"]))
      for item in list_items
    ]
    bullet_type = "1" if list_type == "ol" else "bullet"
    story.append(
      ListFlowable(
        flowable_items,
        bulletType=bullet_type,
        leftIndent=18,
        bulletFontName="Helvetica",
      )
    )
    story.append(Spacer(1, 4))
    list_items = []
    list_type = None

  for raw_line in lines:
    stripped = raw_line.strip()

    if not stripped:
      flush_paragraph()
      flush_list()
      continue

    heading_match = HEADING_RE.match(stripped)
    if heading_match:
      flush_paragraph()
      flush_list()
      level = len(heading_match.group(1))
      title = heading_match.group(2).strip()
      style_name = f"Heading{min(level, 3)}"
      story.append(Paragraph(apply_inline_markup_pdf(title), styles[style_name]))
      continue

    if stripped.startswith("- "):
      flush_paragraph()
      if list_type not in (None, "ul"):
        flush_list()
      list_type = "ul"
      list_items.append(stripped[2:].strip())
      continue

    ordered_match = ORDERED_RE.match(stripped)
    if ordered_match:
      flush_paragraph()
      if list_type not in (None, "ol"):
        flush_list()
      list_type = "ol"
      list_items.append(ordered_match.group(1).strip())
      continue

    flush_list()
    paragraph.append(stripped)

  flush_paragraph()
  flush_list()
  return story


def build_pdf(
  chapter_paths: list[Path],
  output_path: Path,
  title: str,
  subtitle: str,
  author: str,
) -> None:
  styles = build_pdf_styles()
  story: list = []

  story.append(Spacer(1, 30 * mm))
  story.append(Paragraph("Back2Basics", styles["CoverEyebrow"]))
  story.append(Paragraph(html.escape(title), styles["CoverTitle"]))
  story.append(Paragraph(html.escape(subtitle), styles["CoverSubtitle"]))
  story.append(Paragraph(html.escape(author), styles["CoverAuthor"]))
  story.append(Spacer(1, 12 * mm))
  story.append(
    Paragraph(
      "Credits: source material inspired by the Sismique podcast on knowledge",
      styles["Credits"],
    )
  )
  story.append(Paragraph("Compiled with GPT-5.4 &amp; Copilot", styles["Credits"]))
  story.append(Paragraph("Prepared &amp; curated by Vivien Clauzon", styles["Credits"]))
  story.append(PageBreak())

  story.append(Paragraph("Contents", styles["ContentsHeading"]))
  for chapter_path in chapter_paths:
    markdown = chapter_path.read_text(encoding="utf-8")
    chapter_title = extract_title(markdown, chapter_path.stem)
    story.append(Paragraph(apply_inline_markup_pdf(chapter_title), styles["ContentsItem"]))
  story.append(PageBreak())

  for index, chapter_path in enumerate(chapter_paths, start=1):
    markdown = chapter_path.read_text(encoding="utf-8")
    story.append(Paragraph(f"Chapter {index}", styles["ChapterKicker"]))
    story.extend(markdown_to_pdf_story(markdown, styles))
    if index != len(chapter_paths):
      story.append(PageBreak())

  doc = SimpleDocTemplate(
    str(output_path),
    pagesize=A4,
    leftMargin=22 * mm,
    rightMargin=22 * mm,
    topMargin=18 * mm,
    bottomMargin=18 * mm,
    title=title,
    author=author,
  )
  doc.build(story)


def render_book(
    chapter_paths: list[Path],
    title: str,
    subtitle: str,
    author: str,
) -> str:
    toc_items: list[str] = []
    chapter_sections: list[str] = []

    for index, chapter_path in enumerate(chapter_paths, start=1):
        markdown = chapter_path.read_text(encoding="utf-8")
        chapter_title = extract_title(markdown, chapter_path.stem)
        chapter_anchor = f"chapter-{index}"
        body_html, headings = markdown_to_html(markdown, chapter_anchor)

        toc_items.append(
            f"<li><a href=\"#{chapter_anchor}\">{html.escape(chapter_title)}</a></li>"
        )

        local_toc = []
        for level, heading_title, anchor in headings:
            if level == 1:
                continue
            css_class = "toc-subsection" if level >= 3 else "toc-section"
            local_toc.append(
                f"<li class=\"{css_class}\"><a href=\"#{anchor}\">{html.escape(heading_title)}</a></li>"
            )

        local_toc_html = ""
        if local_toc:
            local_toc_html = (
                "<nav class=\"chapter-nav\"><h3>Chapter Outline</h3><ul>"
                + "".join(local_toc)
                + "</ul></nav>"
            )

        chapter_sections.append(
            "\n".join(
                [
                    f"<section class=\"chapter\" id=\"{chapter_anchor}\">",
                    f"<div class=\"chapter-kicker\">Chapter {index}</div>",
                    local_toc_html,
                    body_html,
                    "</section>",
                ]
            )
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --paper: #f7f1e7;
      --ink: #22201c;
      --muted: #6a6258;
      --accent: #8c3d2e;
      --accent-soft: #d7bba5;
      --line: #d9cfc1;
      --panel: rgba(255, 255, 255, 0.58);
      --shadow: 0 18px 50px rgba(60, 35, 20, 0.12);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(140, 61, 46, 0.09), transparent 30%),
        radial-gradient(circle at bottom right, rgba(169, 124, 80, 0.14), transparent 28%),
        linear-gradient(180deg, #efe4d4 0%, var(--paper) 100%);
      line-height: 1.75;
    }}

    .page {{
      width: min(980px, calc(100vw - 32px));
      margin: 24px auto 40px;
      background: var(--panel);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(120, 96, 72, 0.18);
      box-shadow: var(--shadow);
      border-radius: 24px;
      overflow: hidden;
    }}

    .cover {{
      padding: 72px 72px 56px;
      background:
        linear-gradient(135deg, rgba(140, 61, 46, 0.97), rgba(74, 43, 33, 0.96)),
        linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0));
      color: #f8f2ea;
      position: relative;
    }}

    .cover::after {{
      content: "";
      position: absolute;
      inset: auto 32px 28px 32px;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.7), transparent);
    }}

    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.22em;
      font-size: 0.78rem;
      opacity: 0.82;
      margin-bottom: 18px;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(2.6rem, 5vw, 4.4rem);
      line-height: 1.06;
      letter-spacing: -0.03em;
    }}

    .subtitle {{
      margin-top: 18px;
      max-width: 700px;
      font-size: 1.12rem;
      color: rgba(248, 242, 234, 0.86);
    }}

    .author {{
      margin-top: 28px;
      font-size: 0.95rem;
      color: rgba(248, 242, 234, 0.8);
    }}

    .toc {{
      padding: 36px 72px 14px;
      border-bottom: 1px solid var(--line);
    }}

    .toc h2,
    .chapter-nav h3 {{
      margin: 0 0 14px;
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
    }}

    .toc ul,
    .chapter-nav ul {{
      margin: 0;
      padding-left: 20px;
    }}

    .toc li,
    .chapter-nav li {{
      margin: 6px 0;
    }}

    .toc a,
    .chapter-nav a {{
      color: var(--accent);
      text-decoration: none;
    }}

    .toc a:hover,
    .chapter-nav a:hover {{
      text-decoration: underline;
    }}

    .content {{
      padding: 14px 72px 72px;
    }}

    .chapter {{
      padding-top: 30px;
      margin-top: 34px;
      border-top: 1px solid var(--line);
      page-break-before: always;
    }}

    .chapter:first-child {{
      border-top: none;
      margin-top: 0;
      padding-top: 10px;
      page-break-before: auto;
    }}

    .chapter-kicker {{
      display: inline-block;
      padding: 6px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: #58251d;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-bottom: 18px;
    }}

    h2, h3, h4, h5, h6 {{
      color: #2d251f;
      line-height: 1.18;
    }}

    h2 {{
      font-size: 1.65rem;
      margin-top: 1.9em;
      margin-bottom: 0.6em;
    }}

    h3 {{
      font-size: 1.22rem;
      margin-top: 1.4em;
      margin-bottom: 0.5em;
    }}

    p {{
      margin: 0.75em 0;
      font-size: 1.05rem;
    }}

    ul, ol {{
      margin: 0.8em 0 1em;
      padding-left: 24px;
    }}

    li {{
      margin: 0.35em 0;
    }}

    code {{
      background: rgba(70, 45, 30, 0.08);
      padding: 0.1em 0.35em;
      border-radius: 4px;
      font-size: 0.95em;
    }}

    .chapter-nav {{
      margin: 0 0 26px;
      padding: 18px 22px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 252, 247, 0.72);
    }}

    .toc-section {{
      list-style: disc;
    }}

    .toc-subsection {{
      list-style: circle;
      color: var(--muted);
    }}

    .footer {{
      padding: 18px 72px 34px;
      color: var(--muted);
      font-size: 0.92rem;
      border-top: 1px solid var(--line);
    }}

    @media print {{
      body {{
        background: white;
      }}

      .page {{
        width: auto;
        margin: 0;
        border: none;
        box-shadow: none;
        border-radius: 0;
        background: white;
      }}

      .cover {{
        min-height: 95vh;
      }}

      .chapter {{
        page-break-before: always;
      }}
    }}

    @media (max-width: 720px) {{
      .cover,
      .toc,
      .content,
      .footer {{
        padding-left: 24px;
        padding-right: 24px;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="cover">
      <div class="eyebrow">Back2Basics</div>
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">{html.escape(subtitle)}</p>
      <div class="author">{html.escape(author)}</div>
    </section>

    <section class="toc">
      <h2>Contents</h2>
      <ul>
        {''.join(toc_items)}
      </ul>
    </section>

    <section class="content">
      {''.join(chapter_sections)}
    </section>

    <footer class="footer">
      <div>Generated from Markdown chapters with build_book.py</div>
      <div>Credits: source material inspired by the <a href="https://www.sismique.fr/">Sismique podcast on knowledge</a></div>
      <div>Compiled with GPT-5.4 &amp; Copilot</div>
      <div>Prepared & curated by Vivien Clauzon</div>
    </footer>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a styled HTML book from chapter Markdown files."
    )
    parser.add_argument(
        "--pattern",
        default="chapitre*.md",
        help="Glob pattern used to collect chapter files. conclusion.md is included automatically when present.",
    )
    parser.add_argument(
        "--output",
        default="book.html",
        help="Output HTML file.",
    )
    parser.add_argument(
      "--pdf-output",
      default="book.pdf",
      help="Output PDF file.",
    )
    parser.add_argument(
        "--title",
        default="A Course on Knowledge and Epistemology",
        help="Book title.",
    )
    parser.add_argument(
        "--subtitle",
        default="From Antiquity to the Twentieth Century",
        help="Book subtitle.",
    )
    parser.add_argument(
        "--author",
        default="Prepared & curated by Vivien Clauzon from the Sismique podcast series on knowledge",
        help="Author line for the cover.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chapter_paths = discover_chapters(args.pattern)
    if not chapter_paths:
        raise SystemExit(f"No chapter files matched pattern: {args.pattern}")

    book_html = render_book(chapter_paths, args.title, args.subtitle, args.author)
    output_path = Path(args.output)
    output_path.write_text(book_html, encoding="utf-8")
    pdf_output_path = Path(args.pdf_output)
    build_pdf(chapter_paths, pdf_output_path, args.title, args.subtitle, args.author)
    print(f"Book written to {output_path}")
    print(f"Book written to {pdf_output_path}")


if __name__ == "__main__":
    main()