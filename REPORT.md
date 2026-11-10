# K-352 監査レポート — Reason Network で Grok Bot・Codex・Kiro・Pi を連携し、委譲・常設復旧を検証する

監査日: 2026-11-10 JST / 実施: Pi Agent（macOS, Apple Silicon）/ 版: Reason CLI 0.2.727, reason-network engine 0.12.17

## 0. 結論

**判定: 条件付き採用（通信路は成立、常設運用は不採用）。**

- 現行 engine 0.12.17 で、Codex worker・Pi 既存セッション・Kiro CLI（stdio MCP）・REST 経路の**発見・送信・返信回収**が実測で成立した。K-340（engine 0.10.7）の主要所見は現行版でも再現する。
- ただし **常設の無人運用は不可**。理由は (C1) 実行ユーザーが資格情報を読める、(C2) `inbound hold` が自己送信を止めない、(C3) worker の監督プロセスがない、(C4) 遅延回答が失われる、の4点。いずれも「Reason Network の不具合」ではなく、**受信側の実行境界と運用設計の問題**。
- 4対象の状況は一様ではない。**Codex＝可 / Pi＝可 / Kiro＝送信のみ（受信は pull）/ Grok Bot＝未検証**。Grok は CLI worker もローカル認証未了で回答できなかった。
- 無料 Reason Network への移行（`reason network switch`）は**未実施**。本機は現在も旧 workspace network（`kazuki0205-84`）上にあり、本レポートの実測はすべてそのネットワークで取っている。
- 常設 Linux 受信側は存在しない（roster 上の他マシンは 19–21 日 offline）。したがって Done 条件 3（常設 Linux・Grok box reset・sleep・断）は**未達**。

Done 条件との対照は §6、残件は §7。

## 1. 監査環境

| 項目 | 値 |
| -- | -- |
| ホスト | macOS 26 (Apple Silicon), ユーザー `adachi` |
| Reason CLI | 0.2.727（`~/.local/bin/reason`） |
| reason-network engine | 0.12.17（`~/.reason/bin/reason-network`, OSS） |
| Codex CLI | 0.162.1 |
| Pi | 1.3.0（`~/.pi/agent/extensions/reason-network.ts` で native 接続） |
| Kiro CLI | 3.0.0 |
| Grok CLI | Nix 版（未ログイン） |
| ネットワーク | `kazuki0205-84`（workspace 056cd2ee-…）。**Reason Network への switch は未実施** |
| daemon | launchd `com.reasonmachines.network`（`KeepAlive` あり） |
| inbound 既定 | `accept`（`~/.reason/network/config.toml`） |

証跡: [`evidence/00-environment.txt`](evidence/00-environment.txt)

## 2. 接続能力マトリクス（実測）

| 対象 | 発見 | 送信 | 受信 | wake / push | 会話継続 | 往復 | 判定 |
| -- | -- | -- | -- | -- | -- | -- | -- |
| **Codex**（`serve codex`） | ✅ | ✅ | ✅ worker | ✅ worker 常駐 | ❌ 毎回新規 | 5.6–19.0s | **可**（条件付き） |
| **Pi**（native session） | ✅ | ✅ | ✅ push | ✅ idle でも配送 | ✅ セッション内で継続 | ~15–25s | **可**（条件付き） |
| **Kiro CLI**（stdio MCP） | ✅ | ✅ | ⚠️ `check_inbox` の pull のみ | ❌（wake なし） | セッション依存 | 19.6s（list） / 46.5s（委譲） | **送信可・受信は条件付き** |
| **Grok CLI**（`serve grok`） | ✅ | ✅ | ✅ worker | ✅ | 未測定 | 5.3s（認証エラー応答） | **不可（ローカル未ログイン）** |
| **Grok Bot**（hosted MCP） | ⚠️ エンドポイント到達のみ | 未 | 未 | 未 | 未 | — | **未検証** |
| **REST 経路**（hosted 相当） | ✅ 200 / 1.5s | ✅ | ✅ resume 可 | — | 不可（request 単位） | 6.7s | **可** |

