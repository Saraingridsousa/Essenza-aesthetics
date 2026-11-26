import unittest
from backend import assistant

class AssistantTests(unittest.TestCase):
    def test_grounded_default(self):
        result=assistant.answer("price",model="")
        self.assertEqual(result["source"],"#duvidas")
        self.assertEqual(result["mode"],"knowledge")
    def test_model_approved(self):
        result=assistant.answer("agenda",model="test",transport=lambda model,facts:" ".join(reversed(facts)))
        self.assertEqual(result["mode"],"ollama")
    def test_model_hallucination_rejected(self):
        result=assistant.answer("price",model="test",transport=lambda model,facts:"O preço é R$ 200.")
        self.assertEqual(result["mode"],"fallback")
        self.assertNotIn("200",result["answer"])
    def test_failure_fallback(self):
        def failure(*args):
            raise TimeoutError()
        self.assertEqual(assistant.answer("services",model="test",transport=failure)["mode"],"fallback")
    def test_unknown_topic(self):
        for topic in ["diagnosis",None,["agenda"]]:
            with self.assertRaises(ValueError):
                assistant.answer(topic,model="test")

if __name__=="__main__":
    unittest.main()
