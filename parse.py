# parse.py (Revised)
import os
import logging
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv
from typing import List, Optional # Keep List for chat_history type hint
import time
import socket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# Define a practical token limit (1M tokens is theoretical max, let's use ~700k chars as a safety buffer)
# Gemini 1.5 Flash token calculation is roughly 1 token per 4 chars
MAX_CONTENT_LENGTH = 700 * 1000

class ContentAnalyzer:
    """Analyzes full web content using Gemini 1.5 Flash"""

    def __init__(self, max_retries: int = 3, retry_delay: int = 5):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.model = self._initialize_model()

    def _initialize_model(self):
        """Secure model initialization with DNS check"""
        try:
            socket.getaddrinfo('generativelanguage.googleapis.com', 443)
            logger.info("DNS resolution for generativelanguage.googleapis.com successful.")
        except socket.gaierror as e:
            logger.error("DNS resolution failed. Check network configuration or firewall.")
            raise RuntimeError("DNS resolution failed. Check network config") from e

        if not self.api_key:
            logger.error("GOOGLE_API_KEY not found in environment variables or .env file.")
            raise ValueError("GOOGLE_API_KEY missing in .env")
        logger.info("GOOGLE_API_KEY found.")

        # Configure GenAI client
        # Removed redundant options, relying on defaults unless specific overrides needed
        genai.configure(api_key=self.api_key)

        try:
            model = genai.GenerativeModel('gemini-1.5-flash-latest') # Use latest version explicitly
            logger.info("Successfully initialized GenerativeModel('gemini-1.5-flash-latest').")
            # Optional: Make a small test call during init if needed, but can add latency/cost
            # model.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
            return model
        except Exception as e:
            logger.error(f"Model initialization failed: {str(e)}")
            raise RuntimeError(f"Model init failed: {str(e)}")

    def analyze_content(
        self,
        full_content: str, # Changed from dom_chunks: List[str]
        query: str,
        chat_history: Optional[List[str]] = None
    ) -> str:
        """Analyzes the full website content against a query."""
        try:
            if not full_content:
                logger.warning("analyze_content called with empty full_content.")
                return "⚠️ Error: No website content loaded or content is empty."
            if not query:
                logger.warning("analyze_content called with empty query.")
                return "⚠️ Error: Query cannot be empty."

            # Process the full content in one go
            response_text = self._process_full_content(full_content, query, chat_history)

            if response_text:
                return response_text
            else:
                # This case might happen if retries failed or model returned empty despite prompt
                logger.warning("Analysis resulted in no content after retries.")
                return "⚠️ Analysis failed after multiple retries or returned no relevant content."

        except Exception as e:
            logger.exception(f"Critical error during content analysis: {str(e)}") # Use logger.exception for stack trace
            return f"⚠️ Critical Error during analysis: {str(e)}"

    def _process_full_content(self, content: str, query: str, history: Optional[List[str]]) -> Optional[str]:
        """Processes the entire content with retries."""
        truncated_content = content
        if len(content) > MAX_CONTENT_LENGTH:
            truncated_content = content[:MAX_CONTENT_LENGTH]
            logger.warning(f"Content truncated from {len(content)} to {MAX_CONTENT_LENGTH} characters.")

        prompt = self._build_prompt(truncated_content, query, history)

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Sending request to Gemini (Attempt {attempt + 1}/{self.max_retries}). Prompt length (approx chars): {len(prompt)}")
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3, # Slightly higher temp might yield more natural language
                        top_p=0.95,
                        # max_output_tokens=1024 # Increased max output tokens
                        candidate_count=1 # Ensure only one candidate is requested
                    ),
                    request_options={'timeout': 120} # Add timeout for API call (seconds)
                )
                logger.info(f"Received response from Gemini (Attempt {attempt + 1}).")

                # Enhanced check for valid response text
                if response and response.text:
                    return response.text.strip()
                elif response and hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason
                     logger.error(f"Content blocked by API. Reason: {block_reason}")
                     return f"⚠️ Error: Content generation blocked by safety settings or API policy. Reason: {block_reason}"
                else:
                    logger.warning(f"Gemini response was empty or invalid on attempt {attempt + 1}.")
                    # Continue to retry unless it's the last attempt

            except google_exceptions.ResourceExhausted as e:
                 logger.error(f"API Resource Exhausted (Quota Exceeded?): {e}. Check your Google Cloud project quotas.")
                 return f"⚠️ API Error: Resource limits exceeded. Please check your API quota. ({e})"
            except google_exceptions.DeadlineExceeded as e:
                 logger.warning(f"API call timed out (Attempt {attempt + 1}/{self.max_retries}): {e}")
                 # Fall through to retry logic below
            except google_exceptions.ServiceUnavailable as e:
                logger.warning(f"API Service Unavailable (Attempt {attempt + 1}/{self.max_retries}): {e}")
                # Fall through to retry logic below
            except google_exceptions.GoogleAPIError as e:
                 logger.error(f"A non-retryable Google API error occurred: {e}")
                 return f"⚠️ API Error: {e}"
            except Exception as e:
                # Catch other potential errors during API call
                logger.exception(f"Unexpected error during Gemini API call (Attempt {attempt + 1}): {e}")
                # Depending on the error, you might not want to retry. Let's retry for now.

            # Retry logic
            if attempt < self.max_retries - 1:
                sleep_time = self.retry_delay * (2 ** attempt)
                logger.info(f"Waiting {sleep_time} seconds before retrying...")
                time.sleep(sleep_time)
            else:
                logger.error(f"Gemini request failed after {self.max_retries} attempts.")
                return None # Indicate failure after all retries

        return None # Should not be reached if loop completes, but added for safety

    def _build_prompt(self, content: str, query: str, history: Optional[List[str]]) -> str:
        """Constructs a clear analysis prompt for the LLM."""
        context_str = ""
        if history:
            # Include roles for better context understanding by the model
            context_lines = [f"{'User' if i % 2 == 0 else 'Assistant'}: {msg}" for i, msg in enumerate(history[-4:])] # Last 4 turns (2 user, 2 assistant)
            context_str = "\nPrevious Conversation Context:\n" + "\n".join(context_lines)

        # Added more specific instructions
        return f"""**Role:** You are an AI assistant specialized in analyzing provided web page text content to answer user questions accurately.

**Task:** Analyze the following **Web Page Text Content** and answer the **User Query** based *solely* on the information present in the text.

**Web Page Text Content:**
--- START ---
{content}
--- END ---
{context_str}

**User Query:** {query}

**Instructions for Response:**
1.  **Base your answer strictly on the provided "Web Page Text Content".** Do not use external knowledge or make assumptions.
2.  **Address the specific "User Query" directly.**
3.  **If the information needed to answer the query is present, extract and synthesize it clearly.** Quote relevant snippets briefly if helpful using markdown blockquotes (`> snippet`).
4.  **If the information is *not* found in the text, explicitly state that.** For example: "The provided text does not contain information about X."
5.  **Use Markdown formatting** for readability (e.g., headings `##`, lists `* item`, bold `**text**`).
6.  **Be objective and factual.**
7.  **Provide a comprehensive answer covering all parts of the query if possible within the text.**
8.  **Do NOT return an empty response.** If you cannot answer, explain why based on instruction #4.
"""

    # Removed _format_output as it's no longer needed for chunked responses