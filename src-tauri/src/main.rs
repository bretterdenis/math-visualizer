#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod claude;
mod library;

use claude::{ChatMessage, ClaudeReply};
use library::{FunctionEntry, Library, Topic};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::State;

struct AppState {
    client: reqwest::Client,
    api_key: Mutex<Option<String>>,
    history: Mutex<Vec<ChatMessage>>,
    library: Mutex<Library>,
}

#[derive(Serialize, Deserialize)]
struct StoredConfig {
    api_key: Option<String>,
}

fn config_path() -> Option<PathBuf> {
    dirs::config_dir().map(|p| p.join("math-visualizer").join("config.json"))
}

fn load_api_key() -> Option<String> {
    if let Ok(key) = std::env::var("ANTHROPIC_API_KEY") {
        if !key.trim().is_empty() {
            return Some(key);
        }
    }
    let path = config_path()?;
    let data = fs::read_to_string(path).ok()?;
    let cfg: StoredConfig = serde_json::from_str(&data).ok()?;
    cfg.api_key
}

fn save_api_key(key: &str) -> Result<(), String> {
    let path = config_path().ok_or("Could not resolve config directory")?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let cfg = StoredConfig {
        api_key: Some(key.to_string()),
    };
    fs::write(path, serde_json::to_string_pretty(&cfg).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn has_api_key(state: State<AppState>) -> bool {
    state.api_key.lock().unwrap().is_some()
}

#[tauri::command]
fn set_api_key(state: State<AppState>, key: String) -> Result<(), String> {
    let key = key.trim().to_string();
    if key.is_empty() {
        return Err("API key cannot be empty".into());
    }
    save_api_key(&key)?;
    *state.api_key.lock().unwrap() = Some(key);
    Ok(())
}

#[tauri::command]
fn reset_conversation(state: State<AppState>) {
    state.history.lock().unwrap().clear();
}

#[tauri::command]
async fn ask_claude(state: State<'_, AppState>, prompt: String) -> Result<serde_json::Value, String> {
    let api_key = state
        .api_key
        .lock()
        .unwrap()
        .clone()
        .ok_or("No API key set")?;

    {
        let mut history = state.history.lock().unwrap();
        history.push(ChatMessage {
            role: "user".to_string(),
            content: json!(prompt),
        });
    }

    let history_snapshot = state.history.lock().unwrap().clone();

    let reply = claude::ask(&state.client, &api_key, &history_snapshot).await;

    match reply {
        Ok(ClaudeReply::Plot(data)) => {
            let mut history = state.history.lock().unwrap();
            let tool_id = format!("render_plot_call_{}", history.len());
            history.push(ChatMessage {
                role: "assistant".to_string(),
                content: json!([{
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "render_plot",
                    "input": data.clone()
                }]),
            });
            history.push(ChatMessage {
                role: "user".to_string(),
                content: json!([{
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": "Plot rendered."
                }]),
            });
            Ok(json!({ "type": "plot", "data": data }))
        }
        Ok(ClaudeReply::Text(text)) => {
            let mut history = state.history.lock().unwrap();
            history.push(ChatMessage {
                role: "assistant".to_string(),
                content: json!(text),
            });
            Ok(json!({ "type": "text", "data": text }))
        }
        Err(e) => {
            state.history.lock().unwrap().pop();
            Err(e)
        }
    }
}

#[tauri::command]
fn list_topics(state: State<AppState>) -> Vec<Topic> {
    state
        .library
        .lock()
        .unwrap()
        .topics
        .iter()
        .map(|t| Topic {
            name: t.name.clone(),
            functions: t.functions.iter().filter(|f| !f.combined).cloned().collect(),
        })
        .collect()
}

#[tauri::command]
fn list_combined(state: State<AppState>) -> Vec<FunctionEntry> {
    state.library.lock().unwrap().combined.clone()
}

fn library_path_or_err() -> Result<PathBuf, String> {
    library::default_library_path().ok_or_else(|| "Could not resolve config directory".to_string())
}

#[tauri::command]
fn save_function(state: State<AppState>, topic: String, entry: FunctionEntry) -> Result<(), String> {
    let path = library_path_or_err()?;
    let mut lib = state.library.lock().unwrap();
    library::save_function(&mut lib, topic, entry, &path)
}

#[tauri::command]
fn move_function(state: State<AppState>, id: String, new_topic: String) -> Result<(), String> {
    let path = library_path_or_err()?;
    let mut lib = state.library.lock().unwrap();
    library::move_function(&mut lib, id, new_topic, &path)
}

#[tauri::command]
fn delete_function(state: State<AppState>, id: String) -> Result<(), String> {
    let path = library_path_or_err()?;
    let mut lib = state.library.lock().unwrap();
    library::delete_function(&mut lib, id, &path)
}

#[tauri::command]
fn rename_topic(state: State<AppState>, old_name: String, new_name: String) -> Result<(), String> {
    let path = library_path_or_err()?;
    let mut lib = state.library.lock().unwrap();
    library::rename_topic(&mut lib, old_name, new_name, &path)
}

fn main() {
    let env_path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../.env");
    let _ = dotenvy::from_path(env_path);

    tauri::Builder::default()
        .manage(AppState {
            client: reqwest::Client::new(),
            api_key: Mutex::new(load_api_key()),
            history: Mutex::new(Vec::new()),
            library: Mutex::new(library::load_library()),
        })
        .invoke_handler(tauri::generate_handler![
            has_api_key,
            set_api_key,
            reset_conversation,
            ask_claude,
            list_topics,
            list_combined,
            save_function,
            move_function,
            delete_function,
            rename_topic
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
