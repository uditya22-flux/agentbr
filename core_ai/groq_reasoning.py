import os
import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


def generate_reasoning(dao) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "AI reasoning unavailable — GROQ_API_KEY not set."

    prompt = (
        f"You are a fintech compliance analyst reviewing an AI agent decision.\n\n"
        f"Agent: {dao.agent_name}\n"
        f"Action: {dao.action_type}\n"
        f"Input: {dao.input}\n"
        f"Output: {dao.output}\n"
        f"Risk Level: {dao.risk_level}\n"
        f"Flags: {dao.flag_reason}\n\n"
        f"The agent provided no reasoning. In 2-3 sentences, explain what likely happened "
        f"and why this decision is risky from an RBI compliance perspective."
    )

    try:
        r = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.3,
            },
            timeout=8,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"AI reasoning generation failed: {e}"
