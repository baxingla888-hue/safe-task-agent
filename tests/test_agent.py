import json
import os
import tempfile
import unittest
from unittest.mock import patch

from agent import Agent, OfflinePlanner, is_safe


class AgentTests(unittest.TestCase):
    def test_planning(self):
        self.assertEqual(OfflinePlanner().plan("run: printf hi"), ["printf hi"])

    def test_interception(self):
        self.assertFalse(is_safe("rm -rf /"))
        self.assertFalse(is_safe("rm -rf /etc"))
        with self.assertRaises(ValueError): Agent(OfflinePlanner()).run("run: rm -rf /")

    def test_success_and_jsonl(self):
        with tempfile.NamedTemporaryFile(delete=False) as f: path = f.name
        try:
            with patch("sys.stderr"):
                self.assertEqual(Agent(OfflinePlanner()).run("run: echo ok", log_file=path), 0)
            with open(path, encoding="utf8") as f: self.assertEqual(json.loads(f.readline())["returncode"], 0)
        finally: os.unlink(path)

    def test_failure(self):
        self.assertNotEqual(Agent(OfflinePlanner()).run("run: exit 3"), 0)

    def test_dry_run_does_not_execute(self):
        self.assertEqual(Agent(OfflinePlanner()).run("run: touch created", dry_run=True), 0)


if __name__ == "__main__": unittest.main()
