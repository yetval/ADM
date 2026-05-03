import unittest

from awsdockermanager.advisor import build_tips
from awsdockermanager.dockerctl import container_problems


class ScannerTests(unittest.TestCase):
    def test_container_problems_detects_down_and_exit_code(self) -> None:
        row = {"Status": "Exited (137) 2 minutes ago", "ExitCode": 137}

        self.assertEqual(container_problems(row), ["down", "exit-137"])

    def test_container_problems_detects_unhealthy_restart_and_oom(self) -> None:
        row = {
            "Status": "Restarting (1) 4 seconds ago",
            "Health": "unhealthy",
            "OOMKilled": True,
            "RestartCount": 7,
        }

        self.assertEqual(
            container_problems(row),
            ["restart-loop", "unhealthy", "oom-killed", "7-restarts"],
        )

    def test_advisor_warns_on_recent_log_errors(self) -> None:
        snapshot = {
            "docker": {"available": True},
            "system": {"disk": {"percent": 20}, "memory": {"percent": 20}, "load_percent": 10},
            "containers": [
                {
                    "Names": "api",
                    "Status": "Up 1 hour",
                    "Problems": [],
                    "LogErrors": ["fatal: database connection refused"],
                }
            ],
        }

        tips = build_tips(snapshot)

        self.assertTrue(any(tip["title"] == "Recent error logs found" for tip in tips))

    def test_advisor_marks_all_stopped_as_critical(self) -> None:
        snapshot = {
            "docker": {"available": True},
            "system": {"disk": {"percent": 20}, "memory": {"percent": 20}, "load_percent": 10},
            "containers": [{"Names": "worker", "Status": "Exited (1)", "Problems": ["down", "exit-1"]}],
        }

        tips = build_tips(snapshot)

        titles = {tip["title"] for tip in tips}
        self.assertIn("Containers exited with errors", titles)
        self.assertIn("No running containers", titles)


if __name__ == "__main__":
    unittest.main()
