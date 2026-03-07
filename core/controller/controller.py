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


async def handle_agent_websocket(websocket : WebSocket, thread_id: str):

    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        while True:
          
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "start":
                state = initial_state(topic=data.get("topic"))
                await app.ainvoke(state, config=config)
                
                
                current_state = await app.aget_state(config)
                plan_pydantic = current_state.values.get("plan")
                
            
                await websocket.send_json({
                    "status": "plan_ready",
                    "plan": plan_pydantic.model_dump() if plan_pydantic else None
                })
                # Approve
            elif action == "approve":
              
                await app.aupdate_state(config, {"status": "approve"})
          
                await app.ainvoke(None, config=config)
                
                # Fanout then worker trigger             
                final_state = await app.aget_state(config)
                
                # 4. Send final blog to frontend
                await websocket.send_json({
                    "status": "completed",
                    "blog": final_state.values.get("final_blog")
                })

       # Decline
            elif action == "decline":
                
                await app.aupdate_state(config, {"status": "decline"})
                
                # Orchestrator Node back to there.
                await app.ainvoke(None, config=config)
                
               
                new_state = await app.aget_state(config)
                new_plan = new_state.values.get("plan")
                
                # 4. Send the NEW plan to the frontend
                await websocket.send_json({
                    "status": "plan_ready",
                    "plan": new_plan.model_dump() if new_plan else None
                })
                
    except WebSocketDisconnect:
        print("Client disconnected.")


def initial_state(topic: str):
    graph = {
        
            "topic": topic,
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "sections": [],
            "merged_md": "",
            "md_with_placeholders": "",
            "image_specs": [],
            "final": "",
            "status" : "start"
    }
    return graph