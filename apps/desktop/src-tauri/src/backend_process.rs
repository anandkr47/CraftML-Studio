//! Launches and supervises the Python backend.
//!
//! * Packaged app: the PyInstaller build in `<resources>/bin` is copied into a per-user,
//!   per-build directory (re-copied whenever the bundled build changes) and run from there.
//! * Development (or a release build without a bundled backend): `apps/backend/run_server.py`
//!   is run with the project's virtualenv interpreter.
//!
//! The backend always listens on `127.0.0.1:BACKEND_PORT`; the UI uses the same address
//! (`apps/desktop/src/config.ts`). A backend that is already answering on that port (e.g. one
//! started with `scripts/dev.sh --backend-only`) is reused instead of starting a second one.

use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant, UNIX_EPOCH};

use serde::Serialize;
use tauri::State;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// Keep in sync with `apps/desktop/src/config.ts` and `apps/backend/run_server.py`.
/// (Port 5000 is taken by the AirPlay Receiver on macOS; this one is below every OS's ephemeral range.)
pub const BACKEND_PORT: u16 = 17860;
const SERVICE_NAME: &str = "craftml-backend";
const LOG_ROTATE_BYTES: u64 = 5 * 1024 * 1024;
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// How to start the backend, resolved once at app startup.
#[derive(Clone, Debug)]
pub struct LaunchConfig {
    pub app_version: String,
    pub resource_dir: Option<PathBuf>,
    /// Per-user directory the packaged backend is copied into.
    pub runtime_dir: PathBuf,
    pub log_dir: PathBuf,
}

#[derive(Serialize, Clone, Debug)]
pub struct BackendStatus {
    /// "running" (started by us), "external" (already running, reused), "starting", "stopped" or "failed"
    pub state: String,
    pub pid: Option<u32>,
    pub mode: Option<String>,
    pub error: Option<String>,
    /// What is happening while starting (e.g. unpacking the backend after an install or update)
    pub detail: Option<String>,
    pub port: u16,
}

/// Outcome of `start`: only `Spawned` needs `wait_for_ready`.
#[derive(Debug, PartialEq)]
pub enum Started {
    Spawned,
    AlreadyRunning,
    AlreadyStarting,
    Adopted,
}

enum Health {
    Ours(Option<String>), // reported app version
    Foreign,
    Down,
}

#[derive(Default)]
struct Inner {
    child: Option<Child>,
    external: bool,
    starting: bool,
    mode: Option<String>,
    error: Option<String>,
    detail: Option<String>,
}

pub struct BackendProcess {
    inner: Mutex<Inner>,
    config: Mutex<Option<LaunchConfig>>,
}

impl BackendProcess {
    pub fn new() -> Self {
        BackendProcess { inner: Mutex::new(Inner::default()), config: Mutex::new(None) }
    }

    pub fn configure(&self, config: LaunchConfig) {
        *self.config.lock().unwrap() = Some(config);
    }

