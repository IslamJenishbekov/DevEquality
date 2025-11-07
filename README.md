- python 3.12
- чтобы запустить файл создайте в винде виртуальное окружение,
поставьте туда все пакеты из client_windows.requirements, а в wsl окружении
```
pip install nemo_toolkit[asr]
pip install nemo_toolkit[tts]
pip install langchain langgraph langchain-google-genai
```
- cd server_wsl, python main.py
- cd client_windows, python microphone.py