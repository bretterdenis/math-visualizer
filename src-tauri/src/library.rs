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

/// The real on-disk location for the library file (`~/.config/math-visualizer/library.json`
/// or platform equivalent). Used by the Tauri commands; tests use their own temp path instead
/// so they never touch the real user config file.
pub fn default_library_path() -> Option<PathBuf> {
    dirs::config_dir().map(|p| p.join("math-visualizer").join("library.json"))
}

/// Loads the library from `path`. Returns an empty `Library` if the file doesn't exist or
/// can't be parsed (e.g. first run, or a corrupted file) rather than erroring.
pub fn load_library_from(path: &std::path::Path) -> Library {
    let Ok(data) = fs::read_to_string(path) else {
        return Library::default();
    };
    serde_json::from_str(&data).unwrap_or_default()
}

/// Writes `library` to `path`, creating the parent directory if needed.
pub fn save_library_to(library: &Library, path: &std::path::Path) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(
        path,
        serde_json::to_string_pretty(library).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())
}

/// Loads the library from the real default path. Returns an empty `Library` if the config
/// directory can't be resolved, the file doesn't exist, or it can't be parsed.
pub fn load_library() -> Library {
    let Some(path) = default_library_path() else {
        return Library::default();
    };
    load_library_from(&path)
}

