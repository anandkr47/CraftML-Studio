use std::process::{Child, Command};
use std::path::PathBuf;
use std::sync::Mutex;
use std::fs;
use tauri::State;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

pub struct BackendProcess {
    process: Mutex<Option<Child>>,
}

impl BackendProcess {
    pub fn new() -> Self {
        BackendProcess {
            process: Mutex::new(None),
        }
    }

    /// Recursively copy directory and all its contents (files and subdirectories)
    fn copy_directory_recursive(&self, src: &PathBuf, dst: &PathBuf) -> Result<(), String> {
        if !src.exists() {
            return Err(format!("Source directory does not exist: {:?}", src));
        }

        if !src.is_dir() {
            return Err(format!("Source is not a directory: {:?}", src));
        }

        // Create destination directory if it doesn't exist
        fs::create_dir_all(dst)
            .map_err(|e| format!("Failed to create destination directory: {}", e))?;

        // Read all entries in source directory
        let entries = fs::read_dir(src)
            .map_err(|e| format!("Failed to read source directory: {}", e))?;

        for entry in entries {
            let entry = entry.map_err(|e| format!("Failed to read directory entry: {}", e))?;
            let src_path = entry.path();
            let file_name = entry.file_name();
            let dst_path = dst.join(&file_name);

            if src_path.is_dir() {
                // Recursively copy subdirectory
                self.copy_directory_recursive(&src_path, &dst_path)?;
            } else if src_path.is_file() {
                // Copy file
                fs::copy(&src_path, &dst_path)
                    .map_err(|e| format!("Failed to copy {:?}: {}", src_path, e))?;

                // Set executable permissions on Unix for executables and shared libraries
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    let file_name_str = file_name.to_string_lossy();
                    if file_name_str.contains("main") || 
                       file_name_str.ends_with(".so") ||
                       file_name_str.ends_with(".dylib") ||
                       file_name_str.ends_with(".bin") {
                        let mut perms = fs::metadata(&dst_path)
                            .map_err(|e| format!("Failed to read file permissions: {}", e))?
                            .permissions();
                        perms.set_mode(0o755);
                        fs::set_permissions(&dst_path, perms)
                            .map_err(|e| format!("Failed to set executable permissions: {}", e))?;
                    }
                }
            }
        }

