// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
mod desktop_shell;
mod offline_queue;

use tauri::Manager;

#[tauri::command]
fn greet(name: &str) -> String {
    desktop_shell::greet(name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_deep_link::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            desktop_shell::secure_set,
            desktop_shell::secure_get,
            desktop_shell::secure_delete,
            desktop_shell::about_info,
            desktop_shell::verify_update_signature,
            desktop_shell::tray_update_status,
            offline_queue::oq_list,
            offline_queue::oq_replace,
            offline_queue::oq_clear,
            offline_queue::oq_clear_all,
        ])
        .setup(|app| {
            desktop_shell::setup_tray(app.handle())?;
            #[cfg(any(target_os = "linux", all(debug_assertions, windows)))]
            {
                use tauri_plugin_deep_link::DeepLinkExt;
                let _ = app.deep_link().register_all();
            }
            if let Some(win) = app.get_webview_window("main") {
                let w = win.clone();
                win.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = w.hide();
                    }
                });
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
