"""Interpret one Gemini server frame without owning the receive loop."""


async def process_response_frame(
    response,
    response_handler,
    connection_id,
    response_logger,
):
    """Process one response frame while preserving the stream's completion policy."""
    try:
        # Completion is scoped to the current response frame.
        setattr(response_handler, '_completion_handled', False)

        server_content = getattr(response, 'server_content', None)
        if server_content is None:
            print(f"No server_content in response for connection {connection_id}")
            return

        try:
            server_attrs = [
                attr for attr in dir(server_content) if not attr.startswith('_')
            ]
            response_logger.debug(
                f"Server content attributes for {connection_id}: {server_attrs}"
            )
        except Exception as error:
            response_logger.warning(
                f"Could not log server content attributes: {error}"
            )

        # Collect speech transcription before completion so a fragment carried
        # by the final frame is not lost.
        output_transcription = getattr(
            server_content, 'output_transcription', None
        )
        carried_transcription = False
        if output_transcription is not None:
            fragment = getattr(output_transcription, 'text', None)
            if fragment:
                response_handler.audio_processor.spoken_text += fragment
                carried_transcription = True

        turn_complete = getattr(server_content, 'turn_complete', None)
        if turn_complete is not None and turn_complete:
            print(
                "Turn complete detected via server_content.turn_complete "
                f"for connection {connection_id}"
            )
            if not getattr(response_handler, '_completion_handled', False):
                setattr(response_handler, '_completion_handled', True)
                # Deferred so the receive loop can collect trailing transcript.
                response_handler.schedule_turn_completion()
                print(
                    f"Turn completed for connection {connection_id}, "
                    "session remaining active for next user input"
                )
            return

        model_turn = getattr(server_content, 'model_turn', None)

        # A transcription-only frame is not evidence that the turn is over.
        if carried_transcription and model_turn is None:
            return

        if model_turn is not None:
            parts = getattr(model_turn, 'parts', None)
            if parts:
                for part in parts:
                    await response_handler.process_response_part(part)
            else:
                print(
                    f"No parts found in model_turn for connection {connection_id}"
                )
        else:
            response_logger.info(
                "No model_turn in server_content for connection "
                f"{connection_id} - checking for other completion indicators"
            )
            try:
                audio_chunks = getattr(server_content, 'audio_chunks', None)
                if audio_chunks:
                    response_logger.info(
                        f"Found {len(audio_chunks)} audio chunks in "
                        "server_content without model_turn"
                    )
                    for chunk in audio_chunks:
                        if hasattr(chunk, 'data') and chunk.data:
                            await response_handler.process_audio_chunk(chunk.data)
                else:
                    inline_data = getattr(server_content, 'inline_data', None)
                    if inline_data:
                        response_logger.info(
                            "Found inline_data in server_content without "
                            "model_turn"
                        )
                        await response_handler.process_audio_chunk(inline_data)

                server_turn_complete = getattr(
                    server_content, 'turn_complete', None
                )
                if server_turn_complete:
                    response_logger.info(
                        "Turn complete detected in server_content for "
                        f"connection {connection_id}"
                    )
                    if not getattr(
                        response_handler, '_completion_handled', False
                    ):
                        setattr(response_handler, '_completion_handled', True)
                        await response_handler.handle_turn_complete()
                    return
            except Exception as error:
                response_logger.warning(
                    "Error processing server_content without model_turn: "
                    f"{error}"
                )

        if not model_turn:
            server_turn_complete = getattr(server_content, 'turn_complete', None)
            server_final = getattr(server_content, 'final', None)
            server_finished = getattr(server_content, 'finished', None)
            server_complete = getattr(server_content, 'complete', None)

            if (
                server_turn_complete
                or server_final
                or server_finished
                or server_complete
            ):
                print(
                    "Turn complete detected in server_content "
                    f"(turn_complete={server_turn_complete}, "
                    f"final={server_final}, finished={server_finished}, "
                    f"complete={server_complete})"
                )
                if not getattr(response_handler, '_completion_handled', False):
                    setattr(response_handler, '_completion_handled', True)
                    await response_handler.handle_turn_complete()
                return

            # Unknown mid-generation frames are not completion evidence. The
            # owned idle watchdog will finish a genuinely abandoned turn.
            audio_size = len(
                getattr(response_handler.audio_processor, 'audio_data', [])
            )
            if audio_size < response_handler.MIN_MEANINGFUL_AUDIO_BYTES:
                response_logger.debug(
                    "No audio data and no completion indicators for "
                    f"connection {connection_id}"
                )
        else:
            final_attr = getattr(model_turn, 'final', None)
            if final_attr is not None and final_attr:
                if not getattr(response_handler, '_completion_handled', False):
                    setattr(response_handler, '_completion_handled', True)
                    await response_handler.handle_turn_complete()
                    print(
                        "Turn complete (legacy final=True), session remaining "
                        "active"
                    )
                return

            is_finished = getattr(model_turn, 'finished', None)
            is_complete = getattr(model_turn, 'complete', None)
            if is_finished or is_complete:
                if not getattr(response_handler, '_completion_handled', False):
                    setattr(response_handler, '_completion_handled', True)
                    await response_handler.handle_turn_complete()
                    print(
                        f"Turn complete (finished={is_finished}, "
                        f"complete={is_complete}), session remaining active"
                    )
                return

        try:
            completed = await response_handler.check_audio_completion()
            if completed:
                print(
                    "Audio completion detected via timing for connection "
                    f"{connection_id}"
                )
                return
        except Exception as error:
            response_logger.warning(f"Error in audio completion check: {error}")

        pending_audio = len(
            getattr(response_handler.audio_processor, 'audio_data', b'') or b''
        )
        response_logger.debug(
            f"Frame carried {pending_audio} buffered audio bytes for "
            f"connection {connection_id}; awaiting an explicit completion "
            "indicator or the idle watchdog"
        )
        return
    except AttributeError as error:
        print(
            f"AttributeError in response parsing for connection "
            f"{connection_id}: {error}"
        )
        response_logger.warning(
            f"Response structure error for {connection_id}: {error}"
        )
        try:
            await response_handler.check_audio_completion()
        except Exception as fallback_error:
            print(f"Fallback audio completion failed: {fallback_error}")
    except Exception as error:
        print(
            f"Unexpected error in response parsing for connection "
            f"{connection_id}: {error}"
        )
        response_logger.error(
            f"Response parsing error for {connection_id}: {error}"
        )
        try:
            await response_handler.check_audio_completion()
        except Exception as fallback_error:
            print(f"Fallback audio completion failed: {fallback_error}")
