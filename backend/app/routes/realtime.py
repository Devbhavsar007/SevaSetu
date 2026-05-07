from __future__ import annotations

"""
WebSocket Real-Time Layer — Replaces polling with live event push.

Rooms:
  - "admin"     → admin dashboard connections
  - "volunteer" → volunteer app connections

Events emitted:
  - need.created / need.updated
  - assignment.created
  - volunteer.updated
  - sos.triggered
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Real-Time"])


class ConnectionManager:
    """Manages WebSocket connections organized by rooms."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {
            "admin": [],
            "volunteer": [],
        }

    async def connect(self, websocket: WebSocket, room: str):
        await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = []
        self.active_connections[room].append(websocket)
        logger.info(f"WS connected to room '{room}' (total: {len(self.active_connections[room])})")

    def disconnect(self, websocket: WebSocket, room: str):
        if room in self.active_connections:
            try:
                self.active_connections[room].remove(websocket)
            except ValueError:
                pass
        logger.info(f"WS disconnected from room '{room}' (total: {len(self.active_connections.get(room, []))})")

    async def broadcast_to_room(self, room: str, message: dict):
        """Send a message to all connections in a room."""
        connections = self.active_connections.get(room, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        # Clean up dead connections
        for ws in dead:
            self.disconnect(ws, room)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a single connection."""
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    def get_connection_count(self, room: str) -> int:
        return len(self.active_connections.get(room, []))


# Singleton manager
manager = ConnectionManager()


@router.websocket("/ws/{room}/{token}")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str,
    token: str,
):
    """
    WebSocket endpoint for real-time updates.
    
    Rooms: 'admin' or 'volunteer'
    Token: JWT or 'dev-token' / 'dev-vol-token' in DEBUG mode
    """
    # Validate room
    if room not in ("admin", "volunteer"):
        await websocket.close(code=4001, reason="Invalid room")
        return

    # Simple token validation — in DEBUG, accept dev tokens
    if settings.DEBUG and token.startswith("dev-"):
        pass  # Accept dev tokens
    elif not token or len(token) < 10:
        await websocket.close(code=4002, reason="Invalid token")
        return

    await manager.connect(websocket, room)

    try:
        # Send connection confirmation
        await manager.send_personal(websocket, {
            "type": "connection.established",
            "data": {"room": room, "message": "Connected to real-time updates"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong for keepalive
            if data == "ping":
                await manager.send_personal(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, room)
    except Exception as e:
        logger.error(f"WebSocket error in room '{room}': {e}")
        manager.disconnect(websocket, room)


async def emit_event(event_type: str, data: dict, room: str = "admin"):
    """
    Emit a real-time event to a room.
    
    Call this from other routes to push updates:
      await emit_event("need.created", {"id": "...", "title": "..."}, "admin")
    """
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_room(room, message)
    logger.info(f"WS event '{event_type}' → room '{room}' ({manager.get_connection_count(room)} clients)")
