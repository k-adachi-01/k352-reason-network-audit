# K-352 比較検証レポート — Reason Network vs Tailscale（Grok Bot・Muse・ローカル Agent 委譲基盤選定）

検証日: 2026-11-22 JST（既存 Reason Network 監査 2026-11-10 を再利用し差分を実機補完）  
環境: macOS (Apple Silicon) / `reason-network 0.12.17` / `tailscale 1.104.5` (userspace ephemeral) / Tailscale Personal Free / Grok Bot Desktop / Meta Muse Desktop / Codex CLI / Pi 1.3.0

---

## 0. 結論（採用選定）

**選定：「併用（役割分離）」— 条件付き採用**

1. **主軸（ホスト型 Bot → ローカル非同期タスク委譲・常設インフラ到達）：Tailscale（OAuth Apps / Tailscale Serve HTTPS）＋ 最小契約型 MCP Runner**
   - Grok Bot（公式 OAuth App、`0.53–0.57s`）だけでなく、Reason Hosted MCP が OAuth 阻害となる **Muse（組み込み VM クライアント、`~1.0s`）からも非公開 HTTPS MCP へ到達**できた。
   - Tailscale 単体はネットワーク層だが、約 270 行の最小 Streamable HTTP MCP Runner を置くことで、**対象 repo 限定・`task_id` 冪等性（二重実行ゼロ）・`job_status` 非同期結果回収**を契約レベルで強制できた（Codex 実作業委譲 `29.97s`、再送重複抑止 `0.61s`、結果再取得 `0.52s`）。
   - 常設 Linux（NixOS）や Lambda MicroVMs（K-162）の SSH/サービス到達と同一の枯れた基盤で統一できる。
2. **限定併用（既存 Pi セッションへの対話的 push・ローカル Agent 間協調）：Reason Network**
   - **既存 Pi セッションへの push と会話継続**（2026-11-10 実測 `~20s`・codeword 想起）および **Grok Bot ↔ ローカルの双方向メッセージング**（今回実測：Grok Bot→Codex `~11s`、Mac→Grok Bot `check_inbox` 往復成立）は Reason Network 固有の強み。Tailscale 単体で既存 Pi セッション継続を自作するコストは割に合わない。
   - ただし常設の無人 worker（`serve codex`）としては不採用とし、**対話中セッション間の連絡・補助委譲**に限定する。
3. **不採用・割り切り（逆方向自動化）**：
   - **Pi → Muse**：公式 Inbound API / Webhook / MCP が存在せず、Reason Hosted MCP も Muse 側 OAuth リンク生成のパラメータ欠落（`Missing required parameters.`）で阻害されるため**不採用**。
   - **Pi → Grok Bot**：同期往復が必要なら Reason Network（`check_inbox` / `wake_me`）、イベント通知なら Grok Bot Routine Webhook を補助利用し、独自チャット中継 Adapter は作らない。

### 採用条件（必須ガードレール）
- **OS / コンテナ隔離（両方式共通）**：Reason・Tailscale のいずれも **OS ユーザーの Secrets 隔離を代替しない**。本番の常駐 worker / MCP Runner は普段使い OS ユーザーではなく、専用 OS ユーザー・コンテナ・MicroVM で実行する。
- **Tailscale**：Funnel は使わず **Tailnet 限定 HTTPS（`tailscale serve`）** に限定する。Free プランでは `custom:grokbot` Device Posture が使えず、また Grok Bot デバイス自体のタグ所有化は OAuth App の所有者チェックと衝突するリスクがあるため（§3.3）、**宛先側サーバーのタグ・ACL 制限＋MCP 側 allowlist / `task_id` 冪等性＋OS 隔離**で守る。
- **Reason Network**：`inbound hold` は自己送信を止めないため承認ゲートとみなさない。常設無人 worker は置かず、対話セッション間の連絡に限定する。

---

## 1. 要件マトリクス（接続方向・発見・送受信・既存セッション継続・offline・認証）

