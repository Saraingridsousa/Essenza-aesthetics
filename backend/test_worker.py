import tempfile
import unittest
from pathlib import Path
from backend import api, worker

class WorkerTests(unittest.TestCase):
    def test_process_and_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"test.sqlite3"
            api.init(path)
            api.capture(path,{"name":"Demo","email":"demo@example.com","service":"Limpeza de pele","consent":True,"campaign":"Instagram"})
            result=worker.process(path)
            self.assertTrue(result[0]["acknowledged"])
            self.assertEqual(worker.process(path),[])
            report=worker.report(path)
            self.assertEqual(report["outbox"],{"sent":1})
            self.assertEqual(report["by_campaign"][0]["campaign"],"Instagram")
            self.assertEqual(report["by_month_utc"][0]["leads"],1)
