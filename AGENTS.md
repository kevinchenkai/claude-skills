# Repository instructions

## Git attribution

- Every commit created by Codex must end with:
  `Co-authored-by: Codex <codex@openai.com>`
- Keep the user's configured Git author and committer unchanged; Codex is a co-author only.
- Do not replace the email with a guessed bot `noreply` address. GitHub currently maps
  `codex@openai.com` to the official [`@codex`](https://github.com/codex) account.
- After pushing, verify the new commit through GitHub's `Commit.authors` GraphQL field.
  Do not use the cached Contributors count as the immediate acceptance check; see
  [docs/git-ai-attribution.md](docs/git-ai-attribution.md).
