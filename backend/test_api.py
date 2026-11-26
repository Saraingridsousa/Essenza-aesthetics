import tempfile
import unittest
from pathlib import Path
from backend import api

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"test.sqlite3"
        api.init(self.path)
        self.data={"name":"Demo Exemplo","email":"demo@example.com","service":"Limpeza de pele","consent":True}
    def test_duplicate_and_outbox(self):
        first,created=api.capture(self.path,self.data)
        self.assertTrue(created)
        self.assertEqual(api.capture(self.path,{**self.data,"email":"DEMO@example.com"}),(first,False))
        self.assertEqual(api.metrics(self.path)["total"],1)
        self.assertEqual(api.metrics(self.path)["outbox"],{"pending":1})
    def test_validation(self):
        for changes in [{"email":"actual@gmail.com"},{"consent":False},{"service":"unknown"},{"period":"unknown"}]:
            with self.assertRaises(ValueError):
                api.capture(self.path,{**self.data,**changes})
        self.assertEqual(api.metrics(self.path)["total"],0)
    def test_retry_and_lease(self):
        api.capture(self.path,self.data)
        import time
        now=int(time.time())
        first=api.claim(self.path,now)
        self.assertIsNone(api.claim(self.path,now))
        self.assertFalse(api.finish(self.path,first["id"],"wrong",True,now))
        self.assertTrue(api.finish(self.path,first["id"],first["lease"],False,now))
        self.assertIsNone(api.claim(self.path,now))
        second=api.claim(self.path,now+2)
        self.assertEqual(second["id"],first["id"])
        self.assertNotEqual(second["lease"],first["lease"])
        self.assertFalse(api.finish(self.path,first["id"],first["lease"],True,now+2))
        self.assertTrue(api.finish(self.path,second["id"],second["lease"],True,now+2))
        self.assertEqual(api.metrics(self.path)["outbox"],{"sent":1})
    def test_exhausted_retries(self):
        api.capture(self.path,self.data)
        import time
        now=int(time.time())
        for attempt in range(1,api.MAX_ATTEMPTS+1):
            e=api.claim(self.path,now)
            self.assertEqual(e["attempts"],attempt)
            self.assertTrue(api.finish(self.path,e["id"],e["lease"],False,now))
            now+=2**attempt
        self.assertIsNone(api.claim(self.path,now))
        self.assertEqual(api.metrics(self.path)["outbox"],{"failed":1})
    def test_expired_claim_can_be_recovered(self):
        api.capture(self.path,self.data)
        import time
        now=int(time.time())
        first=api.claim(self.path,now)
        self.assertFalse(api.finish(self.path,first["id"],first["lease"],True,now+120))
        second=api.claim(self.path,now+120)
        self.assertEqual(second["id"],first["id"])
        self.assertNotEqual(second["lease"],first["lease"])

if __name__=="__main__":
    unittest.main()