    fn config(&self) -> Result<LaunchConfig, String> {
        self.config.lock().unwrap().clone().ok_or_else(|| "Backend launcher is not configured".to_string())
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, Inner> {
        // A panic while holding the lock must not brick the launcher.
        self.inner.lock().unwrap_or_else(|p| p.into_inner())
    }

    pub fn log_dir(&self) -> PathBuf {
        self.config
            .lock()
            .unwrap()
            .as_ref()
            .map(|c| c.log_dir.clone())
            .unwrap_or_else(|| std::env::temp_dir().join("craftml-studio").join("logs"))
    }

    fn set_detail(&self, detail: &str) {
        self.lock().detail = Some(detail.to_string());
    }

    /// Start the backend (or adopt one already running); then use `wait_for_ready`.
    ///
    /// The slow parts (probing the port, unpacking the bundled backend after an install or update)
    /// run without holding the state lock, so `status()` (polled by the UI) never blocks on them.
    pub fn start(&self) -> Result<Started, String> {
        let config = self.config()?;
        {
            let mut inner = self.lock();
            if inner.starting {
                return Ok(Started::AlreadyStarting);
            }
            if let Some(child) = inner.child.as_mut() {
                if let Ok(None) = child.try_wait() {
                    return Ok(Started::AlreadyRunning);
                }
                inner.child = None;
            }
            inner.external = false;
            inner.error = None;
            inner.starting = true;
            inner.detail = Some("Starting the backend…".to_string());
        }
        let result = self.launch(&config);
        let mut inner = self.lock();
        match &result {
            Err(e) => {
                inner.starting = false;
                inner.error = Some(e.clone());
                inner.detail = None;
            }
            Ok(_) if inner.external => {
                inner.starting = false;
                inner.detail = None;
            }
            Ok(_) => {} // `wait_for_ready` ends the starting phase
        }
        result
    }

    fn launch(&self, config: &LaunchConfig) -> Result<Started, String> {
        match probe_health() {
            Health::Ours(version) => {
                if let Some(v) = version.filter(|v| !v.is_empty() && *v != config.app_version) {
                    return Err(format!(
                        "A CraftML backend from version {v} is still running on port {BACKEND_PORT}. \
                         Quit other CraftML Studio windows (or end the 'craftml-backend' process) and retry."
                    ));
                }
                let mut inner = self.lock();
                inner.external = true;
                inner.mode = Some("external".to_string());
                return Ok(Started::Adopted);
            }
            Health::Foreign => {
                return Err(format!(
                    "Port {BACKEND_PORT} is in use by another application, so the CraftML backend can't start. \
                     Close that application and retry."
                ));
            }
            Health::Down => {}
        }

        self.set_detail("Preparing the backend (the first start after installing or updating takes a while)…");
        let (mut cmd, mode) = build_command(config)?;
        cmd.env("CRAFTML_APP_VERSION", &config.app_version)
            // the backend exits by itself if this process disappears (crash, kill -9)
            .env("CRAFTML_PARENT_PID", std::process::id().to_string())
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(BACKEND_PORT.to_string())
            .stdin(Stdio::null());
        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);

        let (stdout, stderr) = open_logs(&config.log_dir)?;
        cmd.stdout(stdout).stderr(stderr);

        let child = cmd.spawn().map_err(|e| format!("Failed to start the backend ({mode}): {e}"))?;
        eprintln!("Backend started ({mode}), pid {}, logs in {:?}", child.id(), config.log_dir);
        let mut inner = self.lock();
        inner.child = Some(child);
        inner.mode = Some(mode.clone());
        inner.detail = Some("Loading models and services…".to_string());
        Ok(Started::Spawned)
    }

    /// Poll the health endpoint until it answers, the process dies, or the timeout passes.
    pub fn wait_for_ready(&self, timeout: Duration) -> Result<(), String> {
        let started = Instant::now();
        let result = loop {
            {
                let mut inner = self.lock();
                if !inner.external {
                    match inner.child.as_mut().map(|c| c.try_wait()) {
                        None => break Err("Backend process not started".to_string()),
                        Some(Ok(Some(status))) => {
                            inner.child = None;
                            break Err(format!("Backend exited during startup ({status}). See the backend logs."));
                        }
                        _ => {}
                    }
                }
            }
            match probe_health() {
                Health::Ours(_) => break Ok(()),
                Health::Foreign => {
                    break Err(format!("Port {BACKEND_PORT} is answered by another application"))
                }
                Health::Down => {}
            }
            if started.elapsed() > timeout {
                break Err(format!("Backend did not become ready within {} seconds", timeout.as_secs()));
            }
            std::thread::sleep(Duration::from_millis(250));
        };
        let mut inner = self.lock();
        inner.starting = false;
        inner.detail = None;
        if let Err(e) = &result {
            inner.error = Some(e.clone());
        }
        result
    }

    /// Stop the backend we started (an adopted external backend is left alone).
    pub fn stop(&self) -> Result<String, String> {
        let mut inner = self.lock();
        inner.external = false;
        let Some(mut child) = inner.child.take() else {
            return Ok("Backend was not running".to_string());
        };
        if let Ok(Some(_)) = child.try_wait() {
            return Ok("Backend had already exited".to_string());
        }
        // Ask politely first so uvicorn can finish requests and close SQLite cleanly.
        #[cfg(unix)]
        {
            let _ = Command::new("kill").arg("-TERM").arg(child.id().to_string()).status();
            let deadline = Instant::now() + Duration::from_secs(5);
            while Instant::now() < deadline {
                if let Ok(Some(_)) = child.try_wait() {
                    return Ok("Backend stopped".to_string());
                }
                std::thread::sleep(Duration::from_millis(100));
            }
        }
        child.kill().map_err(|e| format!("Failed to stop backend: {e}"))?;
        let _ = child.wait();
        Ok("Backend stopped".to_string())
    }

