//! "End-to-end" test for the function library: there's no built Tauri binary or WebView in
//! this sandbox to drive a real UI, so this instead drives the actual public functions of
//! `library.rs` through a realistic full sequence against a real temp-file-backed library,
//! the same way the real app would use it across several user actions and an app restart
//! (reload from disk).
//!
//! `helpers` below is the reusable piece: future features can add another roundtrip scenario
//! (another `#[test]` fn) without rebuilding the temp-path setup/teardown each time.

#[path = "../src/library.rs"]
mod library;

use library::{FunctionEntry, Library};

mod helpers {
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    /// A temp library.json path, unique per test, cleaned up (best-effort) on drop.
    pub struct TempLibrary {
        path: PathBuf,
    }

    impl TempLibrary {
        pub fn new() -> Self {
            let n = COUNTER.fetch_add(1, Ordering::SeqCst);
            let pid = std::process::id();
            let dir = std::env::temp_dir().join(format!("math-viz-e2e-{pid}-{n}"));
            Self {
                path: dir.join("library.json"),
            }
        }

        pub fn path(&self) -> &Path {
            &self.path
        }
    }

    impl Drop for TempLibrary {
        fn drop(&mut self) {
            if let Some(parent) = self.path.parent() {
                let _ = std::fs::remove_dir_all(parent);
            }
        }
    }

    pub fn entry(id: &str, title: &str) -> super::FunctionEntry {
        super::FunctionEntry {
            id: id.to_string(),
            title: title.to_string(),
            subtitle: format!("f(x) = {title}"),
            description: String::new(),
            kind: "2d".to_string(),
            variables: vec!["x".to_string()],
            domain: serde_json::json!({ "xMin": -10, "xMax": 10 }),
            traces: serde_json::json!([{ "expr": "x" }]),
            created_at: String::new(),
            combined: false,
        }
    }
}

#[test]
fn full_library_lifecycle_roundtrips_through_disk() {
    let tmp = helpers::TempLibrary::new();
    let mut lib = Library::default();

    // Save two functions under different topics.
    library::save_function(
        &mut lib,
        "Polynomials".to_string(),
        helpers::entry("poly-1", "Cubic"),
        tmp.path(),
    )
    .expect("save poly-1");
    library::save_function(
        &mut lib,
        "Trigonometry".to_string(),
        helpers::entry("trig-1", "Sine"),
        tmp.path(),
    )
    .expect("save trig-1");

    assert_eq!(lib.topics.len(), 2);

    // Move the sine function into Polynomials (contrived, but exercises the move path).
    library::move_function(
        &mut lib,
        "trig-1".to_string(),
        "Polynomials".to_string(),
        tmp.path(),
    )
    .expect("move trig-1");

    // Rename "Trigonometry" (now empty) to "Misc".
    library::rename_topic(
        &mut lib,
        "Trigonometry".to_string(),
        "Misc".to_string(),
        tmp.path(),
    )
    .expect("rename Trigonometry -> Misc");

    // Delete the cubic function.
    library::delete_function(&mut lib, "poly-1".to_string(), tmp.path()).expect("delete poly-1");

    // Reload from disk (simulating an app restart) and assert the final state.
    let reloaded = library::load_library_from(tmp.path());

    let polynomials = reloaded
        .topics
        .iter()
        .find(|t| t.name == "Polynomials")
        .expect("Polynomials topic exists");
    assert_eq!(polynomials.functions.len(), 1);
    assert_eq!(polynomials.functions[0].id, "trig-1");
    assert_eq!(polynomials.functions[0].title, "Sine");

    let misc = reloaded
        .topics
        .iter()
        .find(|t| t.name == "Misc")
        .expect("Misc topic exists (renamed from Trigonometry)");
    assert!(misc.functions.is_empty());

    assert!(
        reloaded.topics.iter().all(|t| t.name != "Trigonometry"),
        "old topic name should no longer exist after rename"
    );
    assert!(
        reloaded
            .topics
            .iter()
            .flat_map(|t| &t.functions)
            .all(|f| f.id != "poly-1"),
        "deleted function should not reappear after reload"
    );
}

#[test]
fn reloading_an_untouched_fresh_path_is_an_empty_library() {
    let tmp = helpers::TempLibrary::new();
    let lib = library::load_library_from(tmp.path());
    assert!(lib.topics.is_empty());
}