        Ok(())
    }

    /// Extract entire backend directory from resources to temp directory and return executable path
    /// With --standalone, Nuitka creates a directory with the EXE + all dependencies (DLLs, .pyd, etc.)
    fn extract_backend_from_resources(&self, resource_dir: PathBuf) -> Result<PathBuf, String> {
        // Determine platform-specific backend filename
        let backend_filename = if cfg!(target_os = "windows") {
            "main-x86_64-pc-windows-msvc.exe"
        } else if cfg!(target_os = "macos") {
            if cfg!(target_arch = "aarch64") {
                "main-aarch64-apple-darwin"
            } else {
                "main-x86_64-apple-darwin"
            }
        } else {
            // Linux
            if cfg!(target_arch = "aarch64") {
                "main-aarch64-unknown-linux-gnu"
            } else {
                "main-x86_64-unknown-linux-gnu"
            }
        };

        // Extract entire bin directory from resources (includes EXE + all dependencies)
        let embedded_bin_dir = resource_dir.join("bin");
        
        if !embedded_bin_dir.exists() {
            return Err(format!("Embedded backend directory not found: {:?}", embedded_bin_dir));
        }

        // Extract to temp directory
        let temp_dir = std::env::temp_dir()
            .join("craftml-studio")
            .join("backend");
        fs::create_dir_all(&temp_dir)
            .map_err(|e| format!("Failed to create temp directory: {}", e))?;

        let extracted_exe = temp_dir.join(&backend_filename);

        // Check if we need to extract (if exe doesn't exist, extract everything)
        let should_extract = !extracted_exe.exists();

        if should_extract {
            // Copy all files and subdirectories from bin/ directory recursively
            // Nuitka --standalone includes EXE + all DLLs, .pyd, .so, and data directories (api/, core/, plugins/, etc.)
            self.copy_directory_recursive(&embedded_bin_dir, &temp_dir)?;
        }

        Ok(extracted_exe)
    }

    pub fn start_with_resource_dir(&self, resource_dir: PathBuf) -> Result<String, String> {
        self.start_with_args(resource_dir, None, None, None)
    }

    pub fn start_with_args(
        &self,
        resource_dir: PathBuf,
        host: Option<String>,
        port: Option<u16>,
        log_level: Option<String>,
    ) -> Result<String, String> {
        let mut process_lock = self.process.lock().unwrap();

        if let Some(ref mut child) = *process_lock {
            if let Ok(None) = child.try_wait() {
                return Ok("Backend already running".to_string());
            }
        }

        // Extract backend from embedded binary (or fallback to resources)
        let backend_path = self.extract_backend_from_resources(resource_dir)?;

        // Build command with arguments
        let mut cmd = Command::new(&backend_path);
        cmd.env("CRAFTML_ENV", "prod");
        
        // Hide console window on Windows (CREATE_NO_WINDOW = 0x08000000)
        #[cfg(windows)]
        cmd.creation_flags(0x08000000);
        
        // Redirect stdout/stderr to log files for debugging
        use std::process::Stdio;
        use std::fs::OpenOptions;
        
        let log_dir = std::env::temp_dir().join("craftml-studio").join("logs");
        fs::create_dir_all(&log_dir).ok();
        
        let stdout_log = log_dir.join("backend-stdout.log");
        let stderr_log = log_dir.join("backend-stderr.log");
        
        let stdout_file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&stdout_log)
            .map_err(|e| format!("Failed to create stdout log: {}", e))?;
        
        let stderr_file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&stderr_log)
            .map_err(|e| format!("Failed to create stderr log: {}", e))?;
        
        cmd.stdout(Stdio::from(stdout_file));
        cmd.stderr(Stdio::from(stderr_file));
        
        eprintln!("Backend logs will be written to:");
        eprintln!("  stdout: {:?}", stdout_log);
        eprintln!("  stderr: {:?}", stderr_log);
        
        // Add command-line arguments
        if let Some(h) = host {
            cmd.arg("--host").arg(h);
        }
        if let Some(p) = port {
            cmd.arg("--port").arg(p.to_string());
        }
        if let Some(ll) = log_level {
            cmd.arg("--log-level").arg(ll);
        }
        
        let child = cmd
            .spawn()
            .map_err(|e| format!("Failed to start backend: {}", e))?;

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

            let mut dev_cmd = Command::new(python_cmd);
            dev_cmd.arg(main_py.to_str().ok_or("Invalid path")?)
                .current_dir(&backend_path);
            
            #[cfg(windows)]
            {
                dev_cmd.creation_flags(0x08000000);
            }
            
            // Redirect to log files for debugging
            use std::process::Stdio;
            use std::fs::OpenOptions;
            
            let log_dir = std::env::temp_dir().join("craftml-studio").join("logs");
            fs::create_dir_all(&log_dir).ok();
            
            let stdout_log = log_dir.join("backend-stdout.log");
            let stderr_log = log_dir.join("backend-stderr.log");
            
            let stdout_file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&stdout_log)
                .ok();
            
            let stderr_file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&stderr_log)
                .ok();
            
            if let Some(stdout) = stdout_file {
                dev_cmd.stdout(Stdio::from(stdout));
            }
            if let Some(stderr) = stderr_file {
                dev_cmd.stderr(Stdio::from(stderr));
            }
            
            dev_cmd.spawn()
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
                "main.exe",
                "main-x86_64-pc-windows-msvc.exe",
                "main-x86_64-unknown-linux-gnu",
                "main-aarch64-unknown-linux-gnu",
                "main-x86_64-apple-darwin",
                "main-aarch64-apple-darwin",
                "main", // non-Windows fallback
            ];
            let sidecar_path = candidates
                .iter()
                .map(|name| exe_dir.join(name))
                .find(|p| p.exists())
                .ok_or("Bundled backend sidecar not found")?;

            let mut prod_cmd = Command::new(sidecar_path);
            prod_cmd.env("CRAFTML_ENV", "prod");
            
            #[cfg(windows)]
            {
                prod_cmd.creation_flags(0x08000000);
            }
            
            // Redirect to log files for debugging
            use std::process::Stdio;
            use std::fs::OpenOptions;
            
            let log_dir = std::env::temp_dir().join("craftml-studio").join("logs");
            fs::create_dir_all(&log_dir).ok();
            
            let stdout_log = log_dir.join("backend-stdout.log");
            let stderr_log = log_dir.join("backend-stderr.log");
            
            let stdout_file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&stdout_log)
                .ok();
            
            let stderr_file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&stderr_log)
                .ok();
            
            if let Some(stdout) = stdout_file {
                prod_cmd.stdout(Stdio::from(stdout));
            }
            if let Some(stderr) = stderr_file {
                prod_cmd.stderr(Stdio::from(stderr));
            }
            
            prod_cmd.spawn()
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

    /// Check if backend is ready by polling health endpoint
    pub fn wait_for_ready(&self, max_wait_seconds: u64) -> Result<(), String> {
        use std::time::{Duration, Instant};
        use std::thread;
        
        let start = Instant::now();
        let timeout = Duration::from_secs(max_wait_seconds);
        
        while start.elapsed() < timeout {
            // Check if process is still running
            {
                let mut process_lock = self.process.lock().unwrap();
                if let Some(ref mut child) = *process_lock {
                    if let Ok(Some(_)) = child.try_wait() {
                        return Err("Backend process exited unexpectedly".to_string());
                    }
                } else {
                    return Err("Backend process not found".to_string());
                }
            }
            
            // Try to connect to health endpoint
            match reqwest::blocking::get("http://127.0.0.1:5000/api/health") {
                Ok(response) if response.status().is_success() => {
                    return Ok(());
                }
                _ => {
                    // Backend not ready yet, wait a bit
                    thread::sleep(Duration::from_millis(200));
                }
            }
        }
        
        Err(format!("Backend did not become ready within {} seconds", max_wait_seconds))
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}

#[tauri::command]
pub fn start_backend(
    state: State<BackendProcess>,
    _host: Option<String>,
    _port: Option<u16>,
    _log_level: Option<String>,
) -> Result<String, String> {
    // Try to get resource directory from app state
    // For now, fallback to start() which handles both dev and prod
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

#[tauri::command]
pub fn get_backend_logs() -> Result<serde_json::Value, String> {
    let log_dir = std::env::temp_dir().join("craftml-studio").join("logs");
    let stdout_log = log_dir.join("backend-stdout.log");
    let stderr_log = log_dir.join("backend-stderr.log");
    
    let stdout_content = fs::read_to_string(&stdout_log)
        .unwrap_or_else(|_| "No stdout log available".to_string());
    
    let stderr_content = fs::read_to_string(&stderr_log)
        .unwrap_or_else(|_| "No stderr log available".to_string());
    
    Ok(serde_json::json!({
        "stdout": stdout_content,
        "stderr": stderr_content,
        "stdout_path": stdout_log.to_string_lossy().to_string(),
        "stderr_path": stderr_log.to_string_lossy().to_string()
    }))
}
