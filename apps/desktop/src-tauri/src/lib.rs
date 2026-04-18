mod backend_process;
use backend_process::{BackendProcess, start_backend, stop_backend, backend_status, get_backend_logs};
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
            backend_status,
            get_backend_logs
        ])
        .setup(|app| {
            // Start backend and wait for it to be ready before showing UI
            let backend_state = app.state::<BackendProcess>();
            
            println!("Starting backend server...");
            
            // Start backend
            let resource_dir = app.path().resource_dir();
            let start_result = if let Ok(rd) = resource_dir {
                backend_state.start_with_resource_dir(rd)
            } else {
                backend_state.start()
            };
            
            match start_result {
                Ok(msg) => {
                    println!("Backend: {}", msg);
                    println!("Waiting for backend to be ready...");
                    
                    // Wait for backend to be ready (max 30 seconds)
                    match backend_state.wait_for_ready(30) {
                        Ok(()) => {
                            println!("Backend is ready!");
                        }
                        Err(e) => {
                            eprintln!("Backend failed to start: {}", e);
                            
                            // Log backend error output for debugging
                            if let Ok(logs) = get_backend_logs() {
                                eprintln!("Backend stdout:\n{}", logs["stdout"].as_str().unwrap_or(""));
                                eprintln!("Backend stderr:\n{}", logs["stderr"].as_str().unwrap_or(""));
                            }
                            
                            // Continue anyway - user can retry
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Failed to start backend: {}", e);
                    
                    // Log backend error output for debugging
                    if let Ok(logs) = get_backend_logs() {
                        eprintln!("Backend stdout:\n{}", logs["stdout"].as_str().unwrap_or(""));
                        eprintln!("Backend stderr:\n{}", logs["stderr"].as_str().unwrap_or(""));
                    }
                    
                    // Continue anyway - user can retry manually
                }
            }
            
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
