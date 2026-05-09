# Git 工作流约定

## 推送分支

- 本仓库的所有改动默认推送到 `feature-pure-odd-even` 分支。
- 除非用户明确要求，否则不要推送到 `main` / `master`，也不要新建其他分支。
- 推送前使用 `git status` 确认仅提交相关改动；使用 `github_push_to_remote` 工具推送，不要直接 `git push`。
