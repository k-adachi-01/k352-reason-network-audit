# 証跡一覧（2026-11-10 JST）

すべて macOS / Apple Silicon、Reason CLI 0.2.727、reason-network 0.12.17、ネットワーク `kazuki0205-84` での実測。token / secret の本文は含まない。

| # | ファイル | 内容 |
| -- | -- | -- |
| 00 | `00-environment.txt` | 版・日時・ネットワーク |
| 01 | `01-codex-ping.txt` | Codex worker 疎通（14.0s） |
| 02 | `02-codex-delegation.txt` | バグ修正＋テスト＋diff 返却（19.0s） |
| 03 | `03-codex-continuity.txt` | codeword 非継続 |
| 04 | `04-codex-read-boundary.txt` | ホーム配下の読取可否 |
| 05 | `05-codex-write-boundary.txt` | ホーム書込拒否 / `/tmp` 許可 |
| 06 | `06-codex-concurrency.txt` | 3並列依頼（wall 20s） |
| 07 | `07-offline-queue.txt` | offline 滞留→再起動 6.3s、実行1回 |
| 08 | `08-timeout.txt` | `--timeout 4` の挙動（exit 1、id なし） |
| 09 | `09-late-and-duplicate.txt` | 遅延回答の扱い、再起動時の再配送なし |
| 10 | `10-pi-push.txt` | Pi 既存セッションへの push と返信 |
| 11 | `11-pi-continuity.txt` | Pi のセッション継続（codeword 想起） |
| 12 | `12-mcp-probe.txt` | stdio MCP の tools/list と list_team |
| 13 | `13-kiro-mcp.txt` | Kiro CLI から `@reason-network/list_team` |
| 14 | `14-kiro-receive.txt` | 存在しないセッション宛のエラー（受信の前提確認） |
| 15 | `15-kiro-pull-receive.txt` | MCP クライアントの pull 受信（`check_inbox`） |
| 16 | `16-kiro-to-codex.txt` | Kiro → Codex 委譲と返信回収（46.5s） |
| 17 | `17-grok-worker.txt` | `serve grok` は登録するが未ログインで回答不可 |
| 18 | `18-hosted-mcp.txt` | hosted MCP の 401 / OAuth metadata、relay 状態 |
| 19 | `19-inbound-hold.txt` | `inbound hold` が自己送信を止めない |
| 20 | `20-daemon-restart.txt` | daemon 再起動後の再登録（約1s） |
| 21 | `21-post-restart.txt` | 再起動直後の依頼成功（5.6s） |
| 22 | `22-rest-path.txt` | REST の agents 一覧（1.5s）と ask（6.7s） |
| 23 | `23-crash-recovery.txt` | SIGKILL→再起動で in-flight を再実行（36.2s） |