- 「wake」は、停止・idle のエージェントをメッセージだけで起こせるか。Codex/Pi/Grok worker は常駐プロセスが受けるので可、Kiro は不可。
- Kiro は `reason network doctor` の wired-up 一覧（Claude Code, Codex, Grok CLI, Cursor, Gemini, Antigravity, opencode, Pi, DeepSeek Harness, Reason）に**含まれない**。MCP を手で足せば送信側にはなるが、ネイティブ peer ではない。
- `serve pi` は現行版でも非対応（`serve` は claude / grok / codex のみ）。Pi は起動済みセッションへの push のみ。

## 3. 実測結果

### 3.1 Codex worker

作業ディレクトリは `fixtures/k352-repo`（Secrets なし、`add()` にわざとバグを入れた repo）。

| 試験 | 結果 | 証跡 |
| -- | -- | -- |
| 疎通（pwd + README 1行目） | `K352-PONG`、14.0s | [`01`](evidence/01-codex-ping.txt) |
| 実作業委譲（バグ修正＋unittest＋diff 返却） | 19.0s。返却 diff・テスト結果をホスト側 `git diff` / `python3 -m unittest -v` で**独立照合し一致** | [`02`](evidence/02-codex-delegation.txt) |
| 会話継続（codeword） | 1通目 `OK`、2通目 `NOT-REMEMBERED`。**非継続** | [`03`](evidence/03-codex-continuity.txt) |
| 並列3依頼 | 3件とも正答、wall 20s。混線なし（実質は直列処理） | [`06`](evidence/06-codex-concurrency.txt) |
| worker 停止中の送信 | `queued` → worker 再起動後 **6.3s** で回答、実行は1回のみ | [`07`](evidence/07-offline-queue.txt) |
| `--timeout 4` | `timed_out: true`、exit 1。**request id が返らず後から回収不能** | [`08`](evidence/08-timeout.txt) |
| 遅延回答の取り回し | `TO` の timeout 後、`inbox` には残らない。`send` + `follow` が必須 | [`08`](evidence/08-timeout.txt), [`09`](evidence/09-late-and-duplicate.txt) |
| worker 再起動の重複 | 再起動後も `runs.log` は1行。**再配送なし** | [`09`](evidence/09-late-and-duplicate.txt) |
| SIGKILL（実行中）→ 再起動 | 未完了 request を**最初から再実行**し 36.2s で回答 | [`23`](evidence/23-crash-recovery.txt) |

注意: 3.1 の「非継続」は、CLI が依頼ごとに送信元セッション（`ask-xxxx`）を作るためでもある。`serve codex` の設計（依頼ごとに新規会話）と、CLI 側の送信元非永続の両方が効いている。継続が必要な作業は Pi を使うか、1通に文脈を全部入れる。

### 3.2 Pi（native push）

- アイドル状態の Pi セッションへ `send` → 約20s で `K352-PI-OK` を受信（`evidence/10`）。配送は 5s 間隔の poll。
- 同一セッションへ codeword を送り、次ターンで想起 → `K352PITIN` を返答。**セッション継続は成立**（`evidence/11`）。
- ここで `reason network TO` は 120s タイムアウトした。Pi が返信先を `terminal` にしたため、`TO` の待ち受け（一時送信元セッション）と一致しなかった。**返信は `inbox` に届いており、`send` + `inbox`/`follow` で回収できる**。エージェントに「reply_to を返せ」と指示するときは宛先も明示する必要がある。

### 3.3 Kiro CLI

`kiro-cli mcp add --name reason-network --command ~/.reason/bin/reason-network --args mcp` で stdio MCP を登録（検証後に削除済み。設定スニペットは [`evidence/13`](evidence/13-kiro-mcp.txt) の直前手順参照）。

