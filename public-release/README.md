# 0→1 课程真题高频考点专项训练生成器

传入往年试卷合订本 PDF 与教材已学内容目录，程序会逐题拆解考点、对照目录剔除超纲与未学内容、由 Gemini 为留下的高频考点编写 0→1 专项讲义并本地导出中文 PDF，最后由 GPT 独立核验硬伤并产出一份给人看的修改建议文件。

## 工作流与模型分工

1. **建索引（本地 PyMuPDF + RapidOCR）**：逐页提取往年卷文字；对扫描页或文字极少的图片页自动补做本地 OCR，结果缓存到 `page-index/`。
2. **分批逐题拆考点（Gemini 4 Neon High / `agy`）**：按页分批逐题提炼大学课程考点（尽量拆细但不拆到高中及以下前置基础），自动跳过答案页和封面目录页，每完成一批立刻追加写入 `extracted_batches.jsonl`。
3. **全局归并与目录过滤（Gemini 4 Neon High / `agy`）**：合并同义考点、去重重复试卷后统计真实考频；严格对照教材已学目录（划掉、涂黑或未列入目录的考点全部丢弃），按 0→1 学习顺序排好并保存为 `filtered_topics.json`。
4. **逐考点 0→1 成文与本地导出（Gemini + Pandoc/Typst）**：
   - 逐个考点读取代表真题所在原卷页图精写讲义（追加写入 `generated_topics.jsonl`），把读者当作“有先修基础但未学过本门课”的新手，讲清识别信号、公式符号含义与适用条件、通用解题步骤、必配单点入门小例题以及往年真题实战示范（含原题配图裁剪）。
   - 汇总生成 `workbook.md`，并由 Python 直接调用 [pdf_export.py](pdf_export.py) 在本地排版导出 `workbook.pdf`。
5. **只读硬伤审校（GPT-6.2 Sol / `codex`）**：
   - 分组读取讲义、原卷页图与裁剪图做独立验算（追加写入 `review_batches.jsonl`），输出给人看的 `review_suggestions.md`，**绝不修改或回滚原讲义**。
   - 仅当能明确指出逻辑/数理/概念/公式/计算/原题或超纲硬伤，并给出错因与可验证依据时才提出建议；无明显硬伤则不提建议。

## 在 Windows 上运行

在项目目录打开 PowerShell，确保本机已完成 `agy` 与 `codex login` 登录，安装依赖后即可运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe course_workflow.py start --title "课程名" --paper "往年卷.pdf" --scope "目录1.png" "目录2.png"
```

- `--scope` 支持传入一张或多张目录图片，也兼容 `.md`、`.txt` 或 `.pdf` 目录文件。
- 常用可选参数：
  - `--batch-pages 6`：提炼考点时每批处理的 PDF 页数（默认 6）。
  - `--review-batch-size 2`：GPT 独立审校时每批处理的考点数（默认 2）。
  - `--skip-review`：仅生成 `workbook.md` 与 `workbook.pdf`，暂不运行 GPT 独立审校。
  - `--codex` / `--agy`：分别指定 `codex` 与 `agy` 可执行文件路径。

若某一步中断，直接从终端打印出的运行目录续跑（已完成写入 JSONL/JSON 的批次与考点会自动跳过）：

```powershell
.\.venv\Scripts\python.exe course_workflow.py resume "runs\course-实际运行目录"
```

## 运行目录产物说明

- `page-index/`：逐页试卷文字索引。
- `extracted_batches.jsonl`：分批提炼出的往年题与考点缓存（单文件追加写入）。
- `filtered_topics.json`：归并、统计考频并经教材目录过滤后的保留考点与丢弃记录。
- `generated_topics.jsonl`：逐考点生成的 0→1 讲义缓存（单文件追加写入）。
- `workbook.md` / `workbook.pdf`：最终生成的 0→1 高频考点专项训练讲义与 PDF。
- `review_batches.jsonl` / `review_suggestions.md`：GPT 只读审校缓存与最终给人看的硬伤修改建议（仅 Markdown）。
- `stage-logs/`：各阶段输入 JSON、Schema、响应及 CLI 运行日志。
