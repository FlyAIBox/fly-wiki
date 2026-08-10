#!/bin/sh
# ensure-cli.sh —— 确认本机可用的 mirofish CLI,没有才从固定地址安装。
#
# 默认根本不该跑这个脚本:eval 默认全程不碰 mirofish CLI(不探测、不安装、不登录、
# 不回写),本地 session 就是完整留痕。只有用户明确要求接平台留档时才执行它。
#
# 解析顺序(先到先用,绝不覆盖已有安装):
#   1. $MIROFISH_BIN        显式指定的可执行文件(本地开发构建优先用这个,或 npm link)
#   2. PATH 上的 mirofish    已装版本 / npm link 的开发版
#   3. 都没有 → npm install -g $MIROFISH_CLI_URL(默认平台自托管 tarball)
#
# 只装缺失,不做升级:升级判断留给人(mirofish doctor 会提示)。退出码 0 = CLI 可用。
set -u

CLI_URL="${MIROFISH_CLI_URL:-https://api.mirofish.ai/connect/cli.tgz}"

ok() { echo "mirofish CLI 就绪:$1(版本 $2)"; exit 0; }

if [ -n "${MIROFISH_BIN:-}" ]; then
  if v=$("$MIROFISH_BIN" --version 2>/dev/null); then ok "$MIROFISH_BIN" "$v"; fi
  echo "MIROFISH_BIN 指向的文件无法运行:$MIROFISH_BIN" >&2
  exit 1
fi

if command -v mirofish >/dev/null 2>&1; then
  if v=$(mirofish --version 2>/dev/null); then ok "$(command -v mirofish)" "$v"; fi
  echo "PATH 上的 mirofish 无法运行($(command -v mirofish)),先修复或删除它再重试" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "缺少 Node.js(需要 >=20)。macOS 可执行:brew install node" >&2
  exit 1
fi
major=$(node -v | sed 's/^v//' | cut -d. -f1)
if [ "$major" -lt 20 ]; then
  echo "Node.js 版本过低($(node -v),需要 >=20)。macOS 可执行:brew upgrade node" >&2
  exit 1
fi

echo "本机没有 mirofish CLI,从 $CLI_URL 安装 ..."
if ! npm install -g "$CLI_URL"; then
  echo "安装失败。手动执行:npm install -g $CLI_URL" >&2
  exit 1
fi

if v=$(mirofish --version 2>/dev/null); then ok "$(command -v mirofish)" "$v"; fi
echo "安装完成但 PATH 上仍找不到 mirofish —— 新开一个 shell,或检查 npm 全局 bin 目录是否在 PATH(npm bin -g)" >&2
exit 1
