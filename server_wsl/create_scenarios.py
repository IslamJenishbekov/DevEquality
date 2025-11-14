import os
import wave
from piper import PiperVoice

scenario_path = r"temp_audio/scenarios/scenario1"
while os.path.exists(scenario_path):
    num = scenario_path[-1]
    scenario_path = scenario_path[:-1] + str(int(num) + 1)
os.makedirs(scenario_path)

scenario_texts = [
    "In file main dot py add the line print open parenthesis quote h e l l o space w o r l d quote close parenthesis.",
    "Tell what is in file main dot py shortly"
]

voice = PiperVoice.load("model_for_scenarios/en_US-john-medium.onnx")

for i, text in enumerate(scenario_texts):
    filename = os.path.join(scenario_path, f"{i}.wav")

    with wave.open(filename, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)

