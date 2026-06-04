import unittest
from unittest.mock import patch, MagicMock

# Import the module under test
import llm_decompile_ablation


class TestAblationWorker(unittest.TestCase):

    def setUp(self):
        # Prepare a minimal dummy record for each test
        self.dummy_record = {
            "index": 999,
            "opt": "O2",
            "asm": "mov eax, 1",
            "cfg_dot": "digraph G {}",
            "cfg_lta": "[BLOCK: 0x0]"
        }

    # ---------------------------------------------------------
    # Scenario 1: API succeeds on first attempt
    # ---------------------------------------------------------
    @patch('llm_decompile_ablation.model.generate_content')
    def test_process_success(self, mock_generate):
        mock_response = MagicMock()
        mock_response.text = "int main() { return 1; } // mock result"
        mock_generate.return_value = mock_response

        result = llm_decompile_ablation.process_single_record(
            "base", self.dummy_record)

        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["refined_code"],
                         "int main() { return 1; } // mock result")
        self.assertEqual(mock_generate.call_count, 1)

    # ---------------------------------------------------------
    # Scenario 2: 429 error on first attempt, success on second
    # ---------------------------------------------------------
    @patch('llm_decompile_ablation.time.sleep')  # mock sleep to avoid real delays
    @patch('llm_decompile_ablation.model.generate_content')
    def test_process_retry_success_after_429(self, mock_generate, mock_sleep):
        mock_response = MagicMock()
        mock_response.text = "int main() { return 1; }"

        # First call raises 429, second call succeeds
        mock_generate.side_effect = [
            Exception("429 Resource exhausted. Please try again later."),
            mock_response
        ]

        result = llm_decompile_ablation.process_single_record(
            "base", self.dummy_record)

        self.assertEqual(result["status"], "OK")
        self.assertEqual(mock_generate.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    # ---------------------------------------------------------
    # Scenario 3: All retries fail with 503, returns failure without raising
    # ---------------------------------------------------------
    @patch('llm_decompile_ablation.time.sleep')
    @patch('llm_decompile_ablation.model.generate_content')
    def test_process_all_retries_fail_with_503(self, mock_generate, mock_sleep):
        mock_generate.side_effect = Exception(
            "503 recvmsg:Operation timed out")

        result = llm_decompile_ablation.process_single_record(
            "base", self.dummy_record)

        # Loop must self-terminate and return a failure record without raising
        self.assertEqual(result["status"], "ERROR: max retries exceeded")
        self.assertEqual(result["refined_code"], "// DECOMPILATION FAILED")
        self.assertEqual(mock_generate.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 3)

    # ---------------------------------------------------------
    # Scenario 4: Unexpected internal error (e.g., type error in prompt builder)
    # ---------------------------------------------------------
    @patch('llm_decompile_ablation.build_prompt')
    def test_process_critical_internal_error(self, mock_build_prompt):
        mock_build_prompt.side_effect = TypeError("simulated internal error")

        result = llm_decompile_ablation.process_single_record(
            "base", self.dummy_record)

        # Outer try-catch must absorb the error without killing the thread
        self.assertTrue("ERROR" in result["status"])
        self.assertEqual(result["refined_code"], "// CRITICAL ERROR")


if __name__ == '__main__':
    unittest.main()
