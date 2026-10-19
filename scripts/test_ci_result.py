"""Guard the aggregate CI result job without requiring a YAML dependency."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/validate.yml"
CLA_WORKFLOW = ROOT / ".github/workflows/cla.yml"


def job_names(source):
    """Return job keys from the top-level jobs mapping."""
    lines = source.splitlines()
    jobs_line = next(
        index for index, line in enumerate(lines) if line.rstrip() == "jobs:"
    )
    names = []
    for line in lines[jobs_line + 1 :]:
        if line and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            names.append(match.group(1))
    return names


def job_block(source, job):
    """Return one two-space-indented job's body."""
    match = re.search(
        rf"(?ms)^  {re.escape(job)}:\s*\n(.*?)(?=^  [A-Za-z0-9_-]+:\s*$|\Z)",
        source,
    )
    if not match:
        raise AssertionError(f"missing job: {job}")
    return match.group(1)


def has_merge_group_trigger(source):
    """Check the top-level trigger block for a checks_requested merge group."""
    trigger = source.split("\npermissions:", 1)[0]
    return bool(
        re.search(
            r"(?m)^  merge_group:\s*$\n^    types:\s*\[checks_requested\]\s*$",
            trigger,
        )
    )


class CIResultTest(unittest.TestCase):
    def setUp(self):
        self.source = WORKFLOW.read_text(encoding="utf-8")

    def test_ci_result_needs_every_other_job(self):
        jobs = set(job_names(self.source))
        self.assertIn("ci-result", jobs)
        block = job_block(self.source, "ci-result")
        needs_match = re.search(r"(?m)^    needs:\s*\[([^]]*)\]\s*$", block)
        self.assertIsNotNone(needs_match, "ci-result needs must use an inline list")
        needs = {
            item.strip() for item in needs_match.group(1).split(",") if item.strip()
        }
        self.assertEqual(jobs - {"ci-result"}, needs)

    def test_ci_result_always_runs(self):
        self.assertRegex(job_block(self.source, "ci-result"), r"(?m)^    if: always\(\)$")

    def test_workflow_triggers_on_merge_group(self):
        self.assertTrue(has_merge_group_trigger(self.source))
        if CLA_WORKFLOW.exists():
            self.assertTrue(has_merge_group_trigger(CLA_WORKFLOW.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
