import os
import httpx
from typing import List, Dict, Any, Optional

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

def generate_auto_reasoning(agent_name: str, action_type: str, input_data: Any, output: str) -> str:
    """
    AI Feature 1 — Auto Reasoning Generation (Groq)
    Generates a concise, professional reasoning for an RBI-regulated audit log.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "Reasoning required by RBI Clause 3.1 — Failed to generate (GROQ_API_KEY missing)."

    prompt = f"""You are a compliance reasoning engine for an RBI-regulated AI agent.

A financial AI agent submitted a decision log with NO reasoning field.
You must generate a concise, professional reasoning explanation based 
on the decision data provided.

Decision data:
- Agent: {agent_name}
- Action: {action_type}
- Input: {input_data}
- Output: {output}

Rules:
- Reasoning must be 1-3 sentences
- Must reference key input fields (amount, KYC status, confidence)
- Must explain WHY the action was taken
- Must be audit-ready for RBI inspection
- Do NOT fabricate data not present in the input

Return ONLY the reasoning string. No preamble, no JSON.
"""
    try:
        r = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.2
            },
            timeout=10
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Reasoning generation failed: {str(e)}"

def query_compliance_analyst(question: str, log_summary: str, incidents: str) -> str:
    """
    AI Feature 2 — Natural Language Query Engine (Groq)
    Answers a compliance officer's question using only specified data.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return "Analysis failed: GROQ_API_KEY missing."

    prompt = f"""You are AgentBridge, an RBI compliance analyst AI.

You have access to the following log summary data:
{log_summary}

Recent incidents:
{incidents}

A compliance officer has asked:
"{question}"

Rules:
- Answer ONLY based on the data provided above
- Be specific — cite numbers, agent names, dates where available
- If the data is insufficient to answer, say so clearly
- Format: 2-4 sentences of plain English
- Do NOT hallucinate data not present in the summary
- Flag if the answer reveals a regulatory risk

Return ONLY the answer string.
"""
    try:
        r = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.2
            },
            timeout=10
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Analysis query failed: {str(e)}"
