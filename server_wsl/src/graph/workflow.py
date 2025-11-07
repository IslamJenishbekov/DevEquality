from langgraph.graph import StateGraph, END
from .state import AgentState
from . import nodes


workflow = StateGraph(AgentState)
workflow.add_node("transcribe", nodes.transcribe_audio_node)
workflow.set_entry_point("transcribe")
workflow.add_node("synthesize", nodes.synthesize_audio_node)
workflow.add_edge("transcribe", "synthesize")
workflow.add_edge("synthesize", END)
app = workflow.compile()
