# 极简离线任务 Agent

这是一个仅使用 Python 标准库的 CLI。它接收自然语言任务，由可插拔 Planner 生成 shell 步骤，并在临时沙箱中逐步执行。

运行时固定为 Python 3.11（见 `.python-version`），依赖集合记录在 `requirements.lock`；当前为空，因为项目只使用标准库。

## 安装、运行、测试、部署

```bash
python3.11 -m venv .venv && . .venv/bin/activate
python -m unittest discover -s tests -v
python agent.py --task "run: printf hello"
python agent.py --dry-run --task "run: printf hello" --log-file run.jsonl
printf 'run: printf interactive\\n' | python agent.py
docker build -t offline-task-agent .
docker run --rm offline-task-agent --task "run: printf hello"
```

不设置 `LLM_API_KEY` 时使用离线规则 Planner；设置 `LLM_API_KEY` 后使用 OpenAI-compatible `/chat/completions`，配置 `LLM_BASE_URL`、`LLM_MODEL`（参见 `.env.example`）。密钥只从环境变量读取。

## 安全边界

拒绝 `rm -rf /`、`rm -rf /*`、`mkfs`、`dd if=`、`shutdown/reboot` 和 `curl/wget | sh/bash` 等高风险命令；规划完成后和每一步实际执行前各检查一次。命令在临时目录、最小化环境（固定 PATH、LANG、HOME）中运行，每步默认 10 秒超时。`shell=True` 意味着 Planner 输出仍可执行普通 shell 语法，因此不要把不可信 Planner 当作安全策略；本工具不提供宿主机文件访问权限隔离，Docker 非 root 运行可进一步降低影响。日志写入 stderr，也可用 `--log-file` 追加 JSONL。
