#!/usr/bin/env bash
# 打印让用户本人登录百度网盘的命令。AI 不接触 BDUSS/STOKEN：只把这段输出交给用户。
BIN=${BPCS_BIN:-$HOME/.local/bin/BaiduPCS-Go}
printf -v BIN_Q '%q' "$BIN"
cat <<MSG
请在 $(hostname) 的终端里自己运行下面几行（输入不回显、不进 shell 历史；不要把值发到对话里）：

  read -rsp 'BDUSS: ' B; echo; read -rsp 'STOKEN（转存分享链接需要，可回车跳过）: ' S; echo
  $BIN_Q login -bduss="\$B" \${S:+-stoken="\$S"}; unset B S
  chmod 600 ~/.config/BaiduPCS-Go/pcs_config.json
  $BIN_Q who

BDUSS / STOKEN 在浏览器登录 pan.baidu.com 后的 Cookie 里（开发者工具 → 应用 → Cookie）：
  BDUSS 在 .baidu.com 域，STOKEN 在 pan.baidu.com 域。
登录态保存在 ~/.config/BaiduPCS-Go/pcs_config.json（含凭证，建议 chmod 600，不要拷到共享盘）。
做完回复「已登录」，我再用 who 复核。
MSG
