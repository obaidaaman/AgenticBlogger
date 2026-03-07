from core.agent import app
from fastapi import WebSocket, WebSocketDisconnect
from core.models.response_model import ResponseModel
from core.agent import app
from langgraph.types import Command

def response_controller(topic:str, config : dict):

    output = app.invoke({
        "topic" : topic,
        "mode":"",
        "needs_research":False,
        "queries":[],
        "evidence":[],
        "plan": None,
        "sections": [],
        "final": "",
    }, config=config)
    response = ResponseModel(topic=topic, final= output.get("final", ""))
    return response



from langgraph.types import Command

async def handle_agent_websocket(websocket : WebSocket, thread_id: str):

    config = {"configurable": {"thread_id": thread_id}}

    try:
        data = await websocket.receive_json()

        topic = data.get("topic")
        action = data.get("action")
        if not action:
            graph_input = initial_state(topic)
        else:
            graph_input = Command(resume=action)
        while True:
                
            async for event in app.astream_events(
                graph_input,
                config=config,
                version="v1"
            ):

                event_type = event["event"]

             
                if event_type == "on_node_start":
                    await websocket.send_json({
                        "type": "node_start",
                        "node": event["name"]
                    })

                elif event_type == "on_node_end":
                    await websocket.send_json({
                        "type": "node_end",
                        "node": event["name"]
                    })

           
                elif event_type == "on_llm_stream":
                    await websocket.send_json({
                        "type": "token",
                        "content": event["data"]["chunk"]
                    })

                
                elif "__interrupt__" in event.get("data", {}):
                    await websocket.send_json({
                        "type": "interrupt",
                        "data": event["data"]["__interrupt__"]
                    })
                    action = await websocket.receive_json()
                    graph_input = Command(resume=action)
                    break

                # graph finished
                elif event_type == "on_chain_end":
                    result = event["data"]

                    if hasattr(result, "content"):
                        result = result.content

                    await websocket.send_json({
                        "type": "complete",
                        "data": result
                    })

                    return
    except WebSocketDisconnect:
        print("Client Disconnected")


def initial_state(topic: str):
    graph = {
        "topic" : topic,
          "mode": "",
    "needs_research": False,
    "queries": [],
    "evidence": [],
    "plan": "",
    # workers working.
    "sections": [], # (task_id, section_md)
    "merged_md": "",
    "md_with_placeholders": "",
    "image_specs": [],
    "final" :"",
    "status" : ""

    }
    return graph