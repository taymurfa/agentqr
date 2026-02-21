from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import json

from src.database.connection import get_db
from src.database import models
from src.chat.manager import ChatManager
from src.chat.streaming import StreamingResponseHandler
from api.websocket import ws_manager

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Research Chat"


@router.post("/sessions")
async def create_session(body: ChatSessionCreate, db: AsyncSession = Depends(get_db)):
    chat_mgr = ChatManager(db)
    session = await chat_mgr.create_session(title=body.title)
    return {"session_id": str(session.id), "title": session.title}


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    chat_mgr = ChatManager(db)
    sessions = await chat_mgr.list_sessions()
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    chat_mgr = ChatManager(db)
    messages = await chat_mgr.get_messages(session_id)
    return {"messages": messages}


@router.post("/send")
async def send_message(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Non-streaming chat endpoint for simple requests."""
    try:
        chat_mgr = ChatManager(db)

        if not body.session_id:
            session = await chat_mgr.create_session()
            session_id = str(session.id)
        else:
            session_id = body.session_id

        await chat_mgr.add_message(session_id, role="user", content=body.message)

        handler = StreamingResponseHandler(db)
        response = await handler.generate_response(session_id, body.message)

        await chat_mgr.add_message(session_id, role="assistant", content=response["content"])

        return {
            "session_id": session_id,
            "response": response["content"],
            "agents_used": response.get("agents_used", []),
            "context_sources": response.get("context_sources", []),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming chat responses."""
    await ws_manager.connect(websocket, session_id)
    db_gen = get_db()
    db = await db_gen.__anext__()

    try:
        chat_mgr = ChatManager(db)
        handler = StreamingResponseHandler(db)

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            await chat_mgr.add_message(session_id, role="user", content=message["content"])

            await websocket.send_json({"type": "status", "agent": "orchestrator", "status": "thinking"})

            full_response = ""
            async for chunk in handler.stream_response(session_id, message["content"]):
                if chunk["type"] == "token":
                    full_response += chunk["content"]
                    await websocket.send_json(chunk)
                elif chunk["type"] == "agent_status":
                    await websocket.send_json(chunk)
                elif chunk["type"] == "context":
                    await websocket.send_json(chunk)

            await chat_mgr.add_message(session_id, role="assistant", content=full_response)
            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
    finally:
        await db_gen.aclose()
