"""Typeset the workbook Markdown in a run directory into workbook.pdf."""

from pathlib import Path

import pypandoc
import typst


def export_pdf(directory):
    """Convert directory/workbook.md to Typst and compile directory/workbook.pdf."""
    directory = Path(directory).resolve()
    markdown = (directory / "workbook.md").read_text(encoding="utf-8")
    document = pypandoc.convert_text(
        markdown, "typst", format="markdown-raw_attribute-raw_html-raw_tex",
        extra_args=[
            "--standalone",
            "--variable=papersize=a4",
            "--variable=lang=zh",
            "--variable=mainfont=Microsoft YaHei",
        ],
    )
    try:
        pdf_bytes = typst.compile(document.encode("utf-8"), root=directory)
    except Exception:
        (directory / "workbook.typ").write_text(document, encoding="utf-8")
        raise
    pending = directory / "workbook.pdf.tmp"
    pending.write_bytes(pdf_bytes)
    output = directory / "workbook.pdf"
    pending.replace(output)
    return output


def main():
    """CLI entrypoint for typesetting workbook.md in the current working directory."""
    print(export_pdf(Path.cwd()).name)


if __name__ == "__main__":
    main()
