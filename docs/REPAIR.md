> 第二轮更新见 DATA_PIPELINE_V21.md 与 REAL_DATA_RECONCILIATION.md。下文保留第一轮修复范围；最新数据接口、测试计数和验证结果以第二轮文档为准。

# Systemic Risk 核心修复版

基线：u2017310234/systemic-risk，commit 2d0ee5079a814026a67c6c027205355572dff2a2。
修复方式：本地源码编辑；未推送仓库、未修改线上服务。下载了核心 Python、完整前端及已有测试；没有把旧数值当成修复后的数据交付。

## 重要结论

这版修复了确定性的计算、数据口径和发布错误，并建立可执行的回归测试。它不等于已经完成真实 29 家银行的重新估计，更不等于经过校准的风险预测产品。

最关键的剩余输入是各银行真实披露日期对应的合并报表负债，以及部分机构的集团整体市值。Yahoo 的财报列日期只是报告期末，不能视作披露日。当前版本选择缺失显示 null，而不是凭空补日期或照抄另一家银行。

## 已修复

1. **单位与身份**：所有 FX 使用 USD/单位本币的直接报价；GBp 明确乘 0.01；汇率失败或超过 7 日未更新输出空值。报价币与报表币分开登记。移除港股股数一律除以 100。取消异常市值常数回填与保留异常值。
2. **银行范围**：BPCE 不再复制 GLE 的市值、负债和风险值。A/H 股银行及 Crédit Agricole 的集团市值须提供经过核实的集团口径，不把单一上市证券当成整个集团。
3. **历史时点**：市值使用带日期股数，不使用今天股数回填整个历史；市值不使用分红复权价格。跨拆股区间须提供已核实市值，避免股数与价格基准混合。供应商股数仍标注“未经 point-in-time 验证”。
4. **负债披露**：只在 available_date 后启用当时已披露的负债，最长前向沿用 200 个日历日。没有有效来源时 SRISK 为空；MES/CoVaR 仍能计算。没有暗中切换 A 股作为 H 股的替代。
5. **覆盖**：coverage 记录预计银行、观察到的银行、具有 SRISK 的银行及缺失原因。全样本不完整时 system_srisk_usd_bn=null，另提供 covered_srisk_usd_bn。零风险与未知风险区别处理。
6. **发布一致性**：先完成全部计算和 share，再写 JSON/CSV；重复日期由新值覆盖。每次生成不可变 runs/<id>，通过 current.json 一次性切换。失败不会覆盖上一批已发布结果；提交前逐项对照 JSON/CSV。配置变化必须使用新 DATA_DIR，全量重算，不能混接时间序列。
7. **前端**：时间序列先按日期配对，再计算相同区间的变化；至少 10 对变化值。无效或常数相关性不给边；同区域不凭空加连线。保留带正负号的相关性，边强度只使用正向相关部分。
8. **压力展示**：不再对均值恒为零的横截面 z-score 求平均。改为固定当前节点集合的 SRISK 历史百分位，0–100；至少 20 个更早且可比的日期，否则 N/A。网络密度单独展示，节点颜色仍是相对分数。百分位仅指当前回看窗口，并非长期校准指标。
9. **LRMES**：明确改为 OLS-beta 累积下行情景近似，取消为了得到正 SRISK 而取更大 beta 的逻辑。h 仅是场景标签，不声称做了多期动态模拟。CoVaR 回归不收敛时输出缺失，不再默默换成未验证的 SGD 数值。
10. **运行入口**：修复 setuptools 后端；将服务器迁至 risk_mcp，消除与第三方 mcp SDK 同名遮蔽；gsib-mcp 是可执行入口；历史空值可合法序列化，旧方法数据不进入新版排名。

## 使用

建议先在独立目录运行，不覆盖现有线上数据。

```bash
python -m venv .venv
. .venv/bin/activate
pip install '.[test]'
pytest tests loc/test_branch_locator.py -q
export DATA_DIR=/absolute/path/new-risk-data
export FUNDAMENTALS_DIR=/absolute/path/verified-fundamentals
python -m src.pipeline --start 2024-01-01 --end 2025-12-31
python scripts/verify_data_offline.py
gsib-mcp
```

默认从源站读取市场数据；测试不需要网络。数据抓取依然受供应商接口和授权约束。

### 基本面输入

每家银行一个 BANK_ID.json，见 inputs/fundamentals.example.json。该文件纯属合成演示，不能复制到正式输入目录。货币可按字段分别指定。value 使用原币绝对金额，不是十亿；程序统一除以 1e9 并换算美元。

- scope 必须为 consolidated_group。
- effective_date 是数值对应日期；available_date 是实际可知日期，不可早于 effective_date。
- 负债在 available_date 后启用。若晚于收市披露，请将 available_date 设为下一可用交易日，日频系统不处理盘中发布时刻。
- market_cap 必须是其估值日可观察到的集团整体市值；不可把晚获取的旧市值当作新日期市值。市值不前向填充。
- source 应保存实际披露文件 URL/页码或可复核出处。程序验证结构，不能自动证明引用真实或数值正确。
- 不同股类市值须按各自价格和股数折算后汇总。上市子公司不能直接替代整个集团。
- 如果供应商只有报告期末而没有公开日期，需要补充数据源；本补丁不自行编造披露日。

### 前端

```bash
cd frontend
npm ci
npm test
npm run typecheck
DATA_SOURCE_DIR=/absolute/path/new-risk-data npm run build
```

sync-data 会解析 current.json，只复制已经提交的一批数据，不把 raw、失败的暂存 run 或其他历史 run 暴露到网站。

MCP 读取同一 DATA_DIR/current.json。GitHub 远端模式亦解析同一指针。部署时前端和 MCP 必须指向同一批结果；这次未更新 Cloudflare/Azure 部署。

### 方法边界

- 样本登记为 legacy-research-29-v2，不声称是最新 FSB 名单。
- OLS-beta 场景近似不是 Brownlees–Engle 的动态波动/相关性模拟。未经真实危机样本回测，不应称为预测概率。
- 不同地区使用不同市场指数，跨地区 ΔCoVaR 排序仍需谨慎。
- 股数供应商历史版本和财报重述仍需有版本化来源；当前数据不能默认用于无前视回测。
- 滚动估计使用目标日前的观测窗口；资产负债输入使用目标日可得值。
- 部署环境按 Linux/POSIX 文件锁设计。生产数据更新应串行，不要在同一 Python 进程并行修改全局 cfg。
- 旧 runs 保留以便回滚，需运营方制定保留期限；本修复不自动删除历史数据。

## 验证

详见 docs/VALIDATION.md。真实历史数据重算和真实浏览器视觉验收不包含在已完成验证内；不要把合成测试结果当作银行风险分析。
