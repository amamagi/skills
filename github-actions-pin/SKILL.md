---
name: github-actions-pin
description: Pin GitHub Actions workflow dependencies to immutable commit SHAs for supply chain security, or update existing SHA pins to the latest version. Use this skill whenever the user wants to: pin GitHub Actions to specific SHAs, update pinned action SHAs to newer versions, replace version tags like @v4 or @v2 with commit hashes, audit action versioning in .github/workflows/ files, secure workflow files against supply chain attacks, or do anything related to SHA pinning/updating for GitHub Actions. Trigger on phrases like "pin actions", "pin workflows", "SHA pinning", "pin to SHA", "update action SHAs", "update pinned actions", "secure my workflow", "actions のバージョン固定", "SHAでpin", "アクションをピン留め", "最新SHAに更新", even if the user only mentions a specific file like "build-and-upload.yml を pin して".
---

## このスキルでできること

GitHub Actions ワークフローファイルに書かれたアクション参照を、変更不可能なコミットSHAに置き換えます。サプライチェーン攻撃対策として有効なセキュリティプラクティスです。

## 2つのモード

**Pin モード**（デフォルト）: バージョンタグ → SHA
```yaml
# Before
uses: actions/checkout@v4

# After
uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
```

**Update モード**: 既存のSHAを最新版のSHAに更新
```yaml
# Before
uses: actions/checkout@OLD_SHA # v4.1.0

# After
uses: actions/checkout@NEW_SHA # v4.2.2
```

## 手順

### Step 1: 対象ファイルを特定する

ユーザーがファイルを指定していない場合は `.github/workflows/` 以下を確認し、処理対象を確認する。

### Step 2: スクリプトを実行する

このスキルのディレクトリにある `scripts/pin_actions.py` を使う。

```bash
# Pin モード（タグ → SHA）
python ~/.claude/skills/github-actions-pin/scripts/pin_actions.py <workflow-file>

# Update モード（SHA を最新版に更新）
python ~/.claude/skills/github-actions-pin/scripts/pin_actions.py <workflow-file> --update

# ディレクトリ内の全ワークフローを処理
python ~/.claude/skills/github-actions-pin/scripts/pin_actions.py .github/workflows/ --all

# 変更内容をプレビュー（ファイルは変更しない）
python ~/.claude/skills/github-actions-pin/scripts/pin_actions.py <workflow-file> --dry-run
```

**Windows の場合:**
```powershell
python "$env:USERPROFILE\.claude\skills\github-actions-pin\scripts\pin_actions.py" <workflow-file>
```

### Step 3: 変更内容を報告する

何のアクションが、どのSHAに変換されたかをユーザーに伝える。

## 処理対象と動作

| 参照の種類 | Pin モード | Update モード |
|---|---|---|
| `owner/repo@vX.Y.Z`（タグ） | → SHA に変換 | → 最新版 SHA にピン留め |
| `owner/repo@SHA # vX.Y.Z`（済み） | スキップ | → 最新版SHA に更新 |
| `owner/repo@SHA`（コメントなし） | スキップ | → 最新版SHA に更新 |
| `owner/repo@main`（ブランチ） | → HEAD の SHA に変換 | → 最新 HEAD SHA に更新 |
| `./local/action`（ローカル） | スキップ | スキップ |
| `docker://image`（Docker） | スキップ | スキップ |

## 前提条件

- `gh` CLI がインストール済みかつ認証済み（`gh auth login`）
- Python 3.8+

## スクリプトが実行できない場合のフォールバック

Bash/PowerShell が使えない環境では、WebFetch で GitHub API を直接呼ぶことで同等の処理ができる。

```
# タグのSHAを取得（軽量タグの場合）
GET https://api.github.com/repos/{owner}/{repo}/git/ref/tags/{tag}
→ .object.sha がコミットSHA（typeが "tag" の場合は annotated tag → 次のステップが必要）

# Annotated tag のデリファレンス
GET https://api.github.com/repos/{owner}/{repo}/git/tags/{tag_object_sha}
→ .object.sha がコミットSHA

# 最新リリース取得（updateモード）
GET https://api.github.com/repos/{owner}/{repo}/releases/latest
→ .tag_name でタグ名を取得し、上記の方法でSHAを解決
```

`gh` CLI が使える場合は `gh api /repos/{owner}/{repo}/git/ref/tags/{tag}` でも同様。

## 注記事項

- Annotated tag（署名付きタグ）は API を2回呼ぶ（タグオブジェクト → コミットSHA）
- `gh` CLI の API レート制限に注意（通常は問題ない）
- ローカルアクション（`./`）と Docker アクションは自動でスキップされる
