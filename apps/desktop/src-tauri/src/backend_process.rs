use std::process::{Child, Command};
use std::path::PathBuf;
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

    pub fn start_with_resource_dir(&self, resource_dir: PathBuf) -> Result<String, String> {
        let mut process_lock = self.process.lock().unwrap();

        if let Some(ref mut child) = *process_lock {
            if let Ok(None) = child.try_wait() {
                return Ok("Backend already running".to_string());
            }
        }

        // Look for sidecar under Resources/bin with platform-specific suffixes
        let bin_dir = resource_dir.join("bin");
        let candidates = vec![
            "craftml-backend.exe-x86_64-pc-windows-msvc.exe",
            "craftml-backend.exe",
            "craftml-backend-x86_64-unknown-linux-gnu",
            "craftml-backend-aarch64-unknown-linux-gnu",
            "craftml-backend-x86_64-apple-darwin",
            "craftml-backend-aarch64-apple-darwin",
            "craftml-backend",
        ];
        let sidecar_path = candidates
            .iter()
            .map(|name| bin_dir.join(name))
            .find(|p| p.exists())
            .ok_or("Bundled backend sidecar not found in resources")?;

        let child = Command::new(sidecar_path)
            .env("CRAFTML_ENV", "prod")
            .spawn()
            .map_err(|e| format!("Failed to start backend sidecar: {}", e))?;

        *process_lock = Some(child);
        Ok("Backend started successfully".to_string())
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

        // DEV: run Python script; PROD: spawn bundled sidecar executable
        let child = if cfg!(debug_assertions) {
            // Determine Python command based on OS
            let python_cmd = if cfg!(target_os = "windows") { "python" } else { "python3" };

            // Locate backend source folder from workspace structure
            let backend_path = std::env::current_exe()
                .ok()
                .and_then(|exe_path| exe_path.parent().map(|p| p.to_path_buf()))
                .and_then(|mut p| {
                    p.pop(); // remove target
                    p.pop(); // remove debug
                    p.push("apps");
                    p.push("backend");
                    Some(p)
                })
                .ok_or("Failed to determine backend path")?;
            let main_py = backend_path.join("main.py");

            Command::new(python_cmd)
                .arg(main_py.to_str().ok_or("Invalid path")?)
                .current_dir(&backend_path)
                .spawn()
                .map_err(|e| format!("Failed to start backend (dev): {}", e))?
        } else {
            // Production: sidecar sits next to the app executable
            let exe_dir = std::env::current_exe()
                .map_err(|_| "Failed to locate current exe")?
                .parent()
                .ok_or("Failed to locate exe directory")?
                .to_path_buf();

            // Try common sidecar filenames across platforms (Tauri v2 target-triple suffix)
            let candidates = vec![
                "craftml-backend.exe",
                "craftml-backend.exe-x86_64-pc-windows-msvc.exe",
                "craftml-backend-x86_64-unknown-linux-gnu",
                "craftml-backend-aarch64-unknown-linux-gnu",
                "craftml-backend-x86_64-apple-darwin",
                "craftml-backend-aarch64-apple-darwin",
                "craftml-backend", // non-Windows fallback
            ];
            let sidecar_path = candidates
                .iter()
                .map(|name| exe_dir.join(name))
                .find(|p| p.exists())
                .ok_or("Bundled backend sidecar not found")?;

            Command::new(sidecar_path)
                .env("CRAFTML_ENV", "prod")
                .spawn()
                .map_err(|e| format!("Failed to start backend sidecar: {}", e))?
        };

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