- `list_team` 呼び出し成功（19.6s、`@reason-network/list_team`）。
- Kiro → Codex へ `send_message` → `message_status` を poll → `check_inbox` で本文回収。**`K352-KIRO-VIA-CODEX` を受信**（46.5s、`evidence/16`）。
- 受信側としては **pull 専用**。MCP クライアントを常駐させても `check_inbox` を呼ぶまで読まれず、配送時にも "this agent only sees it when it checks its inbox" と明示される（`evidence/15`）。Kiro セッションを起こす手段はない。
- MCP サーバーのセッション名は cwd から `<dir>-agent` として登録され、`REASON_NETWORK_SESSION` では指定できなかった（0.12.17）。Kiro Crew の UI 側は未検証。

### 3.4 Grok

3経路を分けて扱う。

1. **hosted Grok Bot（`https://mcp.reasonmachines.com/mcp`）**: 未認証 POST は `401 missing_bearer` + `WWW-Authenticate` に OAuth resource metadata。エンドポイント自体は健在（`evidence/18`）。relay（`reason network __relay`）はインストール済みで、最終到達 11:45 UTC。**Grok Bot の画面からの接続・送受信・wake は、本人のブラウザ/API キーが必要なため未検証**。
2. **Grok CLI worker（`serve grok`）**: 15s 以内に `kazuki0205-84/grok` として登録され、5.3s で応答。ただし本文は「Not signed in. run `grok login --device-code`」。**Reason ではなくローカル認証で停止**（`evidence/17`）。
3. **REST 経路（hosted assistant が使う経路）**: 現行 OAuth 資格情報で `GET /v3/organizations/{org}/agent-network/agents` が 200 / 1.5s、`POST .../messages` が 6.65s で `answered`（`request_id` 付き）。**Grok Bot が使う HTTP 経路の成立は確認**（`evidence/22`）。

### 3.5 復旧

| 障害 | 挙動 | 証跡 |
| -- | -- | -- |
| daemon 再起動（launchctl kickstart） | 全セッション・worker が **約1s** で再登録。直後の依頼は 5.6s で成功 | [`20`](evidence/20-daemon-restart.txt), [`21`](evidence/21-post-restart.txt) |
| worker 停止 | 送信は `queued` で滞留。再起動後 6.3s で配送・実行1回 | [`07`](evidence/07-offline-queue.txt) |
| worker SIGKILL（実行中） | 再起動後に**再実行**して回答。副作用は二重になりうる | [`23`](evidence/23-crash-recovery.txt) |
| worker の自動再起動 | **なし**。SIGKILL 後は停止したまま（launchd plist は daemon のみ） | [`07`](evidence/07-offline-queue.txt) |
| Mac sleep / ネットワーク断 / Linux 再起動 / Grok box reset | **未検証**（Linux 機が offline、Grok Bot 未接続） | — |
| OAuth access token 期限 | 監査時点で 12:15Z 期限、refresh token あり。期限切れ時の挙動は未測定 | `~/.config/reason/credentials.json`（値は非記録） |

### 3.6 権限境界・承認

| 項目 | 実測 | 証跡 |
| -- | -- | -- |
| worker からのホーム書込 | `touch ~/k352-escape-test.txt` は `Operation not permitted`、`/tmp` は成功 | [`05`](evidence/05-codex-write-boundary.txt) |
| worker からのホーム読取 | `~/.ssh/config`、`~/.config/gh/hosts.yml`、`~/Library/Keychains`、`/etc/hosts` が **READABLE**。実行ユーザーは `adachi` | [`04`](evidence/04-codex-read-boundary.txt) |
| ローカル資格情報 | `~/.config/reason/credentials.json` は `secrets:read/write`, `ssh:write`, `devices:use`, `org:write` など **31 スコープ**。同一ユーザーから読める | §4 C1 |
| `inbound hold` | `default = "hold"` にしても、同一ユーザーの terminal からの送信は **素通り**（`HOLD-REACHED`）。`held` は空 | [`19`](evidence/19-inbound-hold.txt) |
| API キーの宛先制限 | 未検証（API キー未発行） | — |

## 4. 重大所見

