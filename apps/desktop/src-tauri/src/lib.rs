mod backend_process;

use std::sync::Arc;

use backend_process::{
    backend_status, get_backend_logs, start_backend, start_in_background, stop_backend, BackendProcess, LaunchConfig,
};
use tauri::{Manager, RunEvent};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend = Arc::new(BackendProcess::new());

    let app = tauri::Builder::default()
        .manage(backend.clone())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![start_backend, stop_backend, backend_status, get_backend_logs])
        .setup(|app| {
            let paths = app.path();
            // Per-user locations: ~/Library/{Application Support,Logs}/com.craftml.studio on macOS,
            // %LOCALAPPDATA%\com.craftml.studio on Windows, ~/.local/share/com.craftml.studio on Linux.
            let local_data = paths
                .app_local_data_dir()
                .unwrap_or_else(|_| std::env::temp_dir().join("craftml-studio"));
            let log_dir = paths.app_log_dir().unwrap_or_else(|_| local_data.join("logs"));
            let config = LaunchConfig {
                app_version: app.package_info().version.to_string(),
                resource_dir: paths.resource_dir().ok(),
                runtime_dir: local_data.join("backend"),
                log_dir,
            };

            let backend = app.state::<Arc<BackendProcess>>().inner().clone();
            backend.configure(config);
            // In the background, so the window (and its loading screen) appears immediately;
            // the UI polls `backend_status` and the health endpoint.
            start_in_background(backend);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    // Ctrl+C in a terminal, SIGTERM/SIGHUP (logout, `kill`) or closing the console on Windows:
    // exit through the normal path so the backend is stopped below.
    let handle = app.handle().clone();
    if let Err(e) = ctrlc::set_handler(move || handle.exit(0)) {
        eprintln!("Could not install the termination handler: {e}");
    }

    app.run(move |_app, event| {
        if let RunEvent::Exit = event {
            let _ = backend.stop();
        }
    });
}
