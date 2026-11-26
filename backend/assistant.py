"""Optional local LLM composition of approved administrative facts.

The model receives an allowlisted topic's approved sentences, never the raw
visitor question or a lead record. Unapproved output is discarded.
"""
import json
import os
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

KNOWLEDGE = {
    "agenda": ("#agendamento", ("Escolha um procedimento ou uma avaliação geral no formulário fictício.", "Não há reserva ou atendimento real.")),
    "services": ("#procedimentos", ("O site apresenta categorias facial, corporal e de bem-estar.", "A indicação de procedimentos exige avaliação de um profissional responsável.")),
    "price": ("#duvidas", ("A demonstração não possui preços nem horários reais.", "Uma clínica contratante forneceria essas informações.")),
    "privacy": ("#agendamento", ("Use somente dados fictícios.", "No modo integrado, os registros ficam no SQLite desta máquina e não são enviados externamente.")),
    "brand": ("#contato", ("Essenza é uma marca fictícia de portfólio.", "Não há endereço, WhatsApp ou atendimento real."))
}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def request_model(model, facts):
    prompt = ("Você compõe respostas administrativas. Use exatamente as duas frases autorizadas, "
              "sem modificar palavras ou pontuação. Pode escolher a ordem. Não acrescente texto.\n"
              + "\n".join(facts))
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "num_predict": 150}}).encode()
    # Fixed loopback destination; no ambient proxy and no redirects.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    req = Request("http://127.0.0.1:11434/api/generate", data=body,
                  headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=15) as response:
        return json.loads(response.read(32768))["response"]

def answer(topic, model=None, transport=request_model):
    if not isinstance(topic, str) or topic not in KNOWLEDGE:
        raise ValueError("Unknown administrative topic")
    source, facts = KNOWLEDGE[topic]
    fallback = " ".join(facts)
    model = model if model is not None else os.environ.get("ESSENZA_OLLAMA_MODEL", "")
    if not model:
        return {"answer":fallback,"source":source,"mode":"knowledge"}
    try:
        candidate = " ".join(transport(model, facts).split())
        approved = {fallback, " ".join(reversed(facts))}
        if candidate in approved:
            return {"answer":candidate,"source":source,"mode":"ollama"}
    except Exception:
        pass
    return {"answer":fallback,"source":source,"mode":"fallback"}
