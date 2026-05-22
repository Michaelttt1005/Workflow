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

## 功能

- 每日 AI 简报：生成 `MM-DD-AI简报.pdf`
- 每周 AI 深度周报：生成 `MM-DD-AI深度周报.pdf`
- 重大 AI 更新提醒：生成 `MM-DD-HHMM-重大AI更新提醒.pdf`
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

当前我已经先停掉自动发送：workflow 只保留手动触发，命令里不带 `--send`。

确认样例没问题后，再恢复发送。需要的 secret：

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

现在三个 workflow 都只支持手动触发：

- `Daily Tech Brief`
- `Weekly Tech Brief`
- `Major Tech Update Radar`

等你确认样例后，可以恢复 schedule 和 `--send`，这样电脑息屏后也会在 GitHub 云端自动运行并发到手机。

## 信息来源

主要来源在：

```text
config/sources.yaml
```

可以加 RSS、GitHub release 仓库、arXiv 分类和关键词。
