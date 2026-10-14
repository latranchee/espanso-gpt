import tempfile
import unittest
from pathlib import Path

import logger


class EnsureLoggerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.logs_dir = tempfile.TemporaryDirectory()
        (Path(self.logs_dir.name) / "archives").mkdir()
        self.original_logs_dir = logger._logs_dir
        logger._logs_dir = Path(self.logs_dir.name)

    def tearDown(self) -> None:
        logger.close_logger()
        logger._logs_dir = self.original_logs_dir
        self.logs_dir.cleanup()

    def test_keeps_the_active_log(self) -> None:
        logger.init_logger("push_to_talk")
        logger.ensure_logger("llm_client")
        self.assertEqual(logger._module_name, "push_to_talk")

    def test_starts_a_log_when_none_is_open(self) -> None:
        logger.close_logger()
        logger.ensure_logger("llm_client")
        self.assertTrue((Path(self.logs_dir.name) / "llm_client.log").exists())


if __name__ == "__main__":
    unittest.main()