**C1. worker は同一 OS ユーザーの資格情報を読める（重大）**
`--cwd` を Fixture に変えても、`~/.config/gh/hosts.yml`（GitHub token）、`~/.pi/agent/auth.json`、`~/.config/reason/credentials.json`（`secrets:read/write` を含む 31 スコープ）が読める。**Reason Network 経由で到達できる任意の peer は、これらを読ませる指示を出せる**。書込は `~` で止まるが、`/tmp` は書ける。→ 採用条件: 専用 OS ユーザー / コンテナ / VM で `serve` し、拒否テスト（対象 repo は読める・ホーム秘密は読めない）を記録すること。

**C2. `inbound hold` は承認ゲートにならない（重大）**
`default = "hold"` でも自己 identity の送信は即実行された。API キー（service user）でも同じかは未確認だが、「hold = 人間承認」と設計してはいけない。→ 承認が必要な作業は jobd 型の契約強制（K-343）で行う。

**C3. worker に監督プロセスがない（高）**
daemon は launchd `KeepAlive` で復帰するが、`serve codex` / `serve grok` は**手起動のまま**。SIGKILL されると停止し、依頼は mailbox に滞留する。復旧は「再起動」だが、SIGKILL 時の in-flight 依頼は**最初から再実行**されるため、副作用のある作業は冪等化が必要。

**C4. `TO` の遅延回答は失われる（中）**
`--timeout` 超過時は exit 1 で request id も返らない。`send` で id を取り `follow` する運用が必須。60 秒超の作業を `TO` で投げる設計は不可。

**C5. 無料 Reason Network への移行が未実施（中）**
本機は `reason network invite` が「workspace の network 上にいる」と答える状態で、`reason network switch` を実行していない。issue の Phase 0 は未達。切替はブラウザサインインとネットワーク選択を伴うため、本人の判断が必要。

**C6. Grok Bot は未検証のまま（高）**
hosted MCP の到達性・OAuth 要求・relay 稼働は確認したが、Grok Bot 画面からの `list_team` / `send_message` / `check_inbox`、wake、box reset 後の復帰は測れていない。Grok CLI も `grok login` 未了で回答不能。

**C7. 常設 Linux 受信側が存在しない（高）**
roster 上の他マシンは 19–21 日 offline。Done 条件 3 の「Linux 再起動」「常設受信」は環境がないため測定不能。

**C8. 一時送信元セッションが roster に残る（低）**
CLI の `TO`/`send` は `ask-xxxx` という送信元セッションを作り、10 分程度 roster に残る（本監査で 12 個）。`list_team` のノイズになる。運用では `who` のフィルタか、Pi/worker など固定セッションを宛先にする。

## 5. 費用境界（一次情報ベース）

- Reason Network は無料（カード・プラン不要、サインインのみ）。ネットワークエンジンは OSS（MIT/Apache-2.0）。
- 有料なのは Reason Cloud の Session。ネットワーク自体のメッセージングは課金対象ではない。
- 本監査では有料 Session を起動していない（`--cloud` 未使用、`serve` はローカルのみ）。**実費は 0 円の範囲**だが、Grok/Codex 側のモデル推論料金は別。
- 「無料 Network に移行した」とは言えない（C5）。

## 6. Done 条件との対照

| # | 条件 | 状態 | 根拠 |
| -- | -- | -- | -- |
| 1 | 4対象の接続マトリクスが実測で埋まる | **部分** | Codex/Pi/Kiro/REST は実測。Grok Bot と Kiro Crew UI は未検証。Kiro の公式非対応は「送信のみ・受信pull」として証拠付きで判定 |
| 2 | Grok Bot→Codex/Pi の実作業委譲、Kiro 経由の判定 | **部分** | Codex/Pi への実作業委譲は成功（Codex は独立照合済み）。**Grok Bot 起点は未実施**。Kiro→Codex は成功 |
| 3 | 常設 Linux / Mac / Grok Bot の復旧・権限境界・重複 | **未達** | daemon 復帰・offline queue・SIGKILL 再実行・権限境界は実測。Linux/sleep/断/Grok box reset は環境なし |
| 4 | 無料 Network と有料 Cloud の費用境界、採否、残余リスク | **達成** | §0, §5。判定は条件付き採用 |
| 5 | GitHub に再現手順・匿名化ログ・設定、Credential なし | **達成** | 本リポジトリ（証跡は `evidence/`） |