| 経路 | Reason Network (`0.12.17`) | Tailscale (`1.104.5` + 最小 MCP Runner) | 判定と根拠 |
|---|---|---|---|
| **Grok Bot → Pi / Codex** | **標準で可（実測済）**<br>・Hosted MCP (`https://mcp.reasonmachines.com/mcp`) OAuth 接続後、`list_team`→`send_message` で `k352-codex` へ 1 往復 **~11s**（Codex 4.5s、`K352-ACK K352RN01` 一致、[`evidence/24`](../evidence/24-grokbot-reason-hosted-mcp.txt)）。<br>・既存 Pi への push・会話継続は 2026-11-10 実測済（~20s）。`serve pi` は非対応。 | **Adapter が必要（実測済）**<br>・公式 Tailscale OAuth App プラグイン（`grokbot-user-35173201`）＋Tailnet 限定 HTTPS MCP（`tailscale serve --https=443`、Funnel OFF）。<br>・read-only MCP 登録＆呼び出し **0.53–0.57s**（[`evidence/26`](../evidence/26-tailscale-grokbot-readonly-mcp.txt)）。<br>・最小 Runner による Codex 実作業委譲 **29.97s**（ホスト `git diff` / `unittest` 独立照合一致、[`evidence/27`](../evidence/27-tailscale-grokbot-runner-delegation.txt)）。<br>・既存 Pi セッション継続には別途 Pi Extension/IPC が必要。 | Reason: 標準で可（Pi push 継続が強み）<br>Tailscale: Adapter 必要（契約・冪等性を強制可能） |
| **Pi / ローカル → Grok Bot** | **標準で可・条件付き（実測済）**<br>・`reason network who` に `kazuki0205-84/cursor` が出現。Mac→Grok Bot へ `K352RN02` を送信（`delivered`）→Grok Bot が `check_inbox` 受信・返信→Mac `inbox` で `K352-ACK K352RN02` 回収（[`evidence/24`](../evidence/24-grokbot-reason-hosted-mcp.txt)）。<br>・**制約**：デフォルトは **pull（`check_inbox` 待ち）** で自動起床しない。自動起床には `wake_me` / Webhook ルーチン設定が必要。 | **Adapter が必要（かつ限定）**<br>・Tailscale 単独では Grok Bot を起こす手段なし。<br>・一次資料＋Grok Bot 実機確認により、Routine の **Webhook トリガー**（外部 `POST`）やメール起動はあるが、会話スレッドへの任意送信・同期返信回収 API は未提供。<br>・逆方向自動化には Webhook 起動＋共有ストア/コールバック回収 Adapter（150〜300行）が必要。 | Reason: 条件付き可（pull / `wake_me` 前提）<br>Tailscale: 単独不可（Routine Webhook + 回収 Adapter 必要） |
| **Pi / ローカル ↔ Muse** | **不可・阻害条件あり（実測済）**<br>・Muse が `https://mcp.reasonmachines.com/mcp` の OAuth メタデータ取得（DCR + PKCE S256）までは到達。<br>・生成された `Connect` リンクを開くと **2 回連続で `Missing required parameters.`** となり OAuth 完了不可（[`evidence/25`](../evidence/25-muse-reason-and-tailscale.txt)）。<br>・Pi → Muse 逆方向も不可。 | **Muse → Mac は Adapter 必要（実測済）／Pi → Muse は不可**<br>・Muse には Tailscale 公式 OAuth App 統合はなく、**VM 組み込みラッパー**で毎回承認リンクが必要。<br>・承認後 `muse` (`100.116.68.126`, DERP `nyc`) として参加し、Mac 非公開 HTTPS MCP へ `GET /health`（初回 ~7.8s）・`POST /mcp` `k352_ping`（**~1.0s**、`K352-TS-ACK K352MUSETS` 一致）成功（[`evidence/25`](../evidence/25-muse-reason-and-tailscale.txt)）。<br>・Mac → `muse` の `tailscale ping` は 3/3 タイムアウト。<br>・**Pi → Muse** は公式 API / Webhook / Inbound MCP が一切未提供（WhatsApp / Muse Mail のみ）。 | Muse→Mac: Tailscale（VM 承認＋Adapter）可、Reason は OAuth 阻害<br>Pi→Muse: 両方式とも **不可** |
| **Mac ↔ Linux（常設）** | **標準で可（K-353・既存実測、現行 Linux 機は offline 23–33d）**<br>・UDP/QUIC P2P または iroh Relay E2E 暗号化。daemon は launchd/systemd 常駐。worker は監督プロセスなし。 | **標準で可（ネットワーク層）**<br>・WireGuard P2P / DERP Relay、Tailscale SSH / Serve / Services が標準。Agent セッション配送には Runner/SSH Adapter が別途必要。 | ネットワーク層は Tailscale、Agent 層は Reason が標準提供 |
| **Kiro CLI → Pi / Codex** | **送信可・受信は pull のみ（2026-11-10 実測済）**<br>・stdio MCP 追加で `list_team` (19.6s)・Codex 委譲 (46.5s) 成功。公式 wired-up 外、受信 wake 不可。 | **Adapter 必要（MCP クライアントとして可）**<br>・Tailnet 参加端末なら Tailscale Serve 非公開 MCP を標準 MCP クライアントとして呼び出し可。受信 wake は不可。 | 両方式とも送信可・受信 wake 不可 |

### 機能軸サマリ

