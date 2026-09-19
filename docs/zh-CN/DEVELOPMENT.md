# 开发

基于 [404404/HardwareStatus](https://github.com/404404/HardwareStatus) 的当前 `2.0`
主线开发。源码中仍保留多个 `hermesstatus` 兼容名称；不能仅因仓库改名而重命名运行时接口。

## 变更原则

从干净 worktree 和最新远端基线开始。保持 Client → Device v2 → Server → 单一 stats 投影 →
UI 的数据路径。新增 wire field 必须同时检查 Client 校验、Server decode/model、persistence、
API/schema、UI、测试和回滚行为。

优先使用固定时钟、合成计数器和脱敏 fixture。不得通过接受未知字段、弱化 TLS/SSH、隐藏真实
故障或填充虚假 telemetry 让测试通过。

## 必要检查

先跑针对性回归，再跑受影响 suite：

```sh
(cd clients && python3 -m unittest discover)
(cd scripts/tests && python3 -m unittest discover)
(cd server && go test ./...)
(cd server && go test -race ./...)
(cd server && go vet ./...)
(cd server && go build ./...)
node --test web/js/app.test.js
python3 scripts/validate_migration_contracts.py
python3 scripts/check_release_boundaries.py
python3 scripts/check_unifi_static_authority.py
git diff --check
```

纯文档变更只运行相关检查；candidate 或 release 变更必须完整通过必要 gate。

## Candidate 与 review

向 `codex/` 任务分支提交可审查差异并创建 Draft PR。完整 review 应覆盖 data contract、资源
归属、当前诊断、bounds/truncation、凭据暴露和 image provenance。候选只能由 GitHub CI 构建；
记录 source SHA、Server digest、Client digest、platform，以及适用时的 Catalog revision/hash。

资格验证后任何源码变更都会产生新 candidate 并使旧资格失效。实机证据必须与 offline/CI 证据
分开记录；不能把 fixture 通过描述为 GK50 或 RS820 结果。

## 文档

行为或公开术语变化时同步更新中英文。项目名称是 HardwareStatus；已有运行时名称和 GHCR 包名
在有明确迁移计划前仍是兼容契约。
