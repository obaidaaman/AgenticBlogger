from core.agent import app
from fastapi import WebSocket, WebSocketDisconnect
from core.models.response_model import ResponseModel
from typing import Optional

from datetime import timedelta, datetime
import jwt
import os



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

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=30
        )
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode,
        os.getenv("JWT_SECRET_KEY"),
        algorithm=os.getenv("JWT_ALGORITHM")
    )
    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=30
        )
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode,
        os.getenv("JWT_SECRET_KEY"),
            algorithms=[os.getenv("JWT_ALGORITHM")]
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET_KEY"),
            algorithms=[os.getenv("JWT_ALGORITHM")]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """Verify token and return payload if valid."""
    payload = decode_token(token)
    if payload is None:
        return None

    if payload.get("type") != token_type:
        return None

    return payload

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
                
               
                await websocket.send_json({
                    "status": "completed",
                    "blog": final_state.values.get("final_blog") or final_state.values.get("final" \
                    ""),
                   
                    "notion_url" : final_state.values.get("notion_url", "")
                        })

      
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
            "status" : "start",
            "notion_url" :""
    }
    return graph