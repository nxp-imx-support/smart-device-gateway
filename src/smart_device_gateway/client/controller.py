# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import logging
from typing import Optional, Any

from gi.repository import GLib

from .actions import ActionManager
from .actions.leds import LedsAction
from .actions.notification import NotificationAction
from .pipelines import CapturePipeline, PlaybackPipeline
from .config import UserActionsConfig, UserConfig
from .openai import OpenAISession
from .state_machine import ApplicationStates, StateMachine
from .watchdog import WatchDog
from .utils import GREEN, RESET, get_terminal_width


class Controller:
    def __init__(self, config: UserConfig):
        self.mainloop = GLib.MainLoop()
        self.logger = logging.getLogger("Controller")

        # Initialize State Machine
        self.state_machine = StateMachine()

        # Initialize Resources
        self.openai_ready = False
        self.openai = OpenAISession(self, config.openai)

        self.capture = CapturePipeline(
            self,
            config.pipeline.capture,
            config.mic,
            config.openai.sink,
            config.vit if config.app.trigger == "wake-word" else None,
            (config.vad, config.monitors.vad)
            if config.app.stop_on == "voice-activity"
            else None,
            config.debug,
        )

        self.playback = PlaybackPipeline(
            self,
            config.pipeline.playback,
            config.spkr,
            config.openai.src,
            debug_config=config.debug,
            beep_wav=config.on.events.listen.sound,
        )

        self.action_manager = ActionManager(config.actions.max_workers)
        self.__setup_plugins(config.actions)

        self.on = config.on.events

        # Register state actions
        self.__register_state_actions()

        self.wait_watcher = WatchDog(10, self.__on_wait_timeout)

    def __setup_plugins(self, actions_configs: UserActionsConfig):
        self.__notifier = NotificationAction(actions_configs.notification)
        self.action_manager.register_plugin(self.__notifier)

        self.__leds = LedsAction(actions_configs.led)
        self.action_manager.register_plugin(self.__leds)

    def __register_state_actions(self):
        """Register enter/exit actions for each state"""
        
        # IDLE state
        self.state_machine.manager.register_enter_action(
            ApplicationStates.IDLE, 
            self.__on_enter_idle
        )
        
        # LISTEN state
        self.state_machine.manager.register_enter_action(
            ApplicationStates.LISTEN, 
            self.__on_enter_listen
        )
        
        # SEARCH state
        self.state_machine.manager.register_exit_action(
            ApplicationStates.SEARCH,
            self.__on_exit_search
        )
        
        # WAIT state
        self.state_machine.manager.register_enter_action(
            ApplicationStates.WAIT,
            self.__on_enter_wait
        )

        self.state_machine.manager.register_exit_action(
            ApplicationStates.WAIT,
            self.__on_exit_wait
        )
        
        # SPEAK state
        self.state_machine.manager.register_enter_action(
            ApplicationStates.SPEAK,
            self.__on_enter_speak
        )
        self.state_machine.manager.register_exit_action(
            ApplicationStates.SPEAK,
            self.__on_exit_speak
        )

        # RECOVERY state
        self.state_machine.manager.register_enter_action(
            ApplicationStates.RECOVERY,
            self.__on_enter_recovery
        )
        
        # DOWN state
        self.state_machine.manager.register_enter_action(
            ApplicationStates.DOWN,
            self.__on_enter_down
        )

    # ===== State Enter/Exit Actions =====
    
    def __on_enter_idle(self, context=None):
        """Actions when entering IDLE state"""
        self.logger.debug("Entering IDLE state")
        # Playback cleanup happens in on_exit_speak
    
    def __on_enter_listen(self, context=None):
        """Actions when entering LISTEN state"""
        self.logger.debug("Entering LISTEN state")
        
        # Core actions
        self.capture.start_monitor()
        self.capture.open_valve()
        self.openai.start_listening()

        # Optional actions
        if self.on.listen.sound:
            self.playback.play_beep()

        if self.on.listen.notification:
            self.action_manager.queue_action(self.__notifier.name, 3, **(context or {}))

        if self.on.listen.led:
            self.action_manager.queue_action(self.__leds.name, 3, 255)

        self.logger.info("All actions ran successfully (IDLE → LISTEN)")
    
    def __on_exit_search(self, context=None):
        """Actions when exiting SEARCH state"""
        self.logger.debug("Exiting SEARCH state")
        
        self.capture.stop_monitor()
        self.capture.close_valve()
        
        if self.on.listen.led:
            self.action_manager.queue_action(self.__leds.name, 3, 0)
    
    def __on_enter_wait(self, context=None):
        """Actions when entering WAIT state"""
        self.logger.debug("Entering WAIT state")
        
        self.openai.commit_audio()

        if not self.playback.play_openai():
            self.on_fatal_error()
            return

        message = self.capture.get_voice_end_message()
        if self.on.listen.notification:
            self.action_manager.queue_action(
                self.__notifier.name, 3, message=message
            )

        self.wait_watcher.start()

    def __on_wait_timeout(self):
        self.logger.warning(f"WAIT timeout after {self.wait_watcher.timeout}s - server not respondig")
        self.state_machine.transition_to(ApplicationStates.IDLE)

    def __on_exit_wait(self, context=None):
        """Actions when exiting WAIT state"""
        self.wait_watcher.cancel()
    
    def __on_enter_speak(self, context=None):
        """Actions when entering SPEAK state"""
        self.logger.info("Server is replying")
    
    def __on_exit_speak(self, context=None):
        """Actions when exiting SPEAK state"""
        self.logger.info("Server finish replying")

    def __on_enter_recovery(self, context: Optional[Any] = None):
        """Attempt to recover from error"""
        error = context.get('error', 'unknown')
        self.logger.warning(f"Entering recovery mode: {error}")
        
        # Different recovery strategies based on error
        if error == 'wait_timeout':
            # Server stuck - just go back to IDLE
            self.logger.info("Server timeout - returning to IDLE")
            GLib.timeout_add(1000, lambda: self.state_machine.transition_to(ApplicationStates.IDLE))
        
        elif error == 'connection_lost':
            # Connection issue - try to reconnect
            self.logger.info("Connection lost - attempting reconnect")
            self.__attempt_reconnect()
        
        else:
            # Unknown error - shutdown
            self.logger.error(f"Unknown error: {error} - shutting down")
            self.state_machine.transition_to(ApplicationStates.DOWN)

    def __attempt_reconnect(self, retry_count=0, max_retries=3):
        """Attempt to reconnect to OpenAI"""
        if retry_count >= max_retries:
            self.logger.error("Max retries reached - shutting down")
            self.state_machine.transition_to(ApplicationStates.DOWN)
            return
        
        self.logger.info(f"Reconnect attempt {retry_count + 1}/{max_retries}")
        
        def on_success():
            """Called when reconnect succeeds"""
            self.logger.info("Reconnect successful - returning to IDLE")
            GLib.idle_add(lambda: self.state_machine.transition_to(ApplicationStates.IDLE))
        
        def on_failure(error):
            """Called when reconnect fails"""
            self.logger.warning(f"Reconnect attempt {retry_count + 1} failed: {error}")
            
            # Exponential backoff
            delay_ms = int((2 ** retry_count) * 1000)
            GLib.timeout_add(
                delay_ms,
                lambda: self.__attempt_reconnect(retry_count + 1, max_retries)
            )
        
        # Simple sync call - no asyncio in Controller!
        self.openai.reconnect(on_success=on_success, on_failure=on_failure)

    
    def __on_enter_down(self, context=None):
        """Actions when entering DOWN state"""
        self.logger.debug("Entering DOWN state")
        # Cleanup happens in cleanup() method

    # ==== Event Handlers (called by pipelines/OpenAi) ====

    def on_wakeword(self, *args, **kwargs):
        context = {
                'is_ww': kwargs.get('is_ww', True),
                'ww': kwargs.get('ww', ''),
                'ww_id': kwargs.get('ww_id', ''),
                'timestamp': kwargs.get('timestamp', 0)
                }
        self.state_machine.transition_to(ApplicationStates.LISTEN, context)

    def on_voice(self, *args, **kwargs):
        self.state_machine.transition_to(ApplicationStates.LISTEN)
        self.logger.debug(f"Voice detected with metric: {args[0]}")

    def on_silence(self, *args, **kwargs):
        """Handle silence detection event"""
        self.state_machine.transition_to(ApplicationStates.SEARCH)
        self.logger.debug("Silence detected. Searching for voice end")

    def on_voice_end(self, *args, **kwargs):
        """Handle voice end event (silence threshold reached)"""
        self.state_machine.transition_to(ApplicationStates.WAIT)

    def on_response_start(self):
        """Handle OpenAI response start event"""
        self.state_machine.transition_to(ApplicationStates.SPEAK)

    def on_response_delta(self, data: bytes):
        """Handle OpenAI audio chunk event"""
        # Auto-transition to SPEAK if not already there
        if self.state_machine.state != ApplicationStates.SPEAK:
            self.on_response_start()
        self.playback.push_from_openai(data)

    def on_response_end(self):
        """Handle OpenAI response end event"""
        self.playback.push_eos(self.on_openai_eos)

    def on_openai_eos(self):
        self.logger.info("No audio left from OpenAISession on Playback Pipeline")
        self.state_machine.transition_to(ApplicationStates.IDLE)

    def on_openai_ready(self):
        """Handle OpenAI connection ready event"""
        self.openai_ready = True
        width = get_terminal_width()
        print(f"{GREEN}{'=' * width}{RESET}")
        print(f"{GREEN}{'Edge Voice is Ready! ':-^{width}}{RESET}")
        print(f"{GREEN}{'=' * width}{RESET}")
        self.start()

    # ===== Lifecycle Methods =====

    def start(self):
        """Start the application"""
        self.capture.play()
        self.playback.play()

    def stop(self):
        """Stop the application"""
        self.capture.stop()

    def cleanup(self):
        """Cleanup all resources"""
        self.openai.close()
        self.capture.cleanup()
        self.playback.cleanup()
        self.action_manager.shutdown()

    def on_fatal_error(self):
        """Handle fatal error"""
        GLib.idle_add(self.shutdown)

    def shutdown(self):
        """Shutdown the application"""
        if self.state_machine.state == ApplicationStates.DOWN:
            return
        
        self.state_machine.transition_to(ApplicationStates.DOWN)
        self.cleanup()
        self.mainloop.quit()