    pub fn status(&self) -> BackendStatus {
        let mut inner = self.lock();
        let mut pid = None;
        let state = if inner.external {
            "external"
        } else if let Some(child) = inner.child.as_mut() {
            match child.try_wait() {
                Ok(None) => {
                    pid = Some(child.id());
                    if inner.starting { "starting" } else { "running" }
                }
                Ok(Some(status)) => {
                    inner.error.get_or_insert_with(|| format!("Backend exited ({status})"));
                    inner.child = None;
                    "failed"
                }
                Err(_) => "failed",
            }
        } else if inner.starting {
            "starting"
        } else if inner.error.is_some() {
            "failed"
        } else {
            "stopped"
        };
        BackendStatus {
            state: state.to_string(),
            pid,
            mode: inner.mode.clone(),
            error: inner.error.clone(),
            detail: inner.detail.clone(),
            port: BACKEND_PORT,
        }
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        let _ = self.stop();
    }
}

// ---------------------------------------------------------------------------------------------
// Health probe (plain std HTTP/1.1, so no HTTP client crate or async runtime is needed)

fn probe_health() -> Health {
    probe_health_at(BACKEND_PORT)
}

fn probe_health_at(port: u16) -> Health {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(400)) else {
        return Health::Down;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return Health::Down;
    }
    let mut buf = Vec::new();
    let _ = stream.take(64 * 1024).read_to_end(&mut buf);
    if buf.is_empty() {
        // Accepted but said nothing: a backend still booting or something else entirely.
        return Health::Down;
    }
    let text = String::from_utf8_lossy(&buf);
    let ok_status = text.starts_with("HTTP/1.1 200") || text.starts_with("HTTP/1.0 200");
    let Some(body) = text.split_once("\r\n\r\n").map(|(_, b)| b) else {
        return Health::Foreign;
    };
    if !ok_status {
        return Health::Foreign;
    }
    match serde_json::from_str::<serde_json::Value>(body.trim()) {
        Ok(json) if json.get("service").and_then(|s| s.as_str()) == Some(SERVICE_NAME) => {
            Health::Ours(json.get("app_version").and_then(|v| v.as_str()).map(str::to_string))
        }
        _ => Health::Foreign,
    }
}

// ---------------------------------------------------------------------------------------------
// Command resolution

/// The packaged backend: a PyInstaller one-folder build packed by `scripts/pack_sidecar.py`.
/// (An archive, because Tauri's resource copy would follow the symlinks PyInstaller relies on.)
const BACKEND_ARCHIVE: &str = "backend.tar.gz";

fn backend_exe_name() -> String {
    format!("craftml-backend{}", std::env::consts::EXE_SUFFIX)
}

fn build_command(config: &LaunchConfig) -> Result<(Command, String), String> {
    let bundled = config
        .resource_dir
        .as_ref()
        .map(|rd| rd.join("bin").join(BACKEND_ARCHIVE))
        .filter(|archive| archive.is_file());

    // Debug builds prefer the source tree so code changes apply without rebuilding the sidecar.
    let prefer_source = cfg!(debug_assertions) || std::env::var_os("CRAFTML_BACKEND_DIR").is_some();
    if !prefer_source {
        if let Some(archive) = bundled.as_ref() {
            return packaged_command(archive, config);
        }
    }
    match find_backend_dir() {
        Some(dir) => Ok((source_command(&dir), "source".to_string())),
        None => match bundled {
            Some(archive) => packaged_command(&archive, config),
            None => Err(
                "The backend was not found: this build has no bundled backend and apps/backend/run_server.py \
                 could not be located. Run scripts/build_desktop.sh, or set CRAFTML_BACKEND_DIR."
                    .to_string(),
            ),
        },
    }
}

