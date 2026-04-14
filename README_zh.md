# AI 销售推介 Agent (AI Sales Outreach Agent)

这是一个基于 Python 的外呼销售智能代理（Agent），它可以自动调查公司网站，发现招聘信号和公开的联系邮箱，使用 OpenAI 生成个性化的推介邮件草稿，并通过 Inkbox 发送经过批准的邮件。

当前默认的安全测试模式：
- 生成的草稿可能包含发现的公司邮箱，例如 `hello@linear.app`
- 批准发送的邮件默认会发送到审核邮箱（例如 `chloezzx@bu.edu`）
- 只有在明确启用实时发送 (`--live`) 时，才会向真正的客户发送邮件

## 功能特点

- 调查公司网站并尝试检测招聘页面
- 从主页、联系我们、关于我们、团队和招聘页面中发现公开的联系邮箱
- 使用 OpenAI 生成个性化的推介邮件
- 如果 OpenAI 不可用，则回退到本地模板
- 直接在终端中打印调查摘要和邮件草稿
- 将草稿保存到 CSV 文件以供审核和批准
- 默认情况下，将批准的草稿发送到安全的审核邮箱
- 只有明确添加 `--live` 标志时，才会发送真正的推介邮件

## 技术栈

- Python 3.11+
- [Inkbox](https://github.com/inkbox-ai/inkbox) 用于邮件发送
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses/create?lang=python) 用于生成个性化草稿

## 安装与配置

```bash
# 创建并激活虚拟环境（需要 Python 3.11+ 版本。如果你默认是 3.9，请替换为 python3.11 -m venv .venv）
python -m venv .venv && source .venv/bin/activate

# 安装依赖
python -m pip install --upgrade pip
pip install inkbox openai
```

创建一个本地的 `.env` 文件：

```bash
cp .env.example .env
```

需要配置的环境变量说明：

```bash
INKBOX_API_KEY=ApiKey_your_key_here
INKBOX_IDENTITY_HANDLE=outreach-agent
INKBOX_IDENTITY_DISPLAY_NAME=Chloe
DEFAULT_SIGNATURE_NAME=Chloe
INKBOX_IDENTITY_EMAIL=hirepilot_outreach@inkboxmail.com
OUTREACH_REVIEW_EMAIL=chloezzx@bu.edu
ALLOW_LIVE_OUTREACH=false
OPENAI_API=sk_your_key_here
OPENAI_MODEL=gpt-5
OPENAI_BASE_URL=
OPENAI_PROXY_ENABLED=false
OPENAI_PROXY_URL=
```

- `DEFAULT_SIGNATURE_NAME` 控制生成草稿时邮件底部使用的落款名称。
- `OPENAI_BASE_URL` 留空时，默认走 OpenAI 官方地址。
- 如果你要接入 OpenAI 兼容接口，把 `OPENAI_BASE_URL` 填成对应地址，例如 `https://example.com/v1`。
- 如果要让 AI 请求走代理，设置 `OPENAI_PROXY_ENABLED=true`，并填写 `OPENAI_PROXY_URL=http://127.0.0.1:7890`。

## 快速开始

### 1. 初始化 Inkbox 身份

```bash
python main.py bootstrap
```

### 2. 根据公司名称和网站生成一份草稿

```bash
python main.py draft-company \
  --company-name "Linear" \
  --website-url "https://linear.app" \
  --notes "Check if their hiring workflow could benefit from Hirepilot" \
  --output linear_draft.csv
```

此命令将执行以下操作：
1. 调查该网站
2. 尝试检测招聘页面
3. 尝试发现公开的联系邮箱
4. 将调查结果发送给 OpenAI
5. 在终端打印调查摘要和邮件草稿
6. 将此条草稿写入 `linear_draft.csv` 文件中

### 3. 审核草稿

打开 `linear_draft.csv` 文件，在对应的草稿行，将第一列（`approved` 列）的值修改为 `yes`：

```csv
yes,pending_review,,Linear,hello@linear.app...
```

### 4. 发送已批准的草稿

默认的安全模式会将邮件发送到你的审核邮箱：

```bash
python main.py send-approved --drafts-file linear_draft.csv
```

启用实时模式（Live mode）将把邮件发送给系统发现的公司真实联系人：

```bash
python main.py send-approved --drafts-file linear_draft.csv --live
```

## 批量工作流

创建一个 CSV 文件，例如 `leads.csv`：

```csv
company_name,website_url,contact_email,contact_name,careers_url,notes
Acme,https://acme.com,founder@acme.com,Alice,,Hiring engineers for product and infra
```

其中 `company_name` 和 `website_url` 是必需的。
如果 `contact_email` 为空，调查步骤将尝试从该网站中自动发现一个邮箱。

运行以下命令：

```bash
# 1. 调查线索
python main.py research-leads --input leads.csv --output research_results.json

# 2. 生成草稿
python main.py draft-emails --research-file research_results.json --output outreach_drafts.csv

# 3. 发送批准的草稿
python main.py send-approved --drafts-file outreach_drafts.csv
```

## 安全模型

- `OUTREACH_REVIEW_EMAIL` 控制测试模式下已批准草稿的发送去向
- `ALLOW_LIVE_OUTREACH=false` 保持项目始终处于安全的审核模式
- `--live` 命令标志会在单次发送命令中覆盖安全行为
- CSV 文件中的 `actual_recipient_email` 列会记录邮件真正发送到了哪里

## 命令行参考

- `python main.py bootstrap`
- `python main.py send --to you@example.com --subject "Test" --body "Hello"`
- `python main.py send-intro`
- `python main.py research-leads --input leads.csv --output research_results.json`
- `python main.py draft-emails --research-file research_results.json --output outreach_drafts.csv`
- `python main.py send-approved --drafts-file outreach_drafts.csv`
- `python main.py send-approved --drafts-file outreach_drafts.csv --live`
- `python main.py draft-company --company-name "Linear" --website-url "https://linear.app" --output linear_draft.csv`

## 项目结构

- `main.py`: CLI 命令行入口
- `sales_agent/config.py`: 环境变量和运行时设置
- `sales_agent/email_service.py`: Inkbox 邮件服务集成
- `sales_agent/leads.py`: CSV 客户线索加载
- `sales_agent/research.py`: 网站调查和联系邮箱发现
- `sales_agent/openai_drafter.py`: OpenAI 草稿生成和文本清理机制
- `sales_agent/drafts.py`: 草稿创建、CSV 持久化和邮件发送逻辑
- `tests/`: 针对配置、调查、生成和发送行为的单元测试

## 测试

运行测试：

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```
