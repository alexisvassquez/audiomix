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
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()

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

        # Don't consider the runtime ready until it is actually done
        # initializing (check below)
        await self._wait_for_runtime_ready(timeout=60.0)

    async def _wait_for_runtime_ready(self, timeout: float = 10.0) -> None:
        """
        Blocks until the runtime prints its startup banner, which
        audioscript_runtime.py only prints after load_modules() has fully
        completed.
        This guarantees all startup-time output (such as module registration,
        DSP bridge attach, etc etc etc) has already been consumed from the
        queue before start() returns - closing the race where an early
        comand could receive leftover startup noise instead of its own response.
        """
        try:
            while True:
                line = await asyncio.wait_for(self._output_queue.get(), timeout=timeout)
                logger.debug(f"[runtime startup] {line}")
                if "Welcome to AudioMIX" in line:
                    logger.info("Runtime signaled already")
                    return
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out waiting for runtime reader banner - proceeding "
                "anyway, but early commands may race with startup output."
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

    # LIVE mode (live coding)
    async def enter_live_mode(self) -> SessionStateModel:
        """
        Called when the user switches into LIVE mode from the Electron
        UI.
        Starts the AudioScript runtime subprocess only if it has never been
        started this session.
        Re-entering LIVE mode after a pause reuses the already-running
        process rather than respawning it, so there's no state loss
        and resuming is instant.
        """
        if not self._running:
            await self.start()

        self._session.audioscript_branch = AudioScriptBranch.LIVE.value
        self._session.last_event = "mode:live_resumed"
        await self._notify_clients()

        logger.info("Entered/resumed LIVE mode")
        return self._get_session_model()

    async def exit_live_mode(self) -> SessionStateModel:
        """
        Called when the user leaves LIVE mode back to STUDIO.
        Does NOT kill the runtime subprocess - it stays alive, idle, in
        the background so re-entering LIVE mode later is instant w/ no
        state loss.
        Only the session's active branch changes; commands simply
        aren't expected to be sent while paused.
        """
        self._session.audioscript_branch = AudioScriptBranch.IR.value
        self._session.last_event = "mode:live_paused"
        await self._notify_clients()

        logger.info("Exited LIVE mode (runtime left running, idle)")
        return self._get_session_model()

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
        
        # Drain any backlog in the output queue before sending
        # to remove any stale lines that may be mistaken for a command's
        # result
        drained = []
        while True:
            try:
                drained.append(self._output_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if drained:
            logger.debug(f"Drained {len(drained)} stale runtime line(s) before sending command: {drained}")

        logger.debug(f"Sending command [{request.branch}]: {command}")

        assert self._runtime_process is not None
        assert self._runtime_process.stdin is not None
        assert self._runtime_process.stdout is not None

        try:
            # Write command to runtime stdin
            self._runtime_process.stdin.write(
                (command + "\n").encode()
            )
            await self._runtime_process.stdin.drain()

            # Read response via the queue fed by _read_runtime_output(),
            # rather than reading stdout directly
            # Only one coroutine may await stdout at a time, the bkgrd reader
            # task already owns that responsibility.
            result = await asyncio.wait_for(
                self._output_queue.get(),
                timeout=5.0
            )

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
    
    # Transport
    async def handle_transport(
        self,
        request: TransportRequest,
    ) -> TransportResponse:
        """
        Handles a transport action from the Electron UI.
        Updates SessionState and notifies WebSocket clients.
        
        Args:
            request: TransportRequest w/ action and optional BPM
        
        Returns:
            TransportResponse w/ updated session state
        """
        action = request.action

        if action == TransportAction.PLAY:
            self._session.is_playing = True
            self._session.is_recording = False
            self._session.last_event = "transport:play"
            logger.info("Transport: PLAY")

        elif action == TransportAction.PAUSE:
            self._session.is_playing = False
            self._session.last_event = "transport:pause"
            logger.info("Transport: PAUSE")
        
        elif action == TransportAction.STOP:
            self._session.is_playing = False
            self._session.is_recording = False
            self._session.playback_position = 0.0
            self._session.playhead_bar = 0.0
            self._session.last_event = "transport:stop"
            logger.info("Transport: STOP")

        elif action == TransportAction.RECORD:
            self._session.is_recording = not self._session.is_recording
            self._session.last_event = "transport:record"
            logger.info(f"Transport: RECORD {'ON' if self._session.is_recording else 'OFF'}")
        
        # Update BPM if provided
        if request.bpm is not None:
            self._session.bpm = request.bpm
            logger.info(f"Transport: BPM set to {request.bpm}")
        
        await self._notify_clients()

        return TransportResponse(
            success=True,
            action=action,
            session=self._get_session_model(),
        )
    
    # Session State
    def get_session_state(self) -> SessionStateModel:
        """
        Return current session state as a Pydantic model.
        Called by GET /session route.
        """
        return self._get_session_model()
    
    def _get_session_model(self) -> SessionStateModel:
        """
        Convert internal SessionState dataclass to Pydantic model
        for serialization.
        Private - use get_session_state() externally.
        """
        return SessionStateModel(
            is_playing = self._session.is_playing,
            is_recording = self._session.is_recording,
            playback_position = self._session.playback_position,
            playhead_bar = self._session.playhead_bar,
            project_name = self._session.project_name,
            scene_name = self._session.scene_name,
            current_track = self._session.current_track,
            bpm = self._session.bpm,
            key = self._session.key,
            mood = self._session.mood,
            time_signature = self._session.time_signature,
            active_script = self._session.active_script,
            audioscript_branch = AudioScriptBranch(self._session.audioscript_branch),
            last_as_command = self._session.last_as_command,
            last_as_result = self._session.last_as_result,
            gain = self._session.gain,
            pan = self._session.pan,
            reverb_mix = self._session.reverb_mix,
            compressor_ratio = self._session.compressor_ratio,
            delay_ms = self._session.delay_ms,
            sample_rate = self._session.sample_rate,
            buffer_size = self._session.buffer_size,
            latency_ms = self._session.latency_ms,
            cpu_percent = self._session.cpu_percent,
            last_event = self._session.last_event,
            last_error = self._session.last_error,
        )
    
    # WebSocket Clients
    def register_ws_client(
        self,
        callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """
        Register a WebSocket client callback.
        Called when Electron client connects to WS /shell.
        The callback receives a JSON string to send to the client.
        """
        self._ws_callbacks.append(callback)
        logger.info(f"WS client registered - {len(self._ws_callbacks)} total")
    
    def unregister_ws_client(
        self,
        callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """
        Unregister a WebSocket client callback.
        Called when an Electron client disconnects from WS /shell
        """
        if callback in self._ws_callbacks:
            self._ws_callbacks.remove(callback)
        logger.info(f"WS client unregistered - {len(self._ws_callbacks)} remaining")

    async def _notify_clients(self) -> None:
        """
        Push current session state to all connected WebSocket clients.
        Called after every state-changing operation.
        """
        if not self._ws_callbacks:
            return
        
        # lazy import
        from api.models import WSMessage, WSMessageType
        import json

        message = WSMessage(
            type=WSMessageType.SESSION_UPDATE,
            payload=self._get_session_model().model_dump(),
        )
        message_json = message.model_dump_json()

        # Fire all callbacks concurrently
        results = await asyncio.gather(
            *[cb(message_json) for cb in self._ws_callbacks],
            return_exceptions=True
        )

        # Clean up any dead callbacks
        dead = [
            cb for cb, result in zip(self._ws_callbacks, results)
            if isinstance(result, Exception)
        ]
        for cb in dead:
            self.unregister_ws_client(cb)

    # Runtime Output Reader
    async def _read_runtime_output(self) -> None:
        """
        Background task that continuously reads stdout from the
        AudioScript (AS) runtime process and logs it.
        Runs until the bridge shuts down.
        """
        if not self._runtime_process:
            return
    
        logger.info("Runtime output reader started")

        assert self._runtime_process is not None
        assert self._runtime_process.stdout is not None
        
        while self._running:
            try:
                line = await self._runtime_process.stdout.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                if decoded:
                    logger.debug(f"[runtime] {decoded}")
                    await self._output_queue.put(decoded)
            except Exception as e:
                logger.error(f"Runtime output reader error: {e}")
                break
        
        logger.info("Runtime output reader stopped")

# Singleton
# One bridge instance shared across the entire FastAPI application
# Imported by routes, never instantiated directly in route handlers.
bridge = AudioMIXBridge(project_name="OOEPUI_NIGHT_01")