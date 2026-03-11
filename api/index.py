import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from agent import MODEL, SYSTEM_PROMPT, available_functions, build_client, tools

app = Flask(__name__)


MAX_HISTORY_MESSAGES = 24
MAX_TOOL_ROUNDS = 8


def _normalize_history(raw_history: Any) -> List[Dict[str, str]]:
    if not isinstance(raw_history, list):
        return []

    cleaned: List[Dict[str, str]] = []
    for item in raw_history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"}:
            continue
        if not content:
            continue
        cleaned.append({"role": role, "content": content})

    return cleaned[-MAX_HISTORY_MESSAGES:]


def _safe_json_string(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=True)


def _execute_tool(func_name: str, raw_args: str) -> Dict[str, Any]:
    if func_name not in available_functions:
        return {
            "status": "error",
            "tool": func_name,
            "result": {"status": "error", "message": f"Unknown tool: {func_name}"},
        }

    try:
        parsed_args = json.loads(raw_args or "{}")
        if not isinstance(parsed_args, dict):
            parsed_args = {}
    except json.JSONDecodeError:
        parsed_args = {}

    try:
        raw_result = available_functions[func_name](**parsed_args)
        result_json = _safe_json_string(raw_result)
    except Exception as exc:
        result_json = json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=True)

    try:
        parsed_result = json.loads(result_json)
    except json.JSONDecodeError:
        parsed_result = {"status": "error", "message": "Tool returned non-JSON output."}

    return {"status": "ok", "tool": func_name, "args": parsed_args, "result": parsed_result}


@app.after_request
def _add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/chat", methods=["OPTIONS"])
def chat_options():
    return ("", 204)


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt", "")).strip()
    history = _normalize_history(payload.get("history", []))

    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    try:
        client = build_client()
    except Exception as exc:
        return jsonify({"error": f"Startup error: {exc}"}), 500

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    tool_events: List[Dict[str, Any]] = []
    final_text = ""

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.4,
            )
            response_message = response.choices[0].message

            if response_message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": response_message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in response_message.tool_calls
                        ],
                    }
                )

                for tool_call in response_message.tool_calls:
                    event = _execute_tool(tool_call.function.name, tool_call.function.arguments or "{}")
                    tool_events.append(event)
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": _safe_json_string(event.get("result", {})),
                        }
                    )
                continue

            final_text = response_message.content or ""
            break
        else:
            final_text = "I could not finish the request in time. Please retry with a shorter prompt."
    except Exception as exc:
        return jsonify({"error": f"Model request failed: {exc}"}), 502

    updated_history = (history + [{"role": "user", "content": prompt}, {"role": "assistant", "content": final_text}])[
        -MAX_HISTORY_MESSAGES:
    ]

    return jsonify({"reply": final_text, "history": updated_history, "tool_events": tool_events})


@app.route("/", methods=["GET"])
def root():
    return jsonify({"message": "DeskPilot API is running.", "health": "/api/health", "chat": "/api/chat"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
