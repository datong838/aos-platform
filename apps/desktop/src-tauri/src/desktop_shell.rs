//! TWC.3/4 — secure store (keyring) + tray + about

use serde::Serialize;
use serde_json::json;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager,
};

const KEYRING_SERVICE: &str = "com.aos.desktop";

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AboutInfo {
    pub product_name: String,
    pub version: String,
    pub identifier: String,
}

#[tauri::command]
pub fn secure_set(key: String, value: String) -> Result<(), String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    entry.set_password(&value).map_err(|e| e.to_string())?;
    log_safe("secure_set", &key, true);
    Ok(())
}

#[tauri::command]
pub fn secure_get(key: String) -> Result<Option<String>, String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(v) => {
            log_safe("secure_get", &key, true);
            Ok(Some(v))
        }
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
pub fn secure_delete(key: String) -> Result<(), String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, &key).map_err(|e| e.to_string())?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => {
            log_safe("secure_delete", &key, true);
            Ok(())
        }
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
pub fn about_info() -> AboutInfo {
    AboutInfo {
        product_name: "AOS 桌面".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        identifier: "com.aos.desktop".into(),
    }
}

/// TWC.9 — 壳侧二次验签门禁（与前端 aos-v1 算法一致；失败拒装）
#[tauri::command]
pub fn verify_update_signature(
    version: String,
    url: String,
    sha256: String,
    signature: String,
) -> Result<bool, String> {
    const KEY_ID: &str = "aos-desktop-dev-v1";
    if version.trim().is_empty() || url.trim().is_empty() || sha256.trim().is_empty() {
        return Err("清单字段不完整".into());
    }
    if !signature.starts_with("aos-v1:") {
        return Err("未知签名算法或缺失签名".into());
    }
    let canonical = format!("{version}\n{url}\n{sha256}\n{KEY_ID}");
    let expected_hex = simple_sha256_hex(&format!("{canonical}\n{KEY_ID}"));
    let expected = format!("aos-v1:{expected_hex}");
    if signature != expected {
        eprintln!(
            "{{\"service\":\"aos-desktop\",\"event\":\"verify_update_failed\",\"version\":\"{version}\"}}"
        );
        return Err("签名校验失败 · 请联系运维/管理员".into());
    }
    eprintln!(
        "{{\"service\":\"aos-desktop\",\"event\":\"verify_update_ok\",\"version\":\"{version}\"}}"
    );
    Ok(true)
}

/// 无额外 crate 的轻量 SHA-256（仅用于 aos-v1 门禁；生产可换 cosign）
fn simple_sha256_hex(input: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

fn log_safe(op: &str, key: &str, ok: bool) {
    // never log secret values
    eprintln!(
        "{{\"service\":\"aos-desktop\",\"event\":\"{op}\",\"key\":\"{key}\",\"ok\":{ok}}}"
    );
}

pub fn setup_tray(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "打开主窗口", true, None::<&str>)?;
    let about = MenuItem::with_id(app, "about", "关于本机", true, None::<&str>)?;
    let check_update = MenuItem::with_id(app, "check_update", "检查更新", true, None::<&str>)?;
    let buddy = MenuItem::with_id(app, "buddy_classic", "Buddy 经典三栏", true, None::<&str>)?;
    let local = MenuItem::with_id(app, "local_platform", "本机探活", true, None::<&str>)?;
    let sep = PredefinedMenuItem::separator(app)?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(
        app,
        &[&show, &about, &check_update, &buddy, &local, &sep, &quit],
    )?;

    let icon = app
        .default_window_icon()
        .cloned()
        .expect("default window icon");

    let _tray = TrayIconBuilder::with_id("main-tray")
        .icon(icon)
        .menu(&menu)
        .tooltip("AOS 桌面")
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => show_main(app),
            "about" => {
                let _ = app.emit("aos-desktop-about", json!({}));
                show_main(app);
            }
            "check_update" => {
                let _ = app.emit("aos-desktop-check-update", json!({}));
                show_main(app);
            }
            "buddy_classic" => {
                let _ = app.emit("aos-desktop-buddy-classic", json!({}));
                show_main(app);
            }
            "local_platform" => {
                let _ = app.emit("aos-desktop-navigate", json!({ "path": "/settings/local-platform" }));
                show_main(app);
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main(tray.app_handle());
            }
        })
        .build(app)?;

    Ok(())
}

fn show_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
}

pub fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}
