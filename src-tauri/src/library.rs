use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct FunctionEntry {
    pub id: String,
    pub title: String,
    pub subtitle: String,
    pub description: String,
    pub kind: String,
    pub variables: Vec<String>,
    pub domain: Value,
    pub traces: Value,
    pub created_at: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Topic {
    pub name: String,
    pub functions: Vec<FunctionEntry>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
pub struct Library {
    pub topics: Vec<Topic>,
}

fn library_path() -> Option<PathBuf> {
    dirs::config_dir().map(|p| p.join("math-visualizer").join("library.json"))
}

pub fn load_library() -> Library {
    let Some(path) = library_path() else {
        return Library::default();
    };
    let Ok(data) = fs::read_to_string(path) else {
        return Library::default();
    };
    serde_json::from_str(&data).unwrap_or_default()
}

pub fn save_library(library: &Library) -> Result<(), String> {
    let path = library_path().ok_or("Could not resolve config directory")?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(
        path,
        serde_json::to_string_pretty(library).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())
}

pub fn generate_id() -> String {
    let timestamp_millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let random_suffix: u32 = {
        use std::collections::hash_map::RandomState;
        use std::hash::{BuildHasher, Hash, Hasher};
        let mut hasher = RandomState::new().build_hasher();
        timestamp_millis.hash(&mut hasher);
        (hasher.finish() % 1_000_000) as u32
    };
    format!("{}-{}", timestamp_millis, random_suffix)
}

pub fn now_iso8601() -> String {
    chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}

pub fn find_topic_mut<'a>(library: &'a mut Library, name: &str) -> Option<&'a mut Topic> {
    library.topics.iter_mut().find(|t| t.name == name)
}

pub fn save_function(library: &mut Library, topic: String, mut entry: FunctionEntry) -> Result<(), String> {
    if entry.id.trim().is_empty() {
        entry.id = generate_id();
    }
    if entry.created_at.trim().is_empty() {
        entry.created_at = now_iso8601();
    }
    match find_topic_mut(library, &topic) {
        Some(t) => t.functions.push(entry),
        None => library.topics.push(Topic {
            name: topic,
            functions: vec![entry],
        }),
    }
    save_library(library)
}

pub fn move_function(library: &mut Library, id: String, new_topic: String) -> Result<(), String> {
    let mut found: Option<FunctionEntry> = None;
    for topic in library.topics.iter_mut() {
        if let Some(pos) = topic.functions.iter().position(|f| f.id == id) {
            found = Some(topic.functions.remove(pos));
            break;
        }
    }
    let entry = found.ok_or_else(|| format!("Function '{}' not found", id))?;
    match find_topic_mut(library, &new_topic) {
        Some(t) => t.functions.push(entry),
        None => library.topics.push(Topic {
            name: new_topic,
            functions: vec![entry],
        }),
    }
    save_library(library)
}

pub fn delete_function(library: &mut Library, id: String) -> Result<(), String> {
    let mut removed = false;
    for topic in library.topics.iter_mut() {
        let before = topic.functions.len();
        topic.functions.retain(|f| f.id != id);
        if topic.functions.len() != before {
            removed = true;
        }
    }
    if !removed {
        return Err(format!("Function '{}' not found", id));
    }
    save_library(library)
}

pub fn rename_topic(library: &mut Library, old_name: String, new_name: String) -> Result<(), String> {
    let topic = library
        .topics
        .iter_mut()
        .find(|t| t.name == old_name)
        .ok_or_else(|| format!("Topic '{}' not found", old_name))?;
    topic.name = new_name;
    save_library(library)
}