/// Saves `library` to the real default path.
pub fn save_library(library: &Library) -> Result<(), String> {
    let path = default_library_path().ok_or("Could not resolve config directory")?;
    save_library_to(library, &path)
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

pub fn save_function(
    library: &mut Library,
    topic: String,
    mut entry: FunctionEntry,
    path: &std::path::Path,
) -> Result<(), String> {
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
    save_library_to(library, path)
}

pub fn move_function(
    library: &mut Library,
    id: String,
    new_topic: String,
    path: &std::path::Path,
) -> Result<(), String> {
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
    save_library_to(library, path)
}

pub fn delete_function(
    library: &mut Library,
    id: String,
    path: &std::path::Path,
) -> Result<(), String> {
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
    save_library_to(library, path)
}

pub fn rename_topic(
    library: &mut Library,
    old_name: String,
    new_name: String,
    path: &std::path::Path,
) -> Result<(), String> {
    let topic = library
        .topics
        .iter_mut()
        .find(|t| t.name == old_name)
        .ok_or_else(|| format!("Topic '{}' not found", old_name))?;
    topic.name = new_name;
    save_library_to(library, path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    /// A temp library path unique per call, so parallel test threads never collide. The file
    /// (and its parent dir, which this module creates on save) are best-effort cleaned up via
    /// an RAII guard.
    struct TempLibraryPath(PathBuf);

    impl TempLibraryPath {
        fn new() -> Self {
            let n = COUNTER.fetch_add(1, Ordering::SeqCst);
            let pid = std::process::id();
            let dir = std::env::temp_dir().join(format!("math-viz-test-{pid}-{n}"));
            Self(dir.join("library.json"))
        }

        fn path(&self) -> &std::path::Path {
            &self.0
        }
    }

    impl Drop for TempLibraryPath {
        fn drop(&mut self) {
            if let Some(parent) = self.0.parent() {
                let _ = fs::remove_dir_all(parent);
            }
        }
    }

    fn sample_entry(id: &str, title: &str) -> FunctionEntry {
        FunctionEntry {
            id: id.to_string(),
            title: title.to_string(),
            subtitle: String::new(),
            description: String::new(),
            kind: "2d".to_string(),
            variables: vec!["x".to_string()],
            domain: serde_json::json!({ "xMin": -10, "xMax": 10 }),
            traces: serde_json::json!([{ "expr": "x" }]),
            created_at: String::new(),
        }
    }

    #[test]
    fn load_library_from_missing_file_returns_default() {
        let tmp = TempLibraryPath::new();
        let lib = load_library_from(tmp.path());
        assert!(lib.topics.is_empty());
    }

    #[test]
    fn load_library_from_empty_or_corrupt_file_returns_default() {
        let tmp = TempLibraryPath::new();
        fs::create_dir_all(tmp.path().parent().unwrap()).unwrap();
        fs::write(tmp.path(), "not valid json").unwrap();
        let lib = load_library_from(tmp.path());
        assert!(lib.topics.is_empty());
    }

    #[test]
    fn save_function_creates_topic_if_missing_and_round_trips() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        save_function(
            &mut lib,
            "Polynomials".to_string(),
            sample_entry("", "Cubic"),
            tmp.path(),
        )
        .unwrap();

        assert_eq!(lib.topics.len(), 1);
        assert_eq!(lib.topics[0].name, "Polynomials");
        assert_eq!(lib.topics[0].functions.len(), 1);
        // generate_id/now_iso8601 should have filled in blank fields.
        assert!(!lib.topics[0].functions[0].id.trim().is_empty());
        assert!(!lib.topics[0].functions[0].created_at.trim().is_empty());

        let reloaded = load_library_from(tmp.path());
        assert_eq!(reloaded.topics.len(), 1);
        assert_eq!(reloaded.topics[0].functions[0].title, "Cubic");
    }

    #[test]
    fn save_function_appends_to_existing_topic() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        save_function(
            &mut lib,
            "Trig".to_string(),
            sample_entry("a", "Sine"),
            tmp.path(),
        )
        .unwrap();
        save_function(
            &mut lib,
            "Trig".to_string(),
            sample_entry("b", "Cosine"),
            tmp.path(),
        )
        .unwrap();

        assert_eq!(lib.topics.len(), 1);
        assert_eq!(lib.topics[0].functions.len(), 2);
    }

    #[test]
    fn move_function_moves_entry_between_topics() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        save_function(&mut lib, "A".to_string(), sample_entry("x1", "One"), tmp.path()).unwrap();

        move_function(&mut lib, "x1".to_string(), "B".to_string(), tmp.path()).unwrap();

        let topic_a = lib.topics.iter().find(|t| t.name == "A").unwrap();
        let topic_b = lib.topics.iter().find(|t| t.name == "B").unwrap();
        assert!(topic_a.functions.is_empty());
        assert_eq!(topic_b.functions.len(), 1);
        assert_eq!(topic_b.functions[0].id, "x1");
    }

    #[test]
    fn move_function_missing_id_errors() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        let err = move_function(&mut lib, "nope".to_string(), "B".to_string(), tmp.path())
            .unwrap_err();
        assert!(err.contains("nope"));
    }

    #[test]
    fn delete_function_removes_entry() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        save_function(&mut lib, "A".to_string(), sample_entry("x1", "One"), tmp.path()).unwrap();
        save_function(&mut lib, "A".to_string(), sample_entry("x2", "Two"), tmp.path()).unwrap();

        delete_function(&mut lib, "x1".to_string(), tmp.path()).unwrap();

        assert_eq!(lib.topics[0].functions.len(), 1);
        assert_eq!(lib.topics[0].functions[0].id, "x2");
    }

    #[test]
    fn delete_function_missing_id_errors() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        let err = delete_function(&mut lib, "nope".to_string(), tmp.path()).unwrap_err();
        assert!(err.contains("nope"));
    }

    #[test]
    fn rename_topic_renames_and_persists() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        save_function(&mut lib, "Old".to_string(), sample_entry("x1", "One"), tmp.path()).unwrap();

        rename_topic(&mut lib, "Old".to_string(), "New".to_string(), tmp.path()).unwrap();

        assert_eq!(lib.topics.len(), 1);
        assert_eq!(lib.topics[0].name, "New");

        let reloaded = load_library_from(tmp.path());
        assert_eq!(reloaded.topics[0].name, "New");
    }

    #[test]
    fn rename_topic_missing_errors() {
        let tmp = TempLibraryPath::new();
        let mut lib = Library::default();
        let err = rename_topic(&mut lib, "Ghost".to_string(), "New".to_string(), tmp.path())
            .unwrap_err();
        assert!(err.contains("Ghost"));
    }
}
