# audiomix
# AudioMIX
# api/bridge.py
#
# The AudioMIX bridge - connects the FastAPI layer to the
# audioscript_runtime.py and DSP chain.
#
# This modules owns the lifecycle of the AudioScript runtime
# process and provides a clean async interface for the
# FastAPI routes to use.
# FastAPI routes never import from performance_engine or
# audioscript directly - they always go through this bridge.
#
# Architecture:
#    FastAPI routes 
#        ↓
#    AudioMIXBridge (this file)
#        ↓
#    audioscript_runtime.py (subprocess)
#        ↓
#    dsp_bridge.py -> main.cpp (DSP chain)

import asyncio
import asyncio.subprocess
import logging
import sys
import os
from typing import Optional, Any, Callable, Awaitable
from performance_engine.session_state import SessionState, make_default_session
from api.models import (
    SessionStateModel,
    ShellCommandRequest,
    ShellCommandResponse,
    TransportRequest,
    TransportResponse,
    TransportAction,
    AudioScriptBranch,
)

logger = logging.getLogger(__name__)

class AudioMIXBridge:
    """
    Singleton bridge between the FastAPI layer and the
    AudioMIX runtime.
    
    Responsibilities:
    - spawn and manage the audioscript_runtime.py subprocess
    - route AudioScript commands to the runtime / return results
    - maintain / expose the current SessionState
    - notify registered WebSocket clients of state changes
    - handle graceful shutdown
    
    Usage:
        bridge = AudioMIXBridge()
        await bridge.start()
        
        example
        result = await bridge.send_command("glow('cyan')")
        state = bridge.get_session_state()
        
        await bridge.shutdown()
    """
    def __init__(self, project_name: str = "untitled"):
        self._session: SessionState = make_default_session(project_name)
        self._runtime_process: Optional[asyncio.subprocess.Process] = None
        self._running: bool = False
        self._output_task: Optional[asyncio.Task] = None

        # Registered WebSocket notification callbacks
        # Each connected Electron client registers a callback here
        # so state changes are pushed immediately w/o polling
        self._ws_callbacks: list[Callable[[str], Awaitable[None]]] = []

        logger.info(f"AudioMIXBridge initialized - project: {project_name}")

    # Lifecycle
    async def start(self) -> None:
        """
        Start the AudioScript (AS) runtime subprocess.
        Called once when the FastAPI server starts up.
        """
        if self._running:
            logger.warning("Bridge already running - ignoring start()")
            return
        
        logger.info("Starting AudioScript runtime subprocess...")

        # Path to audioscript_runtime.py relative to project root
        runtime_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "audioscript_runtime.py"
        )

        if not os.path.exists(runtime_path):
            raise FileNotFoundError(
                f"AudioScript runtime not found at: {runtime_path}\n"
                f"Ensure audioscript_runtime.py is in the project root."
            )
        
        self._runtime_process = await asyncio.create_subprocess_exec(
            sys.executable, runtime_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._running = True
        logger.info(f"AudioScript runtime started - PID {self._runtime_process.pid}")

        # Start reading stdout from the runtime in the bkgrd
        # Store task reference - prevents garbage collection
        # and satisfies Pylance's type check on self method refs
        self._output_task = asyncio.create_task(
            self._read_runtime_output()    # type: ignore
        )
    
    async def shutdown(self) -> None:
        """
        Gracefully shut down the AudioScript (AS) runtime
        subprocess.
        Called when the FastAPI server shuts down.
        """
        if not self._running:
            return
        
        logger.info("Shutting down AudioScript runtime...")
        self._running = False

        if self._runtime_process and self._runtime_process.returncode is None:
            self._runtime_process.terminate()
            try:
                await asyncio.wait_for(
                    self._runtime_process.wait(),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Runtime did not terminate cleanly - killing")
                self._runtime_process.kill()

        logger.info("AudioScript runtime stopped")

    # Command Routing
    async def send_command(
        self, 
        request: ShellCommandRequest
    ) -> ShellCommandResponse:
        """
        Send an AudioScript command to the runtime and return
        the result.
        Called by POST /command and WS /shell routes.
        
        Args:
            request: ShellCommandRequest containing the command string
            and branch (IR or LIVE)
        
        Returns:
            ShellCommandResponse with success/failure and result text
        """
        if not self._running or not self._runtime_process:
            return ShellCommandResponse(
                success=False,
                command=request.command,
                error="AudioScript runtime is not running. "
                      "Start the AudioMIX engine first."
            )
        
        command = request.command.strip()
        if not command:
            return ShellCommandResponse(
                success=False,
                command=command,
                error="Empty command"
            )
        
        logger.debug(f"Sending command [{request.branch}]: {command}")

        try:
            # Write command to runtime stdin
            self._runtime_process.stdin.write(
                (command + "\n").encode()
            )
            await self._runtime_process.stdin.drain()

            # Read response from runtime stdout
            # Runtime responds with one line per command
            line = await asyncio.wait_for(
                self._runtime_process.stdout.readline(),
                timeout=5.0
            )
            result = line.decode().strip()

            # Update session state with last command
            self._session.last_as_command = command
            self._session.last_as_result = result
            self._session.last_event = f"command:{command}"

            # Notify all connected WebSocket clients
            await self._notify_clients()

            return ShellCommandResponse(
                success=True,
                command=command,
                result=result,
                session=self._get_session_model(),
            )
        except asyncio.TimeoutError:
            logger.error(f"Command timed out: {command}")
            return ShellCommandResponse(
                success=False,
                command=command,
                error="Command timed out - runtime did not respond within 5s"
            )
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return ShellCommandResponse(
                success=False,
                command=command,
                error=str(e)
            )