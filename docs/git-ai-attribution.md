# Git AI 协作署名与核验

## 结论

Codex 创建提交时，保留仓库原有的人类 author 和 committer，并在提交消息末尾添加：

```text
Co-authored-by: Codex <codex@openai.com>
```

截至 2026-08-27，GitHub 会把 `codex@openai.com` 解析为 OpenAI 官方账号
[`@codex`](https://github.com/codex)。这个 trailer 表示共同作者归属，目标是让
Codex 出现在 GitHub 的提交作者和 Contributors 统计中；它不是 GPG/SSH
`Verified` 加密签名。

## 为什么 Contributors 可能暂时看不到 Codex

GitHub 的 Contributors 页面不是实时判据。特别是提交经过 amend、rebase 或
force-push 等历史重写后，GitHub 官方说明贡献者统计可能需要约 24 小时刷新。

本仓库在 2026-08-27 进行历史重写后，`main` 上的以下三个提交都已带正确 trailer：

- `d2cb75d` — `feat(wps365-cli): add safe markdown bold repair`
- `c247ce5` — `feat(wps365-cli): harden short links and search routing`
- `c73c9ab` — `docs: require Codex commit attribution`

GitHub GraphQL 已能把这些提交的两个作者分别解析为 `@kevinchenkai` 和
`@codex`。因此如果提交页/API 已识别 `@codex`、但仓库首页仍只显示旧的
Contributors 数量，应先按缓存延迟处理，不应继续改邮箱或反复重写历史。

## 推送后的即时核验

先确认本地提交消息：

```bash
git show -s --format='%H%n%an <%ae>%n%B' HEAD
```

再用 GitHub GraphQL 查询服务端实际识别到的所有作者：

```bash
oid=$(git rev-parse HEAD)
gh api graphql \
  -f owner=kevinchenkai \
  -f name=claude-skills \
  -f oid="$oid" \
  -f query='query($owner:String!,$name:String!,$oid:GitObjectID!){
    repository(owner:$owner,name:$name){
      object(oid:$oid){
        ... on Commit {
          oid
          authors(first:10){nodes{name email user{login url}}}
        }
      }
    }
  }' \
  --jq '.data.repository.object'
```

验收标准：`authors.nodes` 同时包含当前人类作者和以下 Codex 映射：

```json
{
  "email": "codex@openai.com",
  "name": "Codex",
  "user": {
    "login": "codex",
    "url": "https://github.com/codex"
  }
}
```

这个结果证明 trailer 已推送且邮箱已映射到 GitHub 账号。Contributors 页面只作为
延迟后的最终展示核验；历史重写后至少等待 24 小时，再决定是否联系 GitHub Support。

## Claude

Claude 同样保留人类 author/committer，并使用 Anthropic 的 GitHub 映射邮箱：

```text
Co-authored-by: Claude <noreply@anthropic.com>
```

如果 Claude Code 自动生成的 trailer 使用具体模型名，但邮箱仍为
`noreply@anthropic.com`，视为等价署名，不要重复添加第二条。
