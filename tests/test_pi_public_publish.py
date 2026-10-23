"""Public publisher wiring sanity checks (no Pi access required)."""
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] /
          "scripts/pi_public_publish.sh").read_text(encoding="utf-8")


class PublisherTrainingIntegrationTests(unittest.TestCase):
    def test_dry_run_checks_training_without_apply(self):
        segment = SCRIPT.split('if [[ "$MODE" == "--dry-run" ]]; then', 1)[1]
        segment = segment.split('exit 0', 1)[0]
        self.assertIn("python3 scripts/pi_training_export.py", segment)
        self.assertNotIn("pi_training_export.py --apply", segment)

    def test_publisher_updates_trainings(self):
        self.assertIn("python3 scripts/pi_training_export.py --apply", SCRIPT)

    def test_bad_training_is_rolled_back(self):
        self.assertIn(
            "git restore --worktree -- data/training-berne.json data/training-farmsen.json",
            SCRIPT
        )

    def test_both_training_files_are_validated(self):
        self.assertIn("python3 -m json.tool data/training-berne.json", SCRIPT)
        self.assertIn("python3 -m json.tool data/training-farmsen.json", SCRIPT)

    def test_both_training_files_are_staged(self):
        staged = SCRIPT.split("git add -A -- ", 1)[1].split("\n", 2)
        combined = "".join(staged)
        self.assertIn("data/training-berne.json", combined)
        self.assertIn("data/training-farmsen.json", combined)

    def test_teams_preview_is_read_only(self):
        segment = SCRIPT.split('if [[ "$MODE" == "--dry-run" ]]; then', 1)[1]
        segment = segment.split('exit 0', 1)[0]
        self.assertIn("python3 scripts/pi_teams_export.py", segment)
        self.assertNotIn("pi_teams_export.py --apply", segment)

    def test_teams_apply_and_optional_git_staging(self):
        self.assertIn("python3 scripts/pi_teams_export.py --apply", SCRIPT)
        self.assertIn('if [[ -f data/teams.json ]]; then', SCRIPT)
        self.assertIn("git add -- data/teams.json", SCRIPT)

    def test_no_direct_pi_display_writes(self):
        self.assertNotIn("portrait-drive-sync.sh --", SCRIPT)
        self.assertNotIn("systemctl restart", SCRIPT)


if __name__ == "__main__":
    unittest.main()
