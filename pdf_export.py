"""Typeset the reviewed Markdown in the current run directory."""

from pathlib import Path

import pypandoc
import typst


def main():
    directory = Path.cwd()
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
    pending = directory / "workbook.pdf.tmp"
    pending.write_bytes(typst.compile(document.encode("utf-8"), root=directory))
    pending.replace(directory / "workbook.pdf")
    print("workbook.pdf")


if __name__ == "__main__":
    main()
