# User guide

CraftML Studio runs language models on your own computer. Everything stays on your machine unless you
choose otherwise: downloading or publishing a model, chatting with a cloud model, or fine-tuning on a
rented GPU.

When the app starts it launches its local engine. The first start after installing or updating
unpacks it and can take a few minutes while your system checks the new files; later starts take
seconds. If the engine can't start, the loading screen shows why, along with the end of the log
and a **Retry** button.

The status bar at the bottom shows live CPU, RAM, GPU and VRAM use, and warns you before memory runs
out.

## Getting a model

* **Download:** go to **Deploy & Endpoints → Download a model**, enter a Hugging Face id (for
  example `HuggingFaceTB/SmolLM2-360M-Instruct`) and, for GGUF repositories, the file name. Gated
  models (Llama, Gemma) need a Hugging Face token: save one in **Settings**.
* **Fine-tune** your own (below), or **compress** one you have (below).

Models you download, train or compress appear everywhere: Chat, Compress, Deploy.

## Chat

1. Pick a model at the top. Cloud models carry a cloud badge.
2. Type a message. Replies stream in, with Markdown and highlighted, copyable code.
3. **Parameters:** temperature, top-p, top-k, repetition penalty, max tokens and the system prompt.
   They are saved with the conversation.
4. Conversations are saved automatically and listed in **History**. Export one as Markdown or JSON;
   the desktop app saves it to your Downloads folder.

If a model plus the context you ask for won't fit in memory, you're warned before you send. Instruct
or chat models give the best results; base models (no chat template) are prompted with a plain
`User:` / `Assistant:` format.

### Answering from your documents

Turn on **Ground with Knowledge Base** in a chat. The most relevant passages from your documents are
given to the model, and the reply lists them under **Sources**.

## Knowledge Base

Drop PDF, Word (`.docx`), Markdown or text files onto the page. They are split into passages and
indexed on your computer (the embedding model downloads once, about 130 MB). Use **Test retrieval**
to see which passages a question finds, and delete documents you no longer need. Scanned PDFs
without a text layer can't be read; run OCR first.

## Fine-Tune

A four-step wizard:

1. **Base model:** a Hugging Face id or one of your local models. Small models (0.5–3B) are the
   practical choice on a laptop.
2. **Dataset:** upload JSONL, JSON, CSV, Parquet or TXT. The format is detected (instruction /
   output, prompt / completion, chat messages, or plain text) and previewed; problems are listed
   before you start.
3. **Settings:** the method, and where to run it.
   * **QLoRA · 4-bit** (NVIDIA GPU) uses the least memory.
   * **LoRA · 8-bit** (NVIDIA GPU).
   * **LoRA · standard precision** runs anywhere, including Apple Silicon and CPU.
   * **Full fine-tuning** needs a lot of memory.

   Epochs, learning rate, batch size, sequence length and checkpoint interval have sensible defaults.
   *Where to run* is this computer or a cloud GPU (see [CLOUD.md](CLOUD.md)); cloud runs show an
   estimated cost and a hard time limit before you start.
4. **Review** and start.

The job page shows live loss, learning rate and VRAM charts, logs and checkpoints. **Stop** ends the
run; for cloud runs it also shuts the remote machine down. The finished adapter appears in Chat.

## Compress

Choose a model and a preset, or pick the method yourself:

| Preset | What it does |
|---|---|
| Fit on 8 GB VRAM | INT4 (NVIDIA): a 7B model shrinks to about 4 GB |
| Apple Silicon / CPU | GGUF Q4_K_M: the usual best balance for llama.cpp |
| Edge device | GGUF Q3_K_M for phones, Raspberry Pi and other small devices |
| Max quality | GGUF Q8_0: about half the size, almost no quality loss |

The page recommends a preset for your hardware. GGUF needs llama.cpp's converter; the first time,
**Set up llama.cpp** downloads it (Git is required). The result is a new model with a before/after
report: file size, memory, perplexity (lower is better) and speed.

If llama.cpp can't run a particular architecture, the GGUF file is still created, but chatting with it
shows an error message instead of loading it.

## Deploy & Endpoints

* **Local API server:** serve any model at an OpenAI-compatible address on your machine
  (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`), optionally protected with an API key.
  The page shows ready-to-copy `curl` and Python examples. Use it from any OpenAI client by setting
  the base URL.
* **Export to Hugging Face:** publish a model or adapter to a repository (needs a token with write
  access). A model card with usage instructions is generated.

## Settings

* **Hugging Face token:** stored encrypted on this computer and never shown again after saving.
* **Cloud GPUs:** connect RunPod, Modal, Together or Replicate, and add SSH hosts (see
  [CLOUD.md](CLOUD.md)). The page says whether secrets are protected by your system keychain.
* **Application updates.**

## Troubleshooting

| Problem | What to do |
|---|---|
| "Port 17860 is in use by another application" | Another program uses the app's port; close it and press Retry. |
| "A CraftML backend from version … is still running" | Quit the other CraftML Studio window, then Retry. |
| Download is very slow or stalls | Check the network; behind a proxy, set `HTTPS_PROXY`. Gated models need a token. |
| Out of memory while training | Use a smaller model, QLoRA (NVIDIA), a smaller batch size or a shorter sequence length. |
| "INT4/INT8/GPTQ/AWQ needs an NVIDIA GPU" | Use a GGUF preset on Apple Silicon or CPU. |
| Where are the logs? | See [SETUP.md](SETUP.md#where-things-are-stored), or run `scripts/check_backend_logs`. |
