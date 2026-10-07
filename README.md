# Systemic Risk — v2.4.2

29 家银行研究样本的 MES、CoVaR/ΔCoVaR 与 OLS-beta 情景 SRISK 服务。包含 Python 计算流水线、MCP 接口及 Next.js / Cloudflare 前端。

**本包默认即可运行历史演示。附带数据为 2025-05-16 的 27 家银行历史重建，并非当前风险数据。** 原始审计来源保留在 `examples/verified-disclosures-v23/`；没有改写其 v2.3 校准身份，也没有虚构后续时间序列。

本次修改基于仓库 `bf3d7dea569600974088e37593ff49090c54de40`。本次交付说明见 [docs/DELIVERY_V241.md](docs/DELIVERY_V241.md)，历史修复记录见 `docs/REPAIR_V23.md` 等文件。

## v2.4.2：无数据时正常跳过

Daily workflow 遇到行情不可用或发布覆盖不足时正常结束，明确记录 `skipped`，保留旧数据，不提交空批次。Live acceptance 遇到数据不可用时标记 `unavailable` 并跳过前端真实数据构建；这不代表真实验收通过。代码、测试、构建和配置错误仍然失败。详见 [docs/DELIVERY_V242.md](docs/DELIVERY_V242.md)。

## v2.4.1 修正

详见 [docs/DELIVERY_V241.md](docs/DELIVERY_V241.md)：恢复 Yahoo 日常研究基本面路径，按指标报告覆盖；新增独立演示批次指针，避免覆盖上传残留旧历史导致构建失败；新增真实 Yahoo → 计算 → MCP → 前端的独立验收工作流。**当前环境真实请求受到 Yahoo 429 限流，未宣称实时端到端已通过。**

## 本地启动

Python 3.11+、Node.js 22+，命令从项目根目录执行。

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install '.[test]'
python -m pytest tests loc/test_branch_locator.py -q
uvicorn risk_mcp.server:app --host 0.0.0.0 --port 8000
```

另开终端：

```bash
cd frontend
npm ci
npm run dev
```

前端：`http://localhost:3000`。MCP：`http://localhost:8000/mcp`。后端健康：`/health`。前端可独立展示默认样本，不依赖 MCP 在线。需要前端转发 MCP 时设置 `MCP_ORIGIN_URL=http://127.0.0.1:8000`。

## 本次变化

- Actions 安装项目本身并通过 `python -m pytest` 执行；生产任务先检查输入，测试失败或质量门槛未通过不发布。
- 新增研究、历史和生产模式。生产按交易日历及收市宽限检查可计算银行的新鲜度，默认至少 80%；失败保留旧指针，记录 `data/last-attempt.json`。
- 明确休市、尚未到计算时点、缺行情、输入/计算失败及不适用。旧值单独注明观察日期，不补进当日排名与合计。
- MCP 排名带校准、参数、质量和覆盖信息；方法说明读取快照参数；增加敏感性与同银行变化归因。
- 增加配对移动块 bootstrap 和按时间切分的预测评分验证入口；不会拿单日样本冒充历史回测。
- 前端全站显示数据性质；单银行页展示场景表；网络边显示有效样本数、时间范围及半窗口相关性。
- Cloudflare 生成真实 `out/` 静态资源，由 Worker 转发 MCP、提供状态与数据 CORS。保留普通 Next.js 构建。

## 构建与部署

```bash
cd frontend
npm ci
npm test
npm run build                  # 普通 Next.js，npm start 启动
npm run build:cloudflare       # Cloudflare 静态资源 + Worker
npx wrangler deploy --dry-run  # 只验证，不发布
# 账号授权、域名和 MCP_ORIGIN_URL 配置完成后：
npx wrangler deploy
```

Cloudflare Git 集成根目录设为 `frontend`，构建命令 `npm ci && npm run build:cloudflare`，部署命令 `npx wrangler deploy`。这是 **Workers** 项目，不能把 `.next` 当作静态资源上传。MCP Python 服务独立部署；根目录提供 Dockerfile。外部域名需加入后端 `MCP_ALLOWED_HOSTS`。

## 启用真实生产更新

先运行新增的 `Live Yahoo end-to-end acceptance` Actions 工作流，真实检验 JPM/BAC 的 SRISK、其他指标、MCP 和前端。再运行 Daily Pipeline 查看全体覆盖。

Daily 显式启用 `FUNDAMENTALS_POLICY=yahoo_daily`、`PUBLICATION_BASIS=market_metrics`，不再要求预先提供人工基本面 JSON。日常估计使用 Yahoo 获取版本并标注未做严格时点核验；复杂集团市值等缺口保持 null。定时运行仍需 `RISK_PRODUCTION_ENABLED=true`。

严格历史重算使用 `FUNDAMENTALS_POLICY=verified`，输入格式见 `inputs/fundamentals.example.json` 和 `docs/REPAIR.md`，必须使用独立数据目录。示例为合成数据，不能当生产输入。

本地日常运行：

```bash
FUNDAMENTALS_POLICY=yahoo_daily PUBLICATION_BASIS=market_metrics python -m src.workflow_run
```

不同校准不可直接拼接。前端构建时用 `DATA_SOURCE_DIR`，后端用 `DATA_DIR` 指向同一已发布批次。此压缩包没有替你更新远端仓库、Cloudflare 或 Azure。

LRMES 是 OLS-beta 情景近似，不是动态危机模拟；资本率不是 Basel 风险加权资本率；统计联动不等于双边敞口或因果传染。真实全历史重算和独立样本外效果仍需后续数据支持。
