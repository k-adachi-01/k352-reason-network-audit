# Runbook — ローカル Pi ↔ Grok Bot / Muse の双方向接続（K-352 完了条件）

2026-11-10 改定の完了条件を判定するための手順。所要 10–15 分。すべて無料の範囲で行う（Reason Cloud セッションは起動しない）。

## 0. 前提とネットワークの選び方

ホスト型アシスタントのメッセージは、**同じネットワーク上の自分のコンピュータ**を経由して届く。したがって次のどちらかに揃える。

- **A. 現状のまま**: Mac が参加している workspace network `kazuki0205-84` を、Grok Bot / Muse の同意画面でも選ぶ。
- **B. 無料 Reason Network に移す**: Mac で `reason network switch` を実行してネットワークを作成（または招待リンクで参加）し、**その新しいネットワーク**を Grok Bot / Muse の同意画面で選ぶ。`reason network invite` がリンクを返せば B への移行完了。

> 現状は A。B にする場合は、切替後に Mac の Pi セッションを再起動して再登録させる。

## 1. アシスタントをネットワークに参加させる

両方とも同じアカウントでサインインし、0 で決めたネットワークを選ぶ。

- **Grok Bot**: MCP サーバー `https://mcp.reasonmachines.com/mcp` を追加 → OAuth でサインイン → 同意画面でネットワークを選択。
- **Muse**: コネクタに同じ URL を追加 → サインイン → ネットワークを選択。

CLI をクラウド側にインストールしない（それは自分のコンピュータではない）。

## 2. 参加の確認（Mac 側）

```sh
reason network who
```

Grok Bot / Muse がセッションとして現れることを確認する。アドレスは `kazuki0205-84/<name>` の形。名前が分からない場合は `reason network who --json | jq '.sessions[] | {address, agent, tier}'` で引く。

## 3. 往復テスト（Pi 側から）

Pi のセッションで、Reason Network の MCP ツールを使って次を行う。`<nonce>` は英数字8桁の乱数。

1. `list_team` で宛先（Grok Bot または Muse）のアドレスを確認
2. `send_message` で次を送る

```
K-352 round-trip test. Nonce: <nonce>. Reply with exactly: K352-ACK <nonce>
```

3. `message_status` を 5 秒間隔で poll、または `check_inbox` で返信を回収
4. 返信本文が `K352-ACK <nonce>` と一致することを確認

Muse でも同じ手順を nonce を変えて実施する。

## 4. 記録する項目

| 項目 | 例 |
| -- | -- |
| ネットワーク名 | `kazuki0205-84` または新規作成した名前 |
| 認証・同意の経路 | hosted MCP の OAuth 同意（選んだネットワーク） |
| 宛先アドレス | `kazuki0205-84/<assistant>` |
| 送信→返信の秒数 | `send_message` 実行から返信回収まで |
| つまずいた点 | 宛先が見えない／同意画面にネットワークが出ない 等 |

証跡は `evidence/` に追記し、token 本文・OAuth コードは残さない。

## 5. うまくいかないときの切り分け

| 症状 | 見るところ |
| -- | -- |
| `list_team` にアシスタントが出ない | アシスタント側で MCP が「接続済み」か、同意画面でネットワークを選んだか。Mac 側が同じネットワークか（`reason network doctor` の team 名） |
| 宛先は見えるが `send_message` が失敗 | アドレスの綴り。相手が接続を切っていないか。`reason network who --all` で offline でないか |
| 送ったが返信が来ない | アシスタントが `check_inbox` を呼ぶまで読まれない（push ではない）。アシスタント側で受信を促す |
| Pi 側にツールが出ない | Pi を再起動（`~/.pi/agent/extensions/reason-network.ts` は起動時に MCP を登録する） |
| ネットワークが一致しない | Mac とアシスタントで同じネットワークを選ぶ。必要なら `reason network invite` のリンクで揃える |
