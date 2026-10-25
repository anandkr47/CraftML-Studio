# Cloud GPUs

CraftML Studio can run **fine-tuning** and **inference** on rented GPUs, using your own accounts.
Nothing is sent anywhere until you choose a remote target, and everything stays optional: the
app works fully offline without it.

| Provider | Fine-tuning | Inference | You need |
|---|---|---|---|
| **RunPod** | on-demand pod | serverless endpoint (OpenAI-compatible) | API key, Hugging Face token |
| **Modal** | serverless GPU function | – | token id + secret, Hugging Face token |
| **Together AI** | – | hosted models | API key |
| **Replicate** | – | hosted models (best effort) | API token |
| **SSH host** | your Linux + NVIDIA server | a server you already run, via port-forward | SSH key |

## Setting up

Open **Settings → Cloud GPUs**.

* **RunPod / Modal / Together / Replicate** – paste the credentials and press *Save & verify*. They are
  checked with the provider first and discarded if rejected.
* **Hugging Face token** (RunPod and Modal) – add it under *Settings → Hugging Face*. It needs **write**
  access. It is used to move your dataset to the GPU and the trained adapter back through *private*
  repositories, which are deleted when the run ends.
* **SSH host** – add the host, user and a private key (Ed25519, ECDSA or RSA; use a key made just for
  this). Then press **Verify host key**, compare the fingerprint with the server's
  (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`), and trust it. A later change of the key is a hard
  error. The server must be Linux with an NVIDIA GPU, `python3`, `tar` and coreutils; Docker is optional.

### Running a fine-tune remotely

In the Fine-Tune wizard, step 3 → **Where to run**. For RunPod and Modal pick a GPU; the wizard shows the
listed price and a **worst-case cost** and asks you to acknowledge it. Every remote run has a hard time limit
(default 2 h).

The job page then looks like a local run: live loss, VRAM, logs. **Stop** also terminates the remote machine.
The finished adapter appears in Chat like any local model.

### Using cloud models in Chat

Chat → *Add a cloud model*. The model is tested before it is kept. Your messages go to the provider and
usage is billed there. Cloud models also work through the local OpenAI-compatible server (Deploy).

## How your money and data are protected

* A run's time limit is enforced **on the remote machine** (`timeout` on SSH hosts; a self-removing pod on
  RunPod; the function timeout on Modal), so it still stops if the app crashes or your laptop sleeps.
* The app terminates the remote resource when a run ends, fails or is stopped. If cleanup itself fails, you
  are told which resource to check.
* On startup, runs left over from a previous session are terminated. *Settings → Running remote
  resources → Check for stray resources* lists anything named `craftml-*` that isn't accounted for.
* Costs shown in the app are **estimates** from listed prices; your provider's invoice is authoritative.
* Credentials are stored encrypted. The OS keychain (macOS Keychain, Windows Credential Manager, Linux
  Secret Service) holds only the encryption key. If no keychain is available (e.g. headless Linux) the key
  lives in a permission-restricted file and the app says so. No API ever returns a stored secret, and secrets
  are scrubbed from logs.
* The local API only accepts requests from the desktop app: other web pages open in your browser can't
  call it (this matters because it can start paid GPUs).
* Your **dataset leaves your computer** for the provider (and, for RunPod/Modal, passes through a private
  Hugging Face repo). Don't use remote targets for data you aren't allowed to send there.

## Per-OS notes

* **macOS (Apple Silicon)** – nothing runs locally on the GPU; only orchestration. The first credential save
  may show a Keychain prompt: choose *Always Allow*.
* **Windows** – nothing needs OpenSSH or `ssh-agent`: keys are imported into the app. To make a key:
  `ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\craftml_ed25519` (PowerShell), then paste the private key.
  Behind a corporate proxy set `HTTPS_PROXY`.
* **Linux** – without a Secret Service (headless, minimal desktops) credentials fall back to the protected
  file. Install `gnome-keyring` or KeePassXC's Secret Service for keychain storage.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "…hasn't been verified yet" | Verify and trust the SSH host key in Settings. |
| "…host key … CHANGED" | The server was reinstalled, or someone is intercepting. Remove and re-add the host only if you expect it. |
| RunPod "isn't available right now" | That GPU is out of stock; pick another. |
| Run stuck on "Waiting for the pod to start" | Image pull and package install take a few minutes; the app gives up after 25 min, and if the pod dies it shows the log the pod uploaded. |
| "Hugging Face refused to …" | The token lacks write access. |
| Modal / RunPod SDK errors in a packaged build | See *Known limitations*. |

## Known limitations

* A run is terminated, not resumed, if the app restarts mid-run. (The adapter, if it finished, stays in the
  private Hugging Face repo until you delete it.)
* RunPod's pod self-removal relies on `runpodctl` and the pod-scoped key RunPod injects; the command syntax
  differs between versions, so several forms are tried, and the app also terminates the pod itself.
* Replicate language models take model-specific inputs; the adapter sends a generic chat-style prompt.
* The vendor SDK surfaces (RunPod pod fields, Modal queues/serialized functions) are isolated behind adapters
  and covered by tests with fakes; they should be smoke-tested against real accounts when upgrading SDKs.
* Packaged builds bundle the provider SDKs and the worker sources as data files; verify a release build
  can start a run before publishing.
