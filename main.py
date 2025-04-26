# main.py (Revised)
import streamlit as st
from scrape import scrape_website, extract_body_content, clean_body_content # Removed split_dom_content import
from parse import ContentAnalyzer
import logging # Added for logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Session state initialization ---
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'dom_content' not in st.session_state:
    st.session_state.dom_content = ""
if 'website_url' not in st.session_state:
    st.session_state.website_url = "" # Store URL for context

# --- Initialize Analyzer ---
# Use a try-except block for robust initialization
try:
    analyzer = ContentAnalyzer()
    ANALYZER_INITIALIZED = True
    logger.info("ContentAnalyzer initialized successfully.")
except Exception as e:
    ANALYZER_INITIALIZED = False
    logger.error(f"Failed to initialize ContentAnalyzer: {e}", exc_info=True)
    # Display error prominently in the UI if initialization fails
    st.error(f"Fatal Error: Could not initialize the AI Analyzer. Please check logs and API key setup. Error: {e}", icon="🚨")


# --- UI Configuration ---
st.set_page_config(
    page_title="AI Web Analyst",
    page_icon="🤖",
    layout="wide" # Changed to wide layout for better content display
)

st.title("🤖 AI Web Content Analyzer")
st.caption("Enter a URL, load the content, and ask questions about the page.")

# --- Sidebar - Website Setup ---
with st.sidebar:
    st.header("⚙️ Website Configuration")
    # Use text_input with session state for persistence
    st.session_state.website_url = st.text_input(
        "Enter Website URL",
        value=st.session_state.website_url,
        key="website_url_input",
        placeholder="https://example.com"
    )

    if st.button("Load Website Content", key="load_website_btn", type="primary", disabled=not ANALYZER_INITIALIZED):
        if st.session_state.website_url and st.session_state.website_url.startswith(('http://', 'https://')):
            st.session_state.dom_content = "" # Clear previous content
            st.session_state.chat_history = [] # Clear history on new load
            with st.spinner(f"Scraping and cleaning {st.session_state.website_url}..."):
                try:
                    logger.info(f"Starting scrape for: {st.session_state.website_url}")
                    html = scrape_website(st.session_state.website_url)
                    logger.info(f"Scraping done. Extracting body content...")
                    body_content = extract_body_content(html)
                    logger.info(f"Extracting done. Cleaning content...")
                    st.session_state.dom_content = clean_body_content(body_content)
                    logger.info(f"Cleaning done. Content length: {len(st.session_state.dom_content)}")
                    if st.session_state.dom_content:
                        st.success("✅ Website content loaded and cleaned!")
                    else:
                        st.warning("⚠️ Content loaded, but it appears empty after cleaning. The page might be dynamic or lack text.")

                except RuntimeError as e: # Catch runtime errors from scrape/init
                    st.error(f"Scraping Error: {e}")
                    logger.error(f"Scraping failed for {st.session_state.website_url}: {e}", exc_info=True)
                except Exception as e:
                    st.error(f"An unexpected error occurred: {str(e)}")
                    logger.error(f"Unexpected error during loading for {st.session_state.website_url}: {e}", exc_info=True)
        elif not st.session_state.website_url:
            st.warning("Please enter a URL.")
        else:
            st.warning("Please enter a valid URL starting with http:// or https://")

    # Display status
    st.divider()
    if not ANALYZER_INITIALIZED:
        st.error("Analyzer Initialization Failed. Check Logs.", icon="🚨")
    elif st.session_state.dom_content:
        st.success(f"Content loaded from:\n{st.session_state.website_url}")
        st.info(f"Cleaned text length: {len(st.session_state.dom_content)} chars")
    else:
        st.info("No website content loaded yet.")


# --- Main Chat Interface ---
st.header("💬 Chat with the Website Content")

# Display chat history
if 'chat_history' in st.session_state:
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Chat input - Ensure analyzer is ready and content is loaded
chat_input_disabled = not ANALYZER_INITIALIZED or not st.session_state.dom_content
chat_placeholder = "Ask about the loaded website..." if not chat_input_disabled else "Load a website first..."

if prompt := st.chat_input(chat_placeholder, key="main_chat_input", disabled=chat_input_disabled):
    # Add user message to state and display it
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty() # Use placeholder for streaming-like effect
        message_placeholder.markdown("🧠 Analyzing...")
        try:
            with st.spinner("AI is thinking..."):
                # Prepare history for the model (only content strings)
                history_for_model = [msg["content"] for msg in st.session_state.chat_history if msg["role"] != "user"] # Send previous Assistant messages too
                history_for_model.extend([msg["content"] for msg in st.session_state.chat_history if msg["role"] == "user"][:-1]) # Add previous user messages, excluding current one

                response = analyzer.analyze_content(
                    st.session_state.dom_content,
                    prompt,
                    history_for_model # Pass previous messages correctly
                )

                # Display the final response
                if response.startswith("⚠️"):
                    st.error(response) # Display errors using st.error
                    # Do not add error messages to history as assistant response
                else:
                    message_placeholder.markdown(response)
                    # Add valid assistant response to chat history
                    st.session_state.chat_history.append({"role": "assistant", "content": response})

        except Exception as e:
            logger.error(f"Error during analysis or display: {e}", exc_info=True)
            st.error(f"An unexpected error occurred during analysis: {str(e)}")
            # Optionally add an error marker to history if needed, but usually avoided
            # st.session_state.chat_history.append({"role": "assistant", "content": f"Error: {str(e)}"})


# --- Content Preview Section (Optional) ---
if st.session_state.dom_content:
    st.divider()
    with st.expander("👁️ View Cleaned Text Content (First 5000 chars)"):
        st.text(st.session_state.dom_content[:5000] + ("..." if len(st.session_state.dom_content) > 5000 else ""))