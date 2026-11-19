# 真题专项训练生成器

用往年卷和本次考试范围生成中文训练册。脚本从试卷里选代表题，用考试范围筛掉超纲内容，再给每道例题配考点讲解、专项练习和解析。成品同时保存为 Markdown 和 PDF。

## 安装

在 Windows 上准备 Python 3.11 或更新版本。安装并登录 [Codex CLI](https://developers.openai.com/codex/cli/) 和 [Antigravity CLI](https://antigravity.google/docs/getting-started)。脚本默认从 PATH 查找 `codex.exe` 和 `agy.exe`。如果终端只提供 Codex 的 npm 启动脚本，用 `--codex` 指向原生 `codex.exe`。两个 CLI 的路径选项放在 `start` 或 `resume` 前。

在仓库目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 使用

### 从往年卷生成一门课的训练册

把往年试卷 PDF 和本次考试范围的目录图片放进 `inputs/`。目录上划掉或涂掉的小节会在筛题时排除。

```powershell
.\.venv\Scripts\python.exe course_workflow.py start --title "课程名" --paper "inputs\往年卷.pdf" --scope "inputs\考试范围1.png" "inputs\考试范围2.png"
```

Python 提取各页文字，并用本地 OCR 为扫描页建索引。Codex 按范围筛选候选题，核对原卷页和图示，再以例题为单位组织训练。每组保留试卷出处和范围小节，下面配 `n.1`、`n.2` 等小例题。默认每次选编最多 14 组代表题。

### 从一道题开始

仓库带了一道自编样题，可直接用来了解输入和输出格式：

```powershell
.\.venv\Scripts\python.exe run.py start examples/paper.md examples/scope.md --question 8
```

自己的单题可以用 Markdown、UTF-8 文本或 PDF。使用 PDF 时，用 `--page` 指定题目所在页。可用 `--textbook` 提供相关教材摘录。

## 成品与续跑

终端会打印本次运行目录，成品是其中的 `workbook.pdf`，校对时可以打开 `workbook.md`。课程模式还会保存 `selection.json`，用于在原卷里找到候选题。

运行中断后，用同一个脚本继续已有的运行目录。已保存的阶段结果会直接复用。

```powershell
.\.venv\Scripts\python.exe course_workflow.py resume "runs\实际课程运行目录"
```

## 模型和用量

默认使用 GPT-6.2 Sol High 和 Gemini 4 Neon High，可在 [`run.py`](run.py) 顶部调整。Codex 负责选题、生成和末审。Gemini 润色讲解与解析中的自然语言，再调用本地排版命令导出 PDF。完整课程模式通常启动 Codex 三次、Antigravity 两次，单题模式少一次选题调用。

项目直接调用本机已登录的官方 CLI。OCR 和 PDF 排版在本机完成，题目和考试范围会随请求发送给 Codex，待润色段落会发送给 Antigravity。请使用你有权提交的资料，并确认当前账号具备所选模型和非交互模式的访问权限。 [Antigravity 非交互模式](https://antigravity.google/docs/cli/headless/) · [Antigravity 使用说明](https://antigravity.google/docs/faq)

## 许可证

代码和自编示例采用 [MIT 许可证](LICENSE)。
