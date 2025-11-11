# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevEquality is a voice-controlled assistant system with a client-server architecture. The Windows client captures audio from microphone, sends it to the WSL server for processing, and plays back synthesized responses. The server uses a LangGraph-based workflow to process audio through ASR (Automatic Speech Recognition), LLM reasoning, and TTS (Text-to-Speech) pipelines.

## Architecture

### Client (client_windows/)
- **microphone.py**: Windows client that records audio via spacebar hotkey, sends filename to server via TCP socket, and plays back response audio
- **config.ini**: Shared configuration for audio settings (16kHz, mono) and server connection (localhost:65437)
- Uses threading for continuous audio recording with start/stop control
- Implements blocking flow: waits for server "True" response before allowing new recordings

### Server (server_wsl/)
- **main.py**: TCP server that receives audio filenames and invokes LangGraph workflow
- **src/graph/**: LangGraph workflow implementation
  - **workflow.py**: Defines StateGraph with nodes: transcribe ’ synthesize
  - **state.py**: AgentState TypedDict tracking messages, audio paths, current context (project/dir/file), and output
  - **nodes.py**: Graph nodes that call ASR and TTS services, singleton instances loaded at module import
- **src/services/**: ML model services (all singletons)
  - **asr_service.py**: NVIDIA NeMo QuartzNet15x5Base-En for speech-to-text
  - **tts_service.py**: NVIDIA NeMo FastPitch + HiFi-GAN for text-to-speech
  - **llm_service.py**: Placeholder for LLM integration (currently minimal implementation)
- **src/core/**: Tool modules for future file/directory/project operations (currently stubs)
- **projects/**: Empty workspace for future project management
- **temp_audio/**: Audio file storage
  - received/: Input audio from client
  - pronounced/: Output audio to client (output.wav)
- **state/**: Persistent state storage (state.json)

### Key Design Patterns
- **Singleton Services**: ASR and TTS services use singleton pattern to prevent reloading heavy ML models
- **State Persistence**: AgentState is saved/loaded from JSON between invocations to maintain conversation context
- **Shared Paths**: Client and server both reference paths relative to project root; audio files stored in server_wsl/temp_audio/
- **LangGraph Workflow**: Uses LangGraph's StateGraph for declarative node-based processing pipeline

## Development Setup

### Python Version
Python 3.12

### Windows Client Setup
```bash
cd client_windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### WSL Server Setup
```bash
cd server_wsl
pip install nemo_toolkit[asr]
pip install nemo_toolkit[tts]
pip install langchain langgraph langchain-google-genai
```

### Environment Configuration
1. Copy `.env_example` to `.env` in project root
2. Add your `GEMINI_API_KEY` for LLM integration (when implemented)

## Running the System

### Start Server (WSL)
```bash
cd server_wsl
python main.py
```
Server listens on localhost:65437 and loads ASR/TTS models on startup (may take time).

### Start Client (Windows)
```bash
cd client_windows
python microphone.py
```
Press spacebar to start/stop recording. Client sends audio filename to server and waits for processing.

### Testing Without Client
Server can run standalone for testing:
```python
# In server_wsl/main.py, uncomment:
# main_imitation()
# And comment out:
# main()
```

## Code Navigation

### Adding New Graph Nodes
1. Define node function in `src/graph/nodes.py` that takes `AgentState` and returns `Dict`
2. Register in `src/graph/workflow.py` using `workflow.add_node()`
3. Connect with `workflow.add_edge()` or conditional edges

### Modifying State Schema
1. Update `AgentState` TypedDict in `src/graph/state.py`
2. Update `get_default_state()` to include new fields
3. Existing state.json files may need migration or deletion

### Audio File Paths
- Input audio: `server_wsl/temp_audio/received/recorder_audio.wav` (hardcoded in client_windows/microphone.py:26)
- Output audio: `server_wsl/temp_audio/pronounced/output.wav` (hardcoded in both client and server)
- These paths are relative to project root (DevEquality/)

### Server Configuration
Audio and network settings in `client_windows/config.ini` are shared by both client and server (server reads from `../client_windows/config.ini`).

## Current State

The system currently implements a basic transcribe ’ synthesize demo workflow. The following are planned but not yet implemented:
- LLM reasoning node between transcribe and synthesize
- File/directory/project manipulation tools
- Multi-turn conversation handling with messages history
- Project workspace management

## Branch Information
- Main branch: `main`
- Current development branch: `timur`
