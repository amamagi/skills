---
name: create-pr
description: Create or update a GitHub PR with a body generated from the project's PR template. Use when the user asks to create a PR, write a PR description, or post a PR. Triggers on phrases like "PRを作って", "PR本文を書いて", "PRに反映して", "PRを出して", "write PR", "create PR", "open PR", "draft PR body". Also use when the user asks to "write the PR body following the template" or wants the PR to reflect current changes — even if the word "PR" is the only cue in the message.
---

# PR作成・更新スキル

現在のブランチの変更を分析し、プロジェクトのPRテンプレートに沿ったPR本文を生成してGitHubに反映する。

## 手順

### 1. 現状把握（並行実行）

```bash
git branch --show-current
git log main..HEAD --oneline
gh pr list --head $(git branch --show-current) --json number,title,body,state
```

### 2. 変更内容の把握

既存PRがある場合：
```bash
gh pr diff <番号>
```

PRがない場合：
```bash
git diff main...HEAD --stat
git diff main...HEAD
```

差分が大きい場合は `--stat` で全体像を把握してから重要ファイルだけ読む。

### 3. PRテンプレートの読み込み

以下のパスを順に確認する：
- `.github/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/PULL_REQUEST_TEMPLATE/*.md`

テンプレートが見つかった場合はそのセクション構成を忠実に守る。
テンプレートがない場合はデフォルト構成（概要 / 変更内容 / 動作確認）を使う。

### 4. PR本文の生成

テンプレートの各セクションを変更内容に基づいて埋める。

**タイトルの形式：** `<type>: <概要>`
- `feat`: 新機能
- `fix`: バグ修正
- `ci`: CI/CD
- `refactor`: リファクタリング
- `docs`: ドキュメント

**本文を書くときの指針：**
- 「概要」には「何を変えたか」ではなく「なぜ変えるか」を書く
- 「変更内容」は箇条書きで主要な変更点を列挙する
- 「動作確認」はチェックボックス形式で、レビュアーが実際に確認すべき観点を書く
- テンプレートにないセクションは追加しない

### 5. ユーザーへの確認

生成したタイトルと本文をチャットに表示してユーザーに確認を求める。
**投稿・更新はユーザーの承認を得てから行う。**

```
以下の内容でPRを作成（or 更新）します。問題なければ「OK」と返信してください。

タイトル: <タイトル>

---
<本文>
---
```

### 6. PRへの反映

ユーザーが承認したら実行する。本文はheredocで渡す（クォートの問題を防ぐため）。

**PRが存在しない場合（新規作成）：**
```bash
gh pr create --title "タイトル" --body "$(cat <<'EOF'
本文
EOF
)"
```

**PRが既存の場合（本文更新）：**
```bash
gh pr edit <番号> --title "タイトル" --body "$(cat <<'EOF'
本文
EOF
)"
```

反映後にPRのURLを出力してユーザーに知らせる。
