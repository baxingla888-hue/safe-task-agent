#!/usr/bin/env python3
"""Tiny offline-first shell task agent."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class Planner(Protocol):
    def plan(self, task: str) -> list[str]: ...


class OfflinePlanner:
    """Conservative planner intended to work without network access."""
    def plan(self, task: str) -> list[str]:
        text = task.strip()
        if not text:
            raise ValueError("task cannot be empty")
        # Explicit shell snippets are useful for demos; each line is a step.
        if text.lower().startswith(("run:", "执行:", "shell:")):
            text = text.split(":", 1)[1]
        steps = [line.strip() for line in text.splitlines() if line.strip()]
        if len(steps) == 1 and ("&&" in steps[0] or ";" in steps[0]):
            steps = [x.strip() for x in re.split(r"&&|;", steps[0]) if x.strip()]
        if len(steps) == 1 and not re.search(r"[\s/\\]", steps[0]):
            # Natural language fallback remains harmless and deterministic.
            steps = ["printf '%s\\n' " + shlex.quote(text)]
        return steps


class OpenAIPlanner:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key, self.base_url, self.model = api_key, base_url.rstrip("/"), model

    def plan(self, task: str) -> list[str]:
        payload = {"model": self.model, "temperature": 0, "messages": [
            {"role": "system", "content": "Return JSON only: {\"steps\":[shell command strings]}. Keep steps safe and minimal."},
            {"role": "user", "content": task},
        ]}
        req = urllib.request.Request(self.base_url + "/chat/completions", data=json.dumps(payload).encode(),
                                     headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.load(response)
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        steps = parsed.get("steps")
        if not isinstance(steps, list) or not all(isinstance(x, str) and x.strip() for x in steps):
            raise ValueError("planner returned invalid steps")
        return steps


HIGH_RISK = [
    # Block any rm variant aimed at an absolute root path, not only the exact
    # `rm -rf /` spelling (being conservative is preferable here).
    re.compile(r"\brm\b[^\n;|]*\s+/", re.I),
    re.compile(r"\bmkfs(?:\.|\s|$)", re.I), re.compile(r"\bdd\s+if\s*=", re.I),
    re.compile(r"\b(?:shutdown|reboot)\b", re.I),
    re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash)\b", re.I),
]


def is_safe(command: str) -> bool:
    return not any(pattern.search(command) for pattern in HIGH_RISK)


@dataclass
class Agent:
    planner: Planner
    timeout: float = 10.0

    def run(self, task: str, dry_run: bool = False, log_file: str | None = None) -> int:
        steps = self.planner.plan(task)
        if any(not is_safe(step) for step in steps):
            raise ValueError("blocked high-risk command in plan")
        records = []
        with tempfile.TemporaryDirectory(prefix="task-agent-") as sandbox:
            for index, command in enumerate(steps, 1):
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                record = {"time": now, "step": index, "command": command}
                if dry_run:
                    record.update(result="dry-run", returncode=None)
                else:
                    if not is_safe(command):  # second check immediately before execution
                        raise ValueError("blocked high-risk command before execution")
                    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C", "HOME": sandbox}
                    try:
                        proc = subprocess.run(command, shell=True, cwd=sandbox, env=env,
                                              capture_output=True, text=True, timeout=self.timeout)
                        record.update(result=(proc.stdout + proc.stderr).strip(), returncode=proc.returncode)
                    except subprocess.TimeoutExpired as exc:
                        record.update(result=f"timeout after {self.timeout}s: {exc}", returncode=None)
                        records.append(record); self._log(record, log_file)
                        return 124
                records.append(record); self._log(record, log_file)
                if not dry_run and record["returncode"] != 0:
                    return int(record["returncode"])
        return 0

    @staticmethod
    def _log(record: dict, log_file: str | None) -> None:
        print(json.dumps(record, ensure_ascii=False), file=sys.stderr)
        if log_file:
            with open(log_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线优先的极简任务 Agent")
    parser.add_argument("--task", help="自然语言任务")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-file")
    args = parser.parse_args(argv)
    task = args.task or input("任务> ")
    if os.getenv("LLM_API_KEY"):
        planner: Planner = OpenAIPlanner(os.environ["LLM_API_KEY"], os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"), os.getenv("LLM_MODEL", "gpt-4o-mini"))
    else:
        planner = OfflinePlanner()
    try:
        return Agent(planner).run(task, args.dry_run, args.log_file)
    except (ValueError, KeyError, OSError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
