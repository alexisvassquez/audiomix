# AudioMIX
# api/routes/shell.py
#
# WebSocket and REST endpoints for the AudioScript shell.
#
# Endpoints:
#    WS /shell - bidirectional shell stream (Electron AS Shell panel)
#    POST /command - single command, synchronous response
#
# AS shell panel is in active development in audiomix-electron repo.
# The Electron AS Shell panel connects to WS /shell on startup.
# Commands typed in the shell are sent to WSMessage(type=shell_input)
# Results are pushed back to WSMessage(type=shell_output)
# Session state updates are pushed as WSMessage(type=session_update)

import os
import secrets

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.bridge import bridge
from api.models import (
    ShellCommandRequest,
    ShellCommandResponse,
    WSMessage,
    WSMessageType,
    AudioScriptBranch,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/shell", tags=["shell"])

# REST Endpoint
@router.post("/command", response_model=ShellCommandResponse)
async def post_command(request: ShellCommandRequest) -> ShellCommandResponse:
    """
    Sends a single AudioScript command and gets a synchronous response.
    Use this for one-off commands from non-WebSocket contexts.
    For the interactive shell, use WS /shell instead.
    
    Request body (ex):
        { "command": "glow('cyan')", "branch": "live" }
    
    Response:
        { "success": true, "command": "glow('cyan')", "result": "...", "session": {...} }
    """
    logger.info(f"POST /command - {request.command}")
    return await bridge.send_command(request)

# WebSocket Endpoint
@router.websocket("/ws")
async def shell_websocket(websocket: WebSocket) -> None:
    """
    Bidirectional WebSocket endpoint for the AudioScript shell.
    Connected by the Electron AS Shell panel on startup.

    Auth: client must send a valid x-audiomix-token header during the
    WebSocket handshake.
    Unauthorized connections are rejected before accept()

    Message flow: 
        Client -> Server: WSMessage(type=ping)
        Server -> Client: WSMessage(type=pong)
    Standard WebSocket keepalive pattern.
    
    The server pushes session_update on every state change, not just
    in response to commands.
    Transport changes / BPM changes / HAL device status changes all flow
    to the client automatically.
    """
    # Token check before accept, reject unauthoized handshakes outright.
    # API_TOKEN is guaranteed non-empty here since main.py raised at
    # startup if missing.
    expected_token = os.environ.get("AUDIOMIX_API_TOKEN", "")
    provided_token = websocket.headers.get("x-audiomix-token", "")
    if not secrets.compare_digest(provided_token, expected_token):
        # custom close code for "unauthorized"
        await websocket.close(code=4401)
        return

    await websocket.accept()
    client_id = id(websocket)
    logger.info(f"WS /shell - client {client_id} connected")

    # Send initial session state immediately on connect
    # so Electron application has real data before the first command
    try:
        initial = WSMessage(
            type=WSMessageType.SESSION_UPDATE,
            payload=bridge.get_session_state().model_dump(),
        )
        await websocket.send_text(initial.model_dump_json())
    except Exception as e:
        logger.error(f"Failed to send initial state to {client_id}: {e}")
        return
    
    # Register this client's send callback with the bridge
    # so state changes are pushed automatically
    async def send_to_client(message_json: str) -> None:
        await websocket.send_text(message_json)

    bridge.register_ws_client(send_to_client)

    try:
        while True:
            # Wait for a message from Electron client
            raw = await websocket.receive_text()

            try:
                message = WSMessage.model_validate_json(raw)
            except Exception as e:
                logger.warning(f"Invalid message from {client_id}: {e}")
                error = WSMessage(
                    type=WSMessageType.ERROR,
                    payload={"message": f"Invalid message format: {e}"},
                )
                await websocket.send_text(error.model_dump_json())
                continue

            # Dispatch on message type
            if message.type == WSMessageType.PING:
                pong = WSMessage(type=WSMessageType.PONG)
                await websocket.send_text(pong.model_dump_json())
            
            elif message.type == WSMessageType.SHELL_INPUT:
                if not message.payload or "command" not in message.payload:
                    error = WSMessage(
                        type=WSMessageType.ERROR,
                        payload={"message": "shell_input requires payload.command"},
                    )
                    await websocket.send_text(error.model_dump_json())
                    continue

                # Build command request from payload
                request = ShellCommandRequest(
                    command=message.payload["command"],
                    branch=AudioScriptBranch(
                        message.payload.get("branch", "live")
                    ),
                )

                # Send to runtime via bridge
                result = await bridge.send_command(request)

                # Push result back to this client
                response = WSMessage(
                    type=WSMessageType.SHELL_OUTPUT,
                    payload=result.model_dump(),
                )
                await websocket.send_text(response.model_dump_json())
            
            else:
                logger.warning(
                    f"Unhandled message type from {client_id}: {message.type}"
                )
            
    except WebSocketDisconnect:
        logger.info(f"WS /shell - client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WS /shell - client {client_id} error: {e}")
    finally:
        # Always unregister the callback on disconnect
        # so dead clients don't accumulate in the bridge
        bridge.unregister_ws_client(send_to_client)
        logger.info(f"WS /shell - client {client_id} cleaned up")