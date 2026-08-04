import json
import base64
from io import BytesIO
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams

from main_server_files.chat_history.chat_history_handler import save_chat_history
import asyncio

async def process_realtime_input(data, session, connection_monitor, audio_processor):
    """Process realtime input data from the client."""
    print(f"Processing realtime_input with {len(data.get('realtime_input', {}).get('media_chunks', []))} chunks.")
    
    media_chunks = data["realtime_input"]["media_chunks"]
    if not media_chunks:
        print("No media chunks in realtime_input. Skipping processing.")
        return
    
    # Log all MIME types being received for debugging
    print(f"MIME types in chunks: {[chunk.get('mime_type') for chunk in media_chunks]}")

    image_bytes = None
    all_text_content = []  # Re-initialize a list to accumulate all text content
    is_user_message = False
    has_image = False
    is_system_context = False

    for idx, chunk in enumerate(data["realtime_input"]["media_chunks"]):
        mime_type = chunk.get("mime_type")
        chunk_data = chunk.get("data")

        if mime_type == "audio/pcm":
            pass
        elif mime_type == "image/jpeg":
            try:
                image_bytes = base64.b64decode(chunk_data)
                has_image = True
            except Exception as e:
                print(f"Error processing image: {e}")
                image_bytes = None
                has_image = False
                await connection_monitor.safe_send(json.dumps({"text": "Error processing screen capture."}))
        elif mime_type == "text/plain":
            print("Found text/plain chunk in realtime_input")
            is_selftalk = data.get("is_selftalk", False)
            is_system_msg = data.get("is_system_message", False)
            is_sys_context = data.get("is_system_context", False)

            if is_sys_context:
                is_system_context = True
                text_part_content = chunk_data
                print("Detected system context - will handle as background context")
            elif is_system_msg:
                print(f"Ignoring system message from client: {chunk_data[:100]}...")
                continue
            else:
                text_part_content = chunk_data
                print(f"Text chunk content stored: {text_part_content[:100]}...")
                all_text_content.append(text_part_content) # Add to the list

                if not is_selftalk:
                    is_user_message = True
        elif mime_type == "application/pdf":
            print(f"Found application/pdf chunk in realtime_input. Size: {len(chunk_data)} bytes.")
            try:
                pdf_bytes = base64.b64decode(chunk_data)
                # Use BytesIO to treat bytes as a file
                pdf_file = BytesIO(pdf_bytes)
                text_output = BytesIO()
                # Extract text using pdfminer.six
                extract_text_to_fp(pdf_file, text_output, laparams=LAParams())
                extracted_text = text_output.getvalue().decode('utf-8')
                if extracted_text:
                    text_part_content = extracted_text
                    all_text_content.append(text_part_content) # Add to the list
                    print(f"Extracted PDF text: {extracted_text[:100]}...")
                    is_user_message = True # Treat extracted PDF text as a user message
                else:
                    print("No text extracted from PDF.")
                    await connection_monitor.safe_send(json.dumps({"text": "Could not extract text from PDF."}))
            except Exception as e:
                print(f"Error processing PDF: {e}")
                await connection_monitor.safe_send(json.dumps({"text": "Error processing PDF file."}))
        else:
            print(f"WARNING: Unknown MIME type in realtime_input chunk: {mime_type}")

    # Handle system context separately
    if is_system_context and all_text_content: # Check if there is system context and text
        text_part_content = " ".join(all_text_content) # Combine text for system context
        print("Processing system context - adding as background context to session")
        try:
            # Extract just the conversation history without the prefix
            if text_part_content.startswith("[SYSTEM CONTEXT - Chat History]:"):
                history_content = text_part_content.replace("[SYSTEM CONTEXT - Chat History]:", "").strip()
            else:
                history_content = text_part_content
            
            # Format as a system instruction that won't confuse the AI
            system_instruction = f"""System: The following is your conversation history with this user for context. This is NOT a new message from the user, but information to help you understand the conversation context:

{history_content}

Please acknowledge that you've received this context and can now continue the conversation with full awareness of what was discussed previously."""
            
            # Send as system instruction to Gemini with proper formatting
            if session is not None:
                try:
                    # Send using the new send_client_content method
                    from google.genai import types
                    await session.send_client_content(
                        turns=types.Content(
                            role='user',  # System instructions are sent as user messages in live API
                            parts=[types.Part(text=system_instruction)]
                        )
                    )
                    print("System context sent to Gemini as system instruction")
                except Exception as e:
                    print(f"Error sending system instruction: {e}")
                    raise
                
                # Inform the client that context was added
                await connection_monitor.safe_send(json.dumps({
                    "text": "Chat history context added successfully. AI now has access to previous conversation.",
                    "is_system_message": True
                }))
            else:
                print("ERROR: Cannot send system context, session is None.")
                await connection_monitor.safe_send(json.dumps({
                    "text": "Error: Could not add chat history context - no active session.",
                    "is_system_message": True,
                    "is_error": True
                }))
        except Exception as e:
            print(f"ERROR: Exception during system context processing: {e}")
            await connection_monitor.safe_send(json.dumps({
                "text": f"Error adding chat history context: {str(e)}",
                "is_system_message": True,
                "is_error": True
            }))
        return  # Exit early for system context

    # Construct individual parts (string for text)
    text_part_string = None

    if image_bytes:
        print("Image data was received alongside other chunks.")

    if all_text_content and not is_system_context:
        text_part_string = " ".join(all_text_content)  # Combine all text content

        print(f"Preparing text part string for sending: {text_part_string[:100]}...")
        if is_user_message:
            save_chat_history(text_part_string, is_user=True)
            if connection_monitor.is_websocket_open():
                await connection_monitor.safe_send(json.dumps({
                    "text": "Processing your message...",
                    "is_system_message": True,
                    "is_processing": True
                }))

    try:
        if text_part_string:
            if session is not None:
                print(f"Sending text part to Gemini session: {text_part_string[:100]}...")
                try:
                    # Send the text using the new send_client_content method
                    await session.send_client_content(
                        turns=[{"role": "user", "parts": [{"text": text_part_string}]}]
                    )
                    print("Text part sent to Gemini session successfully.")
                except Exception as e:
                    print(f"Error during send_client_content: {e}")
                    # Try alternative format if send_client_content fails
                    try:
                        # Import types if needed
                        from google.genai import types
                        await session.send_client_content(
                            turns=types.Content(
                                role='user',
                                parts=[types.Part(text=text_part_string)]
                            )
                        )
                        print("Text part sent using alternative format successfully.")
                    except Exception as alt_e:
                        print(f"Alternative send format also failed: {alt_e}")
                        raise
            else:
                print("ERROR: Cannot send text part, session is None.")
        elif has_image:
            print("Image received but no text to send. Informing user.")
            system_msg_sent = await connection_monitor.safe_send(json.dumps({
                "text": "Screen capture received, but real-time analysis in the stream isn't supported. Please describe it or ask a question.",
                "is_system_message": True
                }))
            print(f"System message sent status: {system_msg_sent}")
        else:
            print("No valid text part prepared to send for this realtime_input.")

        await asyncio.sleep(0.1)
    except Exception as e:
         print(f"ERROR: Exception during session.send(): {e}")
         import traceback
         traceback.print_exc()
         await connection_monitor.safe_send(json.dumps({
             "text": f"Error sending message to Gemini: {str(e)}",
             "is_system_message": True, "is_error": True })) 