fn packaged_command(archive: &Path, config: &LaunchConfig) -> Result<(Command, String), String> {
    let dir = install_packaged_backend(archive, &config.runtime_dir, &config.app_version)?;
    let mut cmd = Command::new(dir.join(backend_exe_name()));
    cmd.current_dir(&dir).env("CRAFTML_ENV", "prod");
    Ok((cmd, "packaged".to_string()))
}

fn source_command(backend_dir: &Path) -> Command {
    let python = find_python(backend_dir);
    let mut cmd = Command::new(&python);
    cmd.arg(backend_dir.join("run_server.py")).current_dir(backend_dir);
    eprintln!("Running backend from source with {:?}", python);
    cmd
}

/// `CRAFTML_BACKEND_DIR`, else the nearest ancestor of the executable or working directory
/// that contains `apps/backend/run_server.py`.
fn find_backend_dir() -> Option<PathBuf> {
    if let Some(dir) = std::env::var_os("CRAFTML_BACKEND_DIR").map(PathBuf::from) {
        return dir.join("run_server.py").is_file().then_some(dir);
    }
    let starts = [std::env::current_exe().ok(), std::env::current_dir().ok()];
    starts.into_iter().flatten().find_map(|start| {
        start
            .ancestors()
            .map(|a| a.join("apps").join("backend"))
            .find(|candidate| candidate.join("run_server.py").is_file())
    })
}

/// `CRAFTML_PYTHON`, else the backend's virtualenv, else the interpreter on PATH.
fn find_python(backend_dir: &Path) -> PathBuf {
    if let Some(p) = std::env::var_os("CRAFTML_PYTHON") {
        return PathBuf::from(p);
    }
    let rel: &[&str] = if cfg!(windows) { &["Scripts", "python.exe"] } else { &["bin", "python"] };
    let mut roots = vec![backend_dir.join("venv"), backend_dir.join(".venv")];
    if let Some(project) = backend_dir.parent().and_then(Path::parent) {
        roots.push(project.join(".venv"));
        roots.push(project.join("venv"));
    }
    roots
        .into_iter()
        .map(|root| rel.iter().fold(root, |p, part| p.join(part)))
        .find(|p| p.is_file())
        .unwrap_or_else(|| PathBuf::from(if cfg!(windows) { "python" } else { "python3" }))
}

// ---------------------------------------------------------------------------------------------
// Packaged backend installation

/// Identifies one bundled build: app version plus the archive's size and mtime, so a rebuilt
/// bundle with an unchanged version number is still picked up.
fn build_stamp(archive: &Path, app_version: &str) -> String {
    let meta = fs::metadata(archive).ok();
    let len = meta.as_ref().map(|m| m.len()).unwrap_or(0);
    let mtime = meta
        .and_then(|m| m.modified().ok())
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{app_version}-{len:x}-{mtime:x}")
}

const COMPLETE_MARKER: &str = ".craftml-complete";

/// Unpack the bundled archive into `<runtime_dir>/<stamp>` unless that build is already installed.
/// It is unpacked into a temporary directory first and renamed into place, so an interrupted
/// install is never used. Older builds are removed best-effort (on Windows a running one stays
/// locked and goes next time).
fn install_packaged_backend(archive: &Path, runtime_dir: &Path, app_version: &str) -> Result<PathBuf, String> {
    let stamp = build_stamp(archive, app_version);
    let target = runtime_dir.join(&stamp);
    if !target.join(COMPLETE_MARKER).is_file() {
        fs::create_dir_all(runtime_dir).map_err(|e| format!("Can't create {runtime_dir:?}: {e}"))?;
        let staging = runtime_dir.join(format!(".staging-{}-{}", stamp, std::process::id()));
        let _ = fs::remove_dir_all(&staging);
        if let Err(e) = unpack(archive, &staging) {
            let _ = fs::remove_dir_all(&staging);
            return Err(e);
        }
        if !staging.join(backend_exe_name()).is_file() {
            let _ = fs::remove_dir_all(&staging);
            return Err(format!("{archive:?} does not contain {}", backend_exe_name()));
        }
        fs::write(staging.join(COMPLETE_MARKER), &stamp).map_err(|e| e.to_string())?;
        let _ = fs::remove_dir_all(&target);
        if let Err(e) = fs::rename(&staging, &target) {
            let _ = fs::remove_dir_all(&staging);
            return Err(format!("Can't install the backend into {target:?}: {e}"));
        }
    }
    if let Ok(entries) = fs::read_dir(runtime_dir) {
        for entry in entries.flatten() {
            if entry.file_name() != stamp.as_str() && entry.path().is_dir() {
                let _ = fs::remove_dir_all(entry.path());
            }
        }
    }
    Ok(target)
}

