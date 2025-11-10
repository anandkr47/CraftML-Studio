mod backend_process;
use backend_process::{BackendProcess, start_backend, stop_backend, backend_status};
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend = BackendProcess::new();

    tauri::Builder::default()
        .manage(backend)
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            backend_status
        ])
        .setup(|app| {
            // Auto-start backend on app launch
            let backend_state = app.state::<BackendProcess>();
            // Prefer starting from the Resources/bin directory in production bundles
            if let Ok(resource_dir) = app.path().resource_dir() {
                match backend_state.start_with_resource_dir(resource_dir) {
                    Ok(msg) => println!("Backend: {}", msg),
                    Err(e) => eprintln!("Backend error: {}", e),
                }
            } else {
                // Fallback
                match backend_state.start() {
                    Ok(msg) => println!("Backend: {}", msg),
                    Err(e) => eprintln!("Backend error: {}", e),
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
