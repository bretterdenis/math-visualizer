use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

const MODEL: &str = "claude-sonnet-5-5";
const API_URL: &str = "https://api.anthropic.com/v1/messages";

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ChatMessage {
    pub role: String, // "user" | "assistant"
    pub content: Value,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub enum ClaudeReply {
    Plot(Value),
    Text(String),
}

fn plot_tool_definition() -> Value {
    json!({
        "name": "render_plot",
        "description": "Render a mathematical function visualization. Call this whenever the user describes, asks for, or modifies a function to plot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["2d", "3d"],
                    "description": "2d for y = f(x), 3d for z = f(x, y) surfaces"
                },
                "title": {
                    "type": "string",
                    "description": "Short label for what the function is or resembles, e.g. 'Cubic function'"
                },
                "subtitle": {
                    "type": "string",
                    "description": "The function written as valid LaTeX, e.g. 'f(x) = x^3 - 3x'"
                },
                "description": {
                    "type": "string",
                    "description": "Longer explanatory text about the function; may contain inline LaTeX using \\(...\\) or $...$ delimiters"
                },
                "suggested_topic": {
                    "type": "string",
                    "description": "Best-guess category name for organizing this function in the user's library, e.g. 'Polynomial functions'. This is only a suggestion the user can override."
                },
                "variables": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "['x'] for 2d, ['x', 'y'] for 3d"
                },
                "domain": {
                    "type": "object",
                    "properties": {
                        "xMin": { "type": "number" },
                        "xMax": { "type": "number" },
                        "yMin": { "type": "number" },
                        "yMax": { "type": "number" }
                    },
                    "required": ["xMin", "xMax"],
                    "description": "yMin/yMax only required for kind=3d (range of the second variable)"
                },
                "traces": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "expr": {
                                "type": "string",
                                "description": "mathjs-compatible expression using the declared variables, e.g. 'sin(x)*exp(-x/10)' or 'sin(sqrt(x^2+y^2))'"
                            },
                            "label": { "type": "string" }
                        },
                        "required": ["expr"]
                    },
                    "description": "One or more functions to overlay (2d) or a single surface (3d)"
                }
            },
            "required": ["kind", "title", "subtitle", "description", "suggested_topic", "variables", "domain", "traces"]
        }
    })
}

fn system_prompt() -> &'static str {
    "You are a math visualization assistant embedded in a desktop app. \
    When the user describes, requests, or modifies a mathematical function, call the \
    render_plot tool with a valid specification. Use mathjs-compatible syntax in expressions \
    (^ for power, standard function names like sin, cos, exp, log, sqrt, abs). Pick a sensible \
    default domain (e.g. -10 to 10) unless the user specifies one or the function implies a \
    natural range. For follow-up requests like 'zoom out' or 'add cos(x) too', adjust the \
    previous plot accordingly rather than starting over, using the conversation history. \
    If the request is ambiguous or not about plotting a function, ask a brief clarifying \
    question in plain text instead of calling the tool. \
    The 2d plot can only show one y value per x, so implicit or multi-valued relations \
    (e.g. a circle x^2+y^2=r^2, or an ellipse) must be split into separate traces for each \
    branch (e.g. 'sqrt(r^2-x^2)' and '-sqrt(r^2-x^2)' with the domain limited to [-r, r]) so \
    the full curve is covered. The x and y axes are rendered with equal scale by default, so \
    shapes like circles will appear geometrically correct. \
    Every render_plot call must also include: title (a short label for what the function is or \
    resembles), subtitle (the function written as valid LaTeX), description (longer explanatory \
    text, which may use inline LaTeX with \\(...\\) or $...$ delimiters), and suggested_topic \
    (your best-guess category name for organizing this function, e.g. 'Polynomial functions'). \
    The user can edit or override suggested_topic before saving it to their library, so treat it \
    as a helpful guess rather than a final answer."
}

pub async fn ask(
    client: &reqwest::Client,
    api_key: &str,
    history: &[ChatMessage],
) -> Result<ClaudeReply, String> {
    let body = json!({
        "model": MODEL,
        "max_tokens": 1024,
        "system": system_prompt(),
        "tools": [plot_tool_definition()],
        "messages": history,
    });

    let resp = client
        .post(API_URL)
        .header("x-api-key", api_key)
        .header("anthropic-version", "2023-06-01")
        .header("content-type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Request to Claude API failed: {e}"))?;

    let status = resp.status();
    let payload: Value = resp
        .json()
        .await
        .map_err(|e| format!("Could not parse Claude API response: {e}"))?;

    if !status.is_success() {
        let msg = payload
            .get("error")
            .and_then(|e| e.get("message"))
            .and_then(|m| m.as_str())
            .unwrap_or("unknown error");
        return Err(format!("Claude API error ({status}): {msg}"));
    }

    let content = payload
        .get("content")
        .and_then(|c| c.as_array())
        .ok_or("Claude API response had no content array")?;

    for block in content {
        if block.get("type").and_then(|t| t.as_str()) == Some("tool_use")
            && block.get("name").and_then(|n| n.as_str()) == Some("render_plot")
        {
            let input = block.get("input").cloned().unwrap_or(json!({}));
            return Ok(ClaudeReply::Plot(input));
        }
    }

    let text = content
        .iter()
        .filter(|b| b.get("type").and_then(|t| t.as_str()) == Some("text"))
        .filter_map(|b| b.get("text").and_then(|t| t.as_str()))
        .collect::<Vec<_>>()
        .join("\n");

    Ok(ClaudeReply::Text(if text.is_empty() {
        "(no response)".to_string()
    } else {
        text
    }))
}
