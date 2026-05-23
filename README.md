# AI 简报自动化

这个仓库用于在 GitHub Actions 云端生成 AI 相关简报，并可选择通过 Telegram bot 推送 PDF。

它不依赖你的电脑开机。只要代码已经推到 GitHub，并且 Actions secrets 配好，GitHub 会在云端运行；你的电脑息屏、关机都不影响。

## 现在这版到底有没有 AI

有。当前版本会先抓取 RSS / GitHub Release / arXiv 候选，然后强制调用 LLM 生成中文报告。

如果没有配置 `LLM_API_KEY`，脚本会直接失败，不会生成函数模板 PDF。

核心入口：

- `scripts/run_brief.py`：抓取候选、调用 LLM、校验、生成 PDF、可选发送 Telegram
- `src/tech_briefs/llm.py`：调用 OpenAI-compatible `chat/completions`
- `src/tech_briefs/reporting.py`：校验输出，拦截模板句、空链接、过短正文
- LLM 输出如果第一次没过校验，会把具体错误发回模型重写，最多重试 3 次；仍不合格才失败，避免把模板/短正文发出去。

## 功能

- 每日 AI 简报：生成 `MM-DD-AI简报.pdf`
- 每周 AI 深度周报：生成 `MM-DD-AI深度周报.pdf`
- 重大 AI 更新提醒：生成 `MM-DD-HHMM-重大AI更新提醒.pdf`
- 每条更新都包含“通俗解释”：用更直白的语言和具体例子说明这项新技术能做什么
- PDF 使用嵌入中文字体，避免 Telegram 打开空白
- 没有真实 LLM 输出或校验不通过时，拒绝发送模板附件

## 必须配置的 GitHub Secret

打开仓库：

`https://github.com/Michaelttt1005/Workflow`

进入：

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

至少添加：

```text
LLM_API_KEY
```

默认按 DeepSeek 的 OpenAI-compatible API 调用：

```text
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

`LLM_BASE_URL` 和 `LLM_MODEL` 可以放在 Actions Variables，也可以不配，使用默认值。

如果你想换 OpenAI 或其他兼容接口：

```text
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=你的模型名
```

## Telegram 推送

当前三个 GitHub workflow 已恢复自动发送 Telegram：定时触发和手动触发都会带 `--send`。

需要的 Telegram secret：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

发送命令形式是：

```powershell
python scripts\run_brief.py --mode daily --send
```

## 本地测试

```powershell
cd D:\Michael\Workflow
python -m pip install -r requirements.txt
$env:LLM_API_KEY="你的 key"
python scripts\run_brief.py --mode daily
```

这会生成 PDF，但不会发送 Telegram。

## GitHub Actions

现在三个 workflow 同时支持定时触发和手动触发：

- `Daily Tech Brief`
- `Weekly Tech Brief`
- `Major Tech Update Radar`

每次成功生成后，workflow 会上传 artifact：

- `daily-ai-brief`
- `weekly-ai-brief`
- `major-ai-update-alert`

每次成功生成后，也会保留 artifact 和仓库 `output/` 里的 PDF/JSON，方便回看。

当前 schedule 已恢复：

- Daily：每天 America/Chicago 09:00
- Weekly：每周六 America/Chicago 09:00
- Major alert：每 2 小时

这些都在 GitHub 云端运行；电脑息屏、关机都不影响。

## 信息来源

主要来源在：

```text
config/sources.yaml
```

可以加 RSS、GitHub release 仓库、arXiv 分类和关键词。