| 軸 | Reason Network | Tailscale（＋最小 MCP Runner） |
|---|---|---|
| 発見（Discovery） | 標準（`list_team` / `who` で live session・repo・branch・状態表示） | ネットワーク層は MagicDNS / `tailscale status`。Agent/ツール発見は MCP `tools/list` |
| 送受信 | 標準（`send_message` / `check_inbox` / `wake_me`） | ネットワーク層のみ。MCP Runner（約 270 行）で RPC 提供 |
| 既存 Pi セッション配送・継続 | **可**（push 配送、codeword 想起成立） | **不可**（別途 Pi Extension / IPC 実装が必要） |
| オフラインキュー・復旧 | worker 停止中 `queued`→再起動 6.3s 配送。**SIGKILL 時は in-flight 再実行（二重実行リスク）**。`TO` timeout で id 消失 | Tailscale 自体はキューなし（接続不可を即時エラー返却）。**Runner 側で `task_id` 冪等性（0.61s で重複抑止）・`job_status` 再取得（0.52s）を実装可能**。永続化は SQLite 追加 |
| 認証・ネットワーク経路 | PC 間 E2E（iroh P2P/Relay）。Hosted assistant は Reason サーバー経由（OAuth） | WireGuard E2E（P2P/DERP）。Grok Bot は OAuth Apps（DERP `iad` 164–177ms）、Muse は VM ラッパー（DERP `nyc`） |

---

## 2. 同条件タスク実測比較（P1）

対象: Secret なしの `fixtures/k352-repo`（`calc.py` の `a - b` バグ修正 → `python3 -m unittest -v` → `git diff` 返却）

| 項目 | Reason Network (`serve codex`, 2026-11-10) | Tailscale + 最小 MCP Runner (`k352-ts-fix-002`, 2026-11-22) |
|---|---|---|
| 依頼元 | ローカル CLI / REST（Grok Bot ping 往復は今回 ~11s） | **Grok Bot（Implementation ボット）実機** |
| 成功率・独立照合 | 成功（ホスト `git diff` / `unittest` と一致） | **成功（ホスト `git diff` / `unittest` 2/2 OK と完全一致）** |
| 往復時間 | 19.0s（Codex 実行込み） | **29.97s**（うち Codex 28.33s、通信往復 ~0.5–0.6s） |
| 読み取り専用 RPC レイテンシ | REST `agents` 1.5s / `ask` 6.7s | `k352_ping` / `k352_read_fixture`: **0.53–0.57s** (3/3 HTTP 200) |
| 同一タスク再送（冪等性） | SIGKILL 再起動で **最初から再実行（二重実行リスク）** | **`0.61s` で `deduplicated: true, duplicate_hits: 1`（二重実行なし）** |
| タイムアウト後の結果回収 | `TO` タイムアウト時は request_id 消失（`send`+`follow` 必須） | **`k352_job_status` で `0.52s` にて diff/テスト結果を再取得可能** |
| 既存 Pi セッション継続 | **成立**（~20s push） | **非対応**（追加 Pi Adapter が必要） |
| 経路制約・つまずき | `ask-*` 一時セッションが roster ノイズになる。無料 Network への `switch` は未実施 | Grok Bot の box は Pingora プロキシ経由で **FQDN (`*.ts.net`) のみ到達可**（短縮名・`100.x` IP・ICMP 不可）。平文 HTTP はプロキシ制約を受けやすく **Tailscale Serve HTTPS（Funnel OFF）が実用的** |

---

## 3. セキュリティ・認証・コスト・保守負担の比較

### 3.1 認証・権限境界
- **Reason Network**：
  - worker が同一 OS ユーザーの `~/.ssh`, `~/.config/gh/hosts.yml`, `~/Library/Keychains`, `~/.config/reason/credentials.json`（31 スコープ）を読める（2026-11-10 実測）。
  - `inbound hold` は自己 identity 送信を止めないため承認ゲートにならない。
- **Tailscale（OAuth Apps）**：
  - OAuth Apps（2026-11-09 GA）により、Grok Bot は個人ユーザー identity（`<user>@gmail.com`）のデバイス `grokbot-user-35173201` として参加する。
  - **Free プランの制約**：公式ブログにある `custom:grokbot` Custom Device Posture は **Premium / Enterprise 限定**。Free プランでは使えない。
  - **実測で見つけた重要な注意点**：接続状態遷移時に Grok Bot UI へ `The Grok Bot device is no longer owned by the Tailscale login it signed in as, so Grok Bot signed it out.` と表示される挙動を確認。Free プランで Grok Bot デバイス自体をタグ所有（tag-owned）へ変更すると、OAuth App の所有者チェックと衝突し強制サインアウトされるリスクがある。したがって **宛先側サーバーをタグ管理＋ポート最小化＋MCP 側 allowlist / 認可＋専用 OS ユーザー/コンテナ隔離** で境界を作る必要がある。
