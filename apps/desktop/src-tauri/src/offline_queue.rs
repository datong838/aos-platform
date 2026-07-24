//! 187m — offline action queue persisted in SQLite (Tauri desktop).

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct QueueItem {
    pub id: String,
    pub method: String,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub body: Option<Value>,
    pub summary: String,
    pub created_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_error: Option<String>,
}

struct DbState {
    conn: rusqlite::Connection,
}

static DB: Mutex<Option<DbState>> = Mutex::new(None);

fn db_path() -> Result<PathBuf, String> {
    let base = dirs_next_data().ok_or_else(|| "no data dir".to_string())?;
    let dir = base.join("aos-desktop");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("offline_queue.sqlite3"))
}

/// Minimal data dir without extra crate: prefer HOME/.local/share or ~/Library/Application Support
fn dirs_next_data() -> Option<PathBuf> {
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return Some(PathBuf::from(xdg));
    }
    let home = std::env::var("HOME").ok().map(PathBuf::from)?;
    #[cfg(target_os = "macos")]
    {
        return Some(home.join("Library/Application Support"));
    }
    #[cfg(not(target_os = "macos"))]
    {
        Some(home.join(".local/share"))
    }
}

fn with_db<F, T>(f: F) -> Result<T, String>
where
    F: FnOnce(&rusqlite::Connection) -> Result<T, String>,
{
    let mut guard = DB.lock().map_err(|e| e.to_string())?;
    if guard.is_none() {
        let path = db_path()?;
        let conn = rusqlite::Connection::open(&path).map_err(|e| e.to_string())?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS offline_queue (
               id TEXT NOT NULL,
               org_id TEXT NOT NULL,
               project_id TEXT NOT NULL,
               payload_json TEXT NOT NULL,
               created_at TEXT NOT NULL,
               PRIMARY KEY (org_id, project_id, id)
             );",
        )
        .map_err(|e| e.to_string())?;
        *guard = Some(DbState { conn });
    }
    let state = guard.as_ref().unwrap();
    f(&state.conn)
}

#[tauri::command]
pub fn oq_list(org_id: String, project_id: String) -> Result<Vec<QueueItem>, String> {
    with_db(|conn| {
        let mut stmt = conn
            .prepare(
                "SELECT payload_json FROM offline_queue
                 WHERE org_id=?1 AND project_id=?2
                 ORDER BY created_at ASC",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(rusqlite::params![org_id, project_id], |row| {
                let raw: String = row.get(0)?;
                Ok(raw)
            })
            .map_err(|e| e.to_string())?;
        let mut out = Vec::new();
        for r in rows {
            let raw = r.map_err(|e| e.to_string())?;
            let item: QueueItem =
                serde_json::from_str(&raw).map_err(|e| e.to_string())?;
            out.push(item);
        }
        Ok(out)
    })
}

#[tauri::command]
pub fn oq_replace(
    org_id: String,
    project_id: String,
    items: Vec<QueueItem>,
) -> Result<(), String> {
    with_db(|conn| {
        let tx = conn.unchecked_transaction().map_err(|e| e.to_string())?;
        tx.execute(
            "DELETE FROM offline_queue WHERE org_id=?1 AND project_id=?2",
            rusqlite::params![org_id, project_id],
        )
        .map_err(|e| e.to_string())?;
        for it in items {
            let payload = serde_json::to_string(&it).map_err(|e| e.to_string())?;
            tx.execute(
                "INSERT INTO offline_queue (id, org_id, project_id, payload_json, created_at)
                 VALUES (?1,?2,?3,?4,?5)",
                rusqlite::params![it.id, org_id, project_id, payload, it.created_at],
            )
            .map_err(|e| e.to_string())?;
        }
        tx.commit().map_err(|e| e.to_string())?;
        Ok(())
    })
}

#[tauri::command]
pub fn oq_clear(org_id: String, project_id: String) -> Result<u32, String> {
    with_db(|conn| {
        let n = conn
            .execute(
                "DELETE FROM offline_queue WHERE org_id=?1 AND project_id=?2",
                rusqlite::params![org_id, project_id],
            )
            .map_err(|e| e.to_string())?;
        Ok(n as u32)
    })
}

#[tauri::command]
pub fn oq_clear_all() -> Result<u32, String> {
    with_db(|conn| {
        let n = conn
            .execute("DELETE FROM offline_queue", [])
            .map_err(|e| e.to_string())?;
        Ok(n as u32)
    })
}