/// Extract a .tar.gz, keeping permissions and symlinks. `unpack` refuses entries that would land
/// outside `dest` (absolute paths, `..`).
fn unpack(archive: &Path, dest: &Path) -> Result<(), String> {
    let file = fs::File::open(archive).map_err(|e| format!("Can't open {archive:?}: {e}"))?;
    let mut tar = tar::Archive::new(flate2::read::GzDecoder::new(std::io::BufReader::new(file)));
    tar.set_preserve_permissions(true);
    tar.set_preserve_mtime(true);
    tar.set_overwrite(true);
    fs::create_dir_all(dest).map_err(|e| format!("Can't create {dest:?}: {e}"))?;
    tar.unpack(dest).map_err(|e| format!("Can't unpack the backend from {archive:?}: {e}"))
}

// ---------------------------------------------------------------------------------------------
// Logs

fn log_paths(log_dir: &Path) -> (PathBuf, PathBuf) {
    (log_dir.join("backend-stdout.log"), log_dir.join("backend-stderr.log"))
}

fn open_logs(log_dir: &Path) -> Result<(Stdio, Stdio), String> {
    fs::create_dir_all(log_dir).map_err(|e| format!("Can't create log directory {log_dir:?}: {e}"))?;
    let (out, err) = log_paths(log_dir);
    let open = |path: &Path| -> Result<Stdio, String> {
        if fs::metadata(path).map(|m| m.len() > LOG_ROTATE_BYTES).unwrap_or(false) {
            let _ = fs::rename(path, path.with_extension("log.1"));
        }
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(|e| format!("Can't open {path:?}: {e}"))?;
        let _ = writeln!(&file, "\n===== backend start (pid {}) =====", std::process::id());
        Ok(Stdio::from(file))
    };
    Ok((open(&out)?, open(&err)?))
}

/// Last `max` bytes of a log file (a character split by the cut becomes U+FFFD).
fn tail(path: &Path, max: usize) -> Option<String> {
    let bytes = fs::read(path).ok()?;
    let start = bytes.len().saturating_sub(max);
    Some(String::from_utf8_lossy(&bytes[start..]).into_owned())
}

// ---------------------------------------------------------------------------------------------
// Commands

/// How long the first start may take: unpacking ~1 GB and the OS scanning new libraries
/// (antivirus, Gatekeeper) can take minutes on a slow machine. A crash is still noticed at once.
pub const READY_TIMEOUT: Duration = Duration::from_secs(600);

/// Start the backend and wait for it, off the calling thread.
pub fn start_in_background(backend: std::sync::Arc<BackendProcess>) {
    std::thread::spawn(move || match backend.start() {
        Ok(Started::Spawned) => match backend.wait_for_ready(READY_TIMEOUT) {
            Ok(()) => eprintln!("Backend is ready"),
            Err(e) => eprintln!("Backend failed to start: {e}"),
        },
        Ok(other) => eprintln!("Backend: {other:?}"),
        Err(e) => eprintln!("Backend failed to start: {e}"),
    });
}

/// (Re)start the backend in the background; poll `backend_status` for the outcome.
#[tauri::command]
pub fn start_backend(state: State<'_, std::sync::Arc<BackendProcess>>) -> Result<String, String> {
    start_in_background(state.inner().clone());
    Ok("Starting the backend".to_string())
}

#[tauri::command]
pub fn stop_backend(state: State<'_, std::sync::Arc<BackendProcess>>) -> Result<String, String> {
    state.stop()
}

#[tauri::command]
pub fn backend_status(state: State<'_, std::sync::Arc<BackendProcess>>) -> BackendStatus {
    state.status()
}

