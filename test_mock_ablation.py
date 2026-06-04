import time
import random
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 1. Mock Gemini model that simulates various failure modes
# ==========================================


class MockResponse:
    def __init__(self, text):
        self.text = text


class MockGenerativeModel:
    def generate_content(self, prompt):
        # Simulate network latency
        time.sleep(random.uniform(0.1, 0.5))

        # Roll for failure
        luck = random.random()
        if luck < 0.1:
            raise Exception("429 Resource exhausted")       # 10% chance
        elif luck < 0.2:
            raise Exception("503 recvmsg:Operation timed out")  # 10% chance
        elif luck < 0.25:
            raise ValueError("Simulated unexpected internal Python error")  # 5% chance

        return MockResponse("int main() { return 0; } // mock C++ output")


mock_model = MockGenerativeModel()

# ==========================================
# 2. Worker function with full error handling
# ==========================================


def process_single_record_mock(record):
    try:
        idx = record["index"]
        opt = record["opt"]

        # Deliberately trigger an error on record 5 to test outer loop resilience
        if idx == 5:
            raise TypeError("Intentional error to test main loop isolation")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = mock_model.generate_content("mock prompt")
                return {"index": idx, "opt_level": opt, "status": "OK"}
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "503" in error_msg or "timed out" in error_msg:
                    time.sleep(0.1)  # shortened for test speed
                else:
                    return {"index": idx, "opt_level": opt, "status": f"ERROR (unknown API error): {e}"}

        return {"index": idx, "opt_level": opt, "status": "ERROR: max retries exceeded"}

    except Exception as critical_error:
        return {"index": record.get("index", -1), "opt_level": "unknown", "status": f"CRITICAL ERROR: {critical_error}"}

# ==========================================
# 3. Stress test main loop
# ==========================================


def run_mock_test():
    # 20 dummy records
    dummy_records = [{"index": i, "opt": "O2", "asm": "nop"}
                     for i in range(1, 21)]

    print("========== Starting stress test ==========")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(
            process_single_record_mock, r): r for r in dummy_records}

        for future in as_completed(futures):
            try:
                result = future.result()
                print(f"  -> Index {result['index']:2} | {result['status']}")
            except Exception as loop_error:
                print(f"  -> UNHANDLED exception in main loop: {loop_error}")

    print("\n[*] Test complete. All records processed without crashing.")


if __name__ == "__main__":
    run_mock_test()
