use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

pub struct BackendProcess {
    process: Mutex<Option<Child>>,
}

impl BackendProcess {
    pub fn new() -> Self {
        BackendProcess {
            process: Mutex::new(None),
        }
    }

    pub fn start(&self) -> Result<String, String> {
        let mut process_lock = self.process.lock().unwrap();

        // Check if already running
        if let Some(ref mut child) = *process_lock {
            match child.try_wait() {
                Ok(None) => {
                    return Ok("Backend already running".to_string());
                }
                _ => {
                    // Process has exited, will start new one
                }
            }
        }

        // Determine Python command based on OS
        let python_cmd = if cfg!(target_os = "windows") {
            "python"
        } else {
            "python3"
        };

        // Get backend path relative to the executable
        let backend_path = std::env::current_exe()
            .ok()
            .and_then(|exe_path| exe_path.parent().map(|p| p.to_path_buf()))
            .and_then(|mut p| {
                // In development, go up to workspace root
                if cfg!(debug_assertions) {
                    p.pop(); // Remove target
                    p.pop(); // Remove debug
                    p.push("apps");
                    p.push("backend");
                } else {
                    // In production, backend should be bundled
                    p.push("backend");
                }
                Some(p)
            })
            .ok_or("Failed to determine backend path")?;

        let main_py = backend_path.join("main.py");

        // Start Python backend process
        let child = Command::new(python_cmd)
            .arg(main_py.to_str().ok_or("Invalid path")?)
            .current_dir(&backend_path)
            .spawn()
            .map_err(|e| format!("Failed to start backend: {}", e))?;

        *process_lock = Some(child);

        Ok("Backend started successfully".to_string())
    }

    pub fn stop(&self) -> Result<String, String> {
        let mut process_lock = self.process.lock().unwrap();

        if let Some(mut child) = process_lock.take() {
            child
                .kill()
                .map_err(|e| format!("Failed to stop backend: {}", e))?;
            return Ok("Backend stopped successfully".to_string());
        }

        Ok("Backend was not running".to_string())
    }

    pub fn status(&self) -> String {
        let process_lock = self.process.lock().unwrap();

        if let Some(ref child) = *process_lock {
            format!("Backend running (PID: {})", child.id())
        } else {
            "Backend not running".to_string()
        }
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}

#[tauri::command]
pub fn start_backend(state: State<BackendProcess>) -> Result<String, String> {
    state.start()
}

#[tauri::command]
pub fn stop_backend(state: State<BackendProcess>) -> Result<String, String> {
    state.stop()
}

#[tauri::command]
pub fn backend_status(state: State<BackendProcess>) -> String {
    state.status()
}