## 7. 残件（完了させるために必要なこと）

**本人（ブラウザ/認証が必要）**
1. `reason network switch` で無料 Reason Network へ移行し、`reason network invite` がリンクを返すことを確認。
2. Grok Bot に `https://mcp.reasonmachines.com/mcp` を追加（OAuth でサインイン、ネットワーク選択）。`list_team` → `send_message` → `check_inbox` を実行し、画面ログを保存。
3. `grok login --device-code`（または `XAI_API_KEY`）で Grok CLI を認証。
4. Reason API キーの最小スコープ（`run` + `sessions:read`）を発行し、旧過剰スコープ key の失効を確認（key 本文は記録しない）。

**実装（採用ゲート）**
5. `serve codex` を専用 OS ユーザー（またはコンテナ/VM）で起動し、`~/.ssh`, `~/.config/gh`, `~/.config/reason`, `~/Library/Keychains` が**読めない**ことを拒否テストで記録。
6. worker を launchd/systemd で監督（`KeepAlive`）。`serve` の二重起動防止と、SIGKILL 後の自動復帰を確認。
7. 依頼の冪等化（同一 request の再実行で副作用が重複しない）と、`send` + `follow` 前提のクライアント化。

**検証（環境が要る）**
8. Linux 常設機の再起動・ネットワーク断・24h offline からの復帰。
9. Mac sleep 中の配送と起床後の回収。
10. Grok Bot の box reset 後の認証・履歴・requests.log 保全。
11. OAuth token 期限切れ時の refresh 挙動（期限は 12:15Z。監査中は未到達）。

## 8. 再現手順

```sh
# 0) 前提: reason CLI と daemon
reason network doctor

# 1) Fixture repo
git clone <this repo> && cd 261110_k352-reason-network-audit/fixtures/k352-repo
git checkout .   # バグ入り calc.py に戻す
python3 -m unittest -v   # 1 failure

# 2) Codex worker（別端末）
cd <this repo>
reason network serve codex --cwd "$PWD/fixtures/k352-repo"

# 3) 委譲（別端末）
reason network <you>/codex "fix the bug in calc.py, run python3 -m unittest -v, reply with git diff and the test tail" --json
git -C fixtures/k352-repo diff   # 独立照合

# 4) オフライン→復帰
pkill -f "serve codex"
id=$(reason network send <you>/codex "reply OFFLINE-OK" --json | jq -r '.ids[0]')
reason network serve codex --cwd "$PWD/fixtures/k352-repo" &
reason network follow "$id" --timeout 120 --json

# 5) Pi（起動済みセッションへ）
reason network send <you>/<pi-session> "read-only ping: reply K352-PI-OK via send_message to <you>/terminal"

# 6) Kiro（検証後は remove する）
kiro-cli mcp add --name reason-network --command "$HOME/.reason/bin/reason-network" --args mcp
kiro-cli chat --no-interactive --trust-tools=reason-network__list_team \
  "Call the reason-network list_team tool and print its raw output."
kiro-cli mcp remove --name reason-network

# 7) REST 経路（hosted assistant 相当）
python3 scripts/rest_ask.py who
python3 scripts/rest_ask.py ask "reply K352-REST-OK"

# 8) 権限境界
reason network <you>/codex "report READABLE/NOT-READABLE for ~/.ssh/config ~/.config/gh/hosts.yml ~/Library/Keychains; do not print contents"
```

## 9. 付録: 証跡一覧

`evidence/INDEX.md` を参照。生ログはすべて匿名化済み（token 本文・secret 本文は含まない）。
