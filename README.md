# 科技快报自动化

这个仓库用于在 GitHub Actions 云端自动生成科技快报，并通过 Telegram bot 推送 PDF。

它不依赖你的电脑开机。只要代码已经推到 GitHub，并且 Actions secrets 配好，GitHub 会按计划在云端运行。

## 功能

- 每日科技快报：每天生成 `MM-DD-科技快报.pdf`
- 每周科技深度周报：每周六生成 `MM-DD-科技深度周报.pdf`
- 重大科技更新提醒：每 2 小时扫描一次，只有高分重大更新才推送 `MM-DD-HHMM-重大科技更新提醒.pdf`
- PDF 使用嵌入中文字体，避免 Telegram 打开空白
- 去重状态保存到 `data/state/seen-alerts.json`
- 生成文件保存到 `output/`

## 你需要配置的 GitHub Secrets

打开 GitHub 网页里的仓库：

`https://github.com/Michaelttt1005/Workflow`

然后进入：

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

添加两个 secret：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

值就是你的 Telegram bot token 和 chat id。

## GitHub Desktop 这个界面怎么操作

你截图里的界面是 GitHub Desktop。

因为我已经把仓库克隆到了本地：

```text
D:\Michael\Workflow
```

你现在应该这样做：

1. 在 GitHub Desktop 点右侧的 `Add an Existing Repository from your local drive...`
2. 选择这个文件夹：`D:\Michael\Workflow`
3. 点 `Add Repository`
4. 左侧应该会出现这个 repo，或者顶部仓库名会切到 `Workflow`
5. 左边 `Changes` 页面会看到我新增的文件
6. 在左下角 Summary 写：`Add tech brief automation`
7. 点 `Commit to main`
8. 点顶部或右上角的 `Push origin`

推送完成后，GitHub 网页上的仓库会出现 `.github/workflows`，然后 Actions 才能在云端运行。

如果你还没有用我克隆好的文件夹，也可以在截图里点 `Clone Michaelttt1005/Workflow`，但本机已经有 `D:\Michael\Workflow` 时，更推荐用 `Add an Existing Repository`。

## 手动测试 GitHub Actions

推送后，打开 GitHub 网页：

`Actions`

你会看到三个 workflow：

- `Daily Tech Brief`
- `Weekly Tech Brief`
- `Major Tech Update Radar`

点其中一个，再点右侧 `Run workflow`，就能手动触发一次。

如果 Telegram 收到 PDF，说明云端跑通了。

## 本地测试

在本地 PowerShell 中运行：

```powershell
cd D:\Michael\Workflow
python -m pip install -r requirements.txt
python scripts\run_brief.py --mode daily
```

这会生成 PDF，但不会发送 Telegram。

如果要本地发送，需要先设置环境变量：

```powershell
$env:TELEGRAM_BOT_TOKEN="你的 token"
$env:TELEGRAM_CHAT_ID="你的 chat id"
python scripts\run_brief.py --mode daily --send
```

## 修改时间

GitHub Actions 的 cron 使用 UTC。

现在的设置：

- 每日：`.github/workflows/daily-tech-brief.yml`
  - `0 14 * * *`
  - 当前夏令时约等于美国中部时间早上 9 点
- 周报：`.github/workflows/weekly-tech-brief.yml`
  - `0 14 * * 6`
  - 当前夏令时约等于周六早上 9 点
- 高频雷达：`.github/workflows/tech-alert.yml`
  - `0 */2 * * *`
  - 每 2 小时运行一次

冬令时如果你仍想严格保持早上 9 点，需要把 `14` 改成 `15`。

## 修改信息来源

主要来源在：

```text
config/sources.yaml
```

可以加 RSS、GitHub release 仓库、arXiv 分类和关键词。

## 注意

这个项目优先做低成本筛选：先抓标题、摘要、发布时间、链接，再用规则评分。它不会默认打开大量网页，也不会把整页 HTML 交给模型。

如果以后你想接入 DeepSeek 做更好的摘要，可以在这个项目里加一个可选的 LLM summarizer，但目前版本不需要任何 LLM API key，也能稳定生成和推送。