#[tauri::command]
pub fn get_backend_logs(state: State<'_, std::sync::Arc<BackendProcess>>) -> serde_json::Value {
    logs_json(&state.log_dir())
}

pub fn logs_json(log_dir: &Path) -> serde_json::Value {
    let (out, err) = log_paths(log_dir);
    serde_json::json!({
        "stdout": tail(&out, 64 * 1024).unwrap_or_default(),
        "stderr": tail(&err, 64 * 1024).unwrap_or_default(),
        "stdout_path": out.to_string_lossy(),
        "stderr_path": err.to_string_lossy(),
        "log_dir": log_dir.to_string_lossy(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    /// Serve one canned HTTP response on an ephemeral port; returns the port.
    fn serve_once(response: &'static str) -> u16 {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let mut buf = [0u8; 1024];
                let _ = stream.read(&mut buf);
                let _ = stream.write_all(response.as_bytes());
            }
        });
        port
    }

    #[test]
    fn health_recognises_our_backend_and_version() {
        let port = serve_once(
            "HTTP/1.1 200 OK\r\ncontent-type: application/json\r\n\r\n\
             {\"status\":\"healthy\",\"service\":\"craftml-backend\",\"app_version\":\"1.2.3\"}",
        );
        assert!(matches!(probe_health_at(port), Health::Ours(Some(v)) if v == "1.2.3"));
        let port = serve_once(
            "HTTP/1.1 200 OK\r\n\r\n{\"status\":\"healthy\",\"service\":\"craftml-backend\",\"app_version\":null}",
        );
        assert!(matches!(probe_health_at(port), Health::Ours(None)));
    }

    #[test]
    fn health_rejects_other_services() {
        // e.g. the macOS AirPlay receiver on port 5000
        let port = serve_once("HTTP/1.1 403 Forbidden\r\nServer: AirTunes/960.13.1\r\nContent-Length: 0\r\n\r\n");
        assert!(matches!(probe_health_at(port), Health::Foreign));
        let port = serve_once("HTTP/1.1 200 OK\r\n\r\n{\"service\":\"something-else\"}");
        assert!(matches!(probe_health_at(port), Health::Foreign));
        let port = serve_once("HTTP/1.1 200 OK\r\n\r\n<html>hello</html>");
        assert!(matches!(probe_health_at(port), Health::Foreign));
    }

    #[test]
    fn health_down_when_nothing_listens() {
        let port = TcpListener::bind("127.0.0.1:0").unwrap().local_addr().unwrap().port(); // freed on drop
        assert!(matches!(probe_health_at(port), Health::Down));
    }

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("craftml-launcher-test-{}-{}", name, std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    /// A fake packaged backend: the executable, a library and (on Unix) a relative symlink.
    fn write_archive(path: &Path, exe_body: &[u8]) {
        let file = fs::File::create(path).unwrap();
        let gz = flate2::write::GzEncoder::new(file, flate2::Compression::fast());
        let mut tar = tar::Builder::new(gz);
        let mut add = |name: &str, body: &[u8], mode: u32| {
            let mut header = tar::Header::new_gnu();
            header.set_size(body.len() as u64);
            header.set_mode(mode);
            header.set_cksum();
            tar.append_data(&mut header, name, body).unwrap();
        };
        add(&backend_exe_name(), exe_body, 0o755);
        add("_internal/Python.framework/Versions/3.12/Python", b"lib", 0o644);
        #[cfg(unix)]
        {
            let mut header = tar::Header::new_gnu();
            header.set_entry_type(tar::EntryType::Symlink);
            header.set_size(0);
            header.set_mode(0o777);
            tar.append_link(&mut header, "_internal/Python", "Python.framework/Versions/3.12/Python").unwrap();
        }
        tar.into_inner().unwrap().finish().unwrap();
    }

    #[test]
    fn packaged_backend_installs_once_and_reinstalls_on_change() {
        let root = temp_dir("install");
        let archive = root.join(BACKEND_ARCHIVE);
        write_archive(&archive, b"v1");
        let runtime = root.join("runtime");

        let first = install_packaged_backend(&archive, &runtime, "0.1.0").unwrap();
        assert_eq!(fs::read(first.join(backend_exe_name())).unwrap(), b"v1");
        assert!(first.join(COMPLETE_MARKER).is_file());
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = fs::metadata(first.join(backend_exe_name())).unwrap().permissions().mode();
            assert_eq!(mode & 0o111, 0o111);
            // the symlink survives as a symlink (Tauri's resource copy would have flattened it)
            let link = first.join("_internal").join("Python");
            assert!(fs::symlink_metadata(&link).unwrap().file_type().is_symlink());
            assert_eq!(fs::read(&link).unwrap(), b"lib");
        }

        // Same build: reused as is.
        fs::write(first.join("marker"), b"kept").unwrap();
        let again = install_packaged_backend(&archive, &runtime, "0.1.0").unwrap();
        assert_eq!(again, first);
        assert!(again.join("marker").is_file());

        // New app version: fresh install, old one removed.
        let upgraded = install_packaged_backend(&archive, &runtime, "0.2.0").unwrap();
        assert_ne!(upgraded, first);
        assert!(!first.exists());

        // Rebuilt archive with the same version (different size): also a fresh install.
        write_archive(&archive, b"v2-rebuilt-with-a-longer-body");
        let rebuilt = install_packaged_backend(&archive, &runtime, "0.2.0").unwrap();
        assert_ne!(rebuilt, upgraded);
        assert_eq!(fs::read(rebuilt.join(backend_exe_name())).unwrap(), b"v2-rebuilt-with-a-longer-body");

        // An interrupted install (no completion marker) is never used.
        fs::remove_file(rebuilt.join(COMPLETE_MARKER)).unwrap();
        fs::remove_file(rebuilt.join(backend_exe_name())).unwrap();
        let repaired = install_packaged_backend(&archive, &runtime, "0.2.0").unwrap();
        assert!(repaired.join(backend_exe_name()).is_file());

        // A broken archive is an error, and leaves nothing half-installed behind.
        fs::write(&archive, b"not a tarball").unwrap();
        assert!(install_packaged_backend(&archive, &runtime, "0.3.0").is_err());
        let leftovers: Vec<_> = fs::read_dir(&runtime).unwrap().flatten().map(|e| e.file_name()).collect();
        assert!(leftovers.iter().all(|n| !n.to_string_lossy().starts_with(".staging")), "{leftovers:?}");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn python_prefers_the_backend_virtualenv() {
        let root = temp_dir("python");
        let backend = root.join("apps").join("backend");
        let rel: &[&str] = if cfg!(windows) { &["Scripts", "python.exe"] } else { &["bin", "python"] };
        let venv_python = rel.iter().fold(backend.join("venv"), |p, part| p.join(part));
        fs::create_dir_all(venv_python.parent().unwrap()).unwrap();
        fs::write(&venv_python, b"").unwrap();
        if std::env::var_os("CRAFTML_PYTHON").is_none() {
            assert_eq!(find_python(&backend), venv_python);
        }
        fs::remove_file(&venv_python).unwrap();
        if std::env::var_os("CRAFTML_PYTHON").is_none() {
            let fallback = find_python(&backend);
            assert!(fallback == PathBuf::from("python3") || fallback == PathBuf::from("python"));
        }
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn finds_backend_from_the_dev_binary_location() {
        // target/debug/craftml-studio lives under apps/desktop/src-tauri, so walking up finds apps/backend.
        if std::env::var_os("CRAFTML_BACKEND_DIR").is_none() {
            let dir = find_backend_dir().expect("apps/backend should be found from the workspace");
            assert!(dir.join("run_server.py").is_file());
        }
    }

    #[test]
    fn log_tail_handles_short_long_and_missing_files() {
        let root = temp_dir("logs");
        let (out, _) = log_paths(&root);
        assert!(tail(&out, 10).is_none());
        fs::write(&out, "héllo wörld, this is a long line").unwrap();
        assert_eq!(tail(&out, 1000).unwrap(), "héllo wörld, this is a long line");
        assert_eq!(tail(&out, 4).unwrap(), "line");
        let (stdout, _stderr) = open_logs(&root).unwrap();
        drop(stdout);
        assert!(fs::read_to_string(&out).unwrap().contains("===== backend start"));
        let _ = fs::remove_dir_all(&root);
    }
}
