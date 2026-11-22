# K-352 監査・比較検証 — Reason Network vs Tailscale（Grok Bot・Muse・ローカル Agent）

Grok Bot / Muse / Codex / Kiro / Pi の間で安全・低運用負荷に作業委譲する通信基盤として、**Reason Network（engine 0.12.17）** と **Tailscale（OAuth Apps + Tailscale Serve HTTPS + 最小 MCP Runner）** を実機で比較検証したリポジトリ。

- **2026-11-22 最終比較・選定レポート**: [docs/k352-tailscale-comparison-report.md](docs/k352-tailscale-comparison-report.md)（**結論: 併用（役割分離）— 条件付き採用**）
- **2026-11-10 Reason Network 単体監査**: [REPORT.md](REPORT.md)

## 構成

- `docs/k352-tailscale-comparison-report.md` — Reason Network vs Tailscale 比較検証レポート・要件マトリクス・採用選定と条件
- `REPORT.md` — 2026-11-10 Reason Network 監査結果・重大所見
- `docs/k352-grok-muse-runbook.md` — ローカル Pi ↔ Grok Bot / Muse の検証手順
- `evidence/` — 実測ログ（`INDEX.md` に一覧、`00`〜`27`）。token / secret 本文は含まない
- `scripts/tailscale_mcp_runner.py` — Tailscale Serve HTTPS 向け最小 Streamable HTTP MCP サーバー／冪等 Runner（`readonly` / `runner` モード）
- `scripts/rest_ask.py` — hosted assistant と同じ REST 経路（`GET agents` / `POST messages`）
- `scripts/mcp_probe.py` — stdio MCP の `initialize` / `tools/list` / `tools/call` プローブ
- `scripts/mcp_receive_test2.py` — MCP クライアントの pull 受信（`check_inbox`）検証
- `fixtures/k352-repo` — Secrets なしの検証用 repo（`add()` に意図的なバグ）

## 要約

| 対象 | 判定 |
| -- | -- |
| Codex（`serve codex`） | 可。実作業委譲 19s、独立照合一致。会話は非継続 |
| Pi（native session） | 可。idle へ push、セッション内で継続 |
| Kiro CLI（stdio MCP） | 送信可。受信は `check_inbox` の pull のみ（wake なし） |
| Grok Bot（hosted MCP） | 未検証（MCP 到達性と REST 経路のみ確認） |
| Grok CLI（`serve grok`） | 不可（ローカル未ログイン） |

## 主要な安全所見

1. worker は同一 OS ユーザーの資格情報を読める（`~/.config/gh/hosts.yml`, `~/.config/reason/credentials.json` など）。専用ユーザー/コンテナ/VM が必須。
2. `inbound hold` は自己送信を止めない。承認ゲートとして使えない。
3. `serve` worker の監督プロセスがなく、SIGKILL 後は停止したまま。復帰時は in-flight を再実行する。
4. `TO` の timeout では request id が返らず、遅延回答を回収できない（`send` + `follow` が必要）。
5. 無料 Reason Network への `reason network switch` は未実施（本機は workspace network 上）。
