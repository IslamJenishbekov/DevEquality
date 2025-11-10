from langgraph.graph import StateGraph, END
from .state import AgentState
from . import nodes


workflow = StateGraph(AgentState)
# ADDING NODES
workflow.add_node("transcribe", nodes.transcribe_audio_node)
workflow.add_node("get_operation", nodes.get_operation_and_object_name_node)
workflow.add_node("create_project", nodes.create_project_node)
workflow.add_node("clone_project", nodes.git_clone_project_node)
workflow.add_node("create_directory", nodes.create_directory_node)
workflow.add_node("create_file", nodes.create_file_node)
workflow.add_node("edit_file", nodes.edit_file_node)
workflow.add_node("run_file", nodes.run_file_node)
workflow.add_node("read_file", nodes.get_file_content_node)
workflow.add_node("summarize_file", nodes.summarize_file_content_node)
workflow.add_node("unknown_operation", nodes.unknown_operation_node)
workflow.add_node("synthesize", nodes.synthesize_audio_node)

# SET ENTRY POINT
workflow.set_entry_point("transcribe")

# ADDING EDGES
workflow.add_edge("transcribe", "get_operation")
workflow.add_conditional_edges(
    "get_operation",
    nodes.choose_operation_node,
    {
        "create project": "create_project",
        "clone project": "clone_project",
        "create directory": "create_directory",
        "create file": "create_file",
        "edit file": "edit_file",
        "run file": "run_file",
        "read file": "read_file",
        "summarize file": "summarize_file",
        "unknown": "unknown_operation"
    }
)
workflow.add_edge("create_project", "synthesize")
workflow.add_edge("clone_project", "synthesize")
workflow.add_edge("create_directory", "synthesize")
workflow.add_edge("create_file", "synthesize")
workflow.add_edge("edit_file", "synthesize")
workflow.add_edge("run_file", "synthesize")
workflow.add_edge("read_file", "synthesize")
workflow.add_edge("summarize_file", "synthesize")
workflow.add_edge("unknown_operation", "synthesize")
workflow.add_edge("synthesize", END)

# Compile
app = workflow.compile()

with open("workflow.png", 'wb') as f:
    f.write(app.get_graph().draw_mermaid_png())