- **共通原則**：どちらの通信基盤も OS ユーザーの Secrets 隔離を代替しない。

### 3.2 コスト・運用保守負担

| 項目 | Reason Network | Tailscale + 最小 MCP Runner |
|---|---|---|
| 通信基盤の無料枠 | 無料（OSS engine、カード不要。Cloud Session 未使用なら 0 円） | Personal Free 無料（最大 6 users、個人デバイス無制限、タグ付きリソース 50 台、Tailscale Serve 無料。Posture 使うなら Premium $18/user/月） |
| モデル利用料 | 受信側 Codex / Pi の契約・API 料金 | 同じ（受信側 Codex / Pi の契約・API 料金） |
| 常設ホスト費用 | 常設受信先（自宅 Linux 機 or VPS）が別途必要 | 同じ（常設受信先が別途必要） |
| Adapter コード量 | **0 行**（worker 監督 launchd/systemd + 隔離設定のみ） | 最小 Runner **約 270 行**（[`scripts/tailscale_mcp_runner.py`](../scripts/tailscale_mcp_runner.py)）。SQLite 永続化・systemd 化を含めて ~400 行、Pi 既存セッション連携まで自作するなら ~700 行超 |
| アップデート・運用保守 | Reason CLI / engine 更新追従（仕様変更・CLI フラグ変更リスクあり） | Tailscale 自体は極めて安定。自前 MCP Runner と Codex CLI フラグ変更（今回 `--full-auto` 廃止→`-s workspace-write` へ修正）への追従が必要 |

---

## 4. 再現手順（Tailscale 側最小構成）

```sh
# 1) Mac で一時 userspace Tailscale ノードを起動（OS 設定変更なし）
tailscaled --tun=userspace-networking --statedir=/tmp/k352-ts-state --socket=/tmp/k352-ts.sock &
tailscale --socket=/tmp/k352-ts.sock up --hostname=k352-mac-test

# 2) まず read-only MCP を起動し、Tailnet 限定 HTTPS で公開（Funnel は必ずオフ）
python3 scripts/tailscale_mcp_runner.py --host 127.0.0.1 --port 18352 --mode readonly --fixture ./fixtures/k352-repo &
tailscale --socket=/tmp/k352-ts.sock serve --bg --https=443 18352

# 3) Grok Bot の Tailscale プラグインを OAuth 接続し、
#    https://k352-mac-test.<tailnet>.ts.net/mcp を MCP サーバーとして追加 → k352_ping / k352_read_fixture を確認

# 4) Runner モードへ切替（fixture 限定・task_id 冪等性あり）
python3 scripts/tailscale_mcp_runner.py --host 127.0.0.1 --port 18352 --mode runner --fixture ./fixtures/k352-repo &
# Grok Bot から k352_delegate_codex (task_id="k352-ts-fix-002") → 同一 task_id 再送 → k352_job_status を確認

# 5) 終了時クリーンアップ
tailscale --socket=/tmp/k352-ts.sock serve reset
tailscale --socket=/tmp/k352-ts.sock logout
```

---

## 5. 証跡・一次資料

- 新規証跡（2026-11-22）:
  - [`evidence/24-grokbot-reason-hosted-mcp.txt`](../evidence/24-grokbot-reason-hosted-mcp.txt)
  - [`evidence/25-muse-reason-and-tailscale.txt`](../evidence/25-muse-reason-and-tailscale.txt)
  - [`evidence/26-tailscale-grokbot-readonly-mcp.txt`](../evidence/26-tailscale-grokbot-readonly-mcp.txt)
  - [`evidence/27-tailscale-grokbot-runner-delegation.txt`](../evidence/27-tailscale-grokbot-runner-delegation.txt)
  - [`scripts/tailscale_mcp_runner.py`](../scripts/tailscale_mcp_runner.py)
- 既存 Reason Network 監査（2026-11-10）: [`REPORT.md`](../REPORT.md), [`evidence/INDEX.md`](../evidence/INDEX.md)
- 一次資料:
  - Tailscale OAuth Apps GA / Grok Bot 統合 (2026-11-09): https://tailscale.com/blog/oauth-apps-ga
  - Tailscale OAuth Apps Docs: https://tailscale.com/docs/features/oauth-apps
  - Tailscale Services Docs: https://tailscale.com/docs/features/tailscale-services
  - Reason Network Docs: https://docs.reasonmachines.com/docs/network
  - Reason MCP Docs: https://docs.reasonmachines.com/docs/mcp
