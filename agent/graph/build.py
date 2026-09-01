"""Graph wiring.

diagnose -> decide -> guard -> (execute | decide | close | escalate_notify)
escalate_notify -> human_review -[interrupt]-> (decide | close)
execute -> check_outcome -> (decide | close)
close -> END

human_review pauses on a LangGraph interrupt(); with a PostgresSaver
checkpointer the pause survives restarts and POST /resume continues it.
"""

from langgraph.graph import END, StateGraph

from . import nodes
from .state import RecoveryState


def build_graph(checkpointer=None):
    g = StateGraph(RecoveryState)

    g.add_node("diagnose", nodes.diagnose)
    g.add_node("decide", nodes.decide)
    g.add_node("guard", nodes.guard)
    g.add_node("execute", nodes.execute)
    g.add_node("check_outcome", nodes.check_outcome)
    g.add_node("escalate_notify", nodes.escalate_notify)
    g.add_node("human_review", nodes.human_review)
    g.add_node("close", nodes.close)

    g.set_entry_point("diagnose")
    g.add_edge("diagnose", "decide")
    g.add_edge("decide", "guard")
    g.add_conditional_edges("guard", nodes.route_from_guard,
                            {"execute": "execute", "decide": "decide", "close": "close",
                             "human_review": "escalate_notify"})
    g.add_edge("escalate_notify", "human_review")
    g.add_conditional_edges("human_review", nodes.route_from_human,
                            {"decide": "decide", "close": "close"})
    g.add_edge("execute", "check_outcome")
    g.add_conditional_edges("check_outcome", nodes.route_from_outcome,
                            {"decide": "decide", "close": "close"})
    g.add_edge("close", END)

    return g.compile(checkpointer=checkpointer)
