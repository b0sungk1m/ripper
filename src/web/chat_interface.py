"""
🌙 Moon Dev's Voice Assistant
Built with love by Moon Dev 🚀

A simple web interface to start the voice agent.
"""

import streamlit as st
import sys
from pathlib import Path
import asyncio
import base64

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from src.agents.phone_agent import VoiceRecorder, test_conversation

# Page config
st.set_page_config(
    page_title="🌙 Moon Dev Voice Assistant",
    page_icon="🌙",
    layout="wide"
)

# Custom CSS for the giant button and messages
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        height: 300px !important;
        font-size: 120px !important;
        font-weight: bold;
        margin: 50px 0;
        border-radius: 20px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
    }
    .talk-button {
        background-color: #00cc66 !important;
        color: white !important;
    }
    .end-button {
        background-color: #ff4444 !important;
        color: white !important;
    }
    .stButton > button:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.3);
    }
    .main-title {
        text-align: center;
        font-size: 48px !important;
        margin-bottom: 20px;
        color: #1f1f1f;
    }
    .sub-title {
        text-align: center;
        font-size: 24px !important;
        color: #666;
        margin-bottom: 50px;
    }
    .status-message {
        text-align: center;
        font-size: 36px !important;
        padding: 30px;
        border-radius: 15px;
        margin: 30px 0;
        background-color: rgba(0, 0, 0, 0.05);
        color: #333;
    }
    .stSuccess, .stInfo, .stWarning {
        font-size: 24px !important;
        padding: 20px !important;
        margin: 20px 0 !important;
    }
    iframe {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'recording' not in st.session_state:
    st.session_state.recording = False
    st.session_state.recorder = None
    st.session_state.permission_error = False
    st.session_state.permission_granted = False
    st.session_state.conversation_started = False
    st.session_state.permission_requested = False

# Main UI
st.markdown('<p class="main-title">🌙 Moon Dev\'s Voice Assistant</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Your Personal AI Assistant for Algo Trading</p>', unsafe_allow_html=True)

# Create an HTML file with permission request
permission_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Microphone Permission</title>
</head>
<body>
    <script>
    async function requestPermission() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => track.stop());
            document.getElementById('status').innerText = 'Permission granted!';
        } catch (err) {
            document.getElementById('status').innerText = 'Permission denied: ' + err;
        }
    }
    requestPermission();
    </script>
    <div id="status">Requesting permission...</div>
</body>
</html>
"""

# Encode the HTML to data URL
data_url = f"data:text/html;base64,{base64.b64encode(permission_html.encode()).decode()}"

# Center column for giant button
col1, col2, col3 = st.columns([1,2,1])
with col2:
    if not st.session_state.recording:
        if st.button("🎙️ TALK NOW", key="start_button", use_container_width=True):
            st.session_state.recording = True
            st.session_state.permission_requested = True
            # Show iframe to request permission
            st.markdown(f'<iframe src="{data_url}" width="1" height="1"></iframe>', unsafe_allow_html=True)
            st.info("🎤 Please allow microphone access when prompted...")
            st.rerun()
    else:
        # Only start recording after a short delay to allow permission prompt
        if st.session_state.permission_requested and not st.session_state.permission_granted:
            try:
                recorder = VoiceRecorder()
                recorder.start_recording()
                st.session_state.recorder = recorder
                st.session_state.permission_granted = True
                st.session_state.conversation_started = True
                st.rerun()
            except Exception as e:
                if "Microphone access denied" in str(e) or "Could not open stream" in str(e):
                    st.session_state.permission_error = True
                    st.error("🎤 Please allow microphone access in your browser!")
                    st.info("Check your browser's address bar for the microphone permission prompt.")
                else:
                    st.error(f"❌ Error: {str(e)}")
                st.session_state.recording = False
                st.rerun()
        
        if st.button("🛑 END NOW", key="stop_button", use_container_width=True):
            if st.session_state.recorder:
                st.session_state.recorder.stop_recording()
            st.session_state.recording = False
            st.session_state.permission_granted = False
            st.session_state.conversation_started = False
            st.session_state.permission_requested = False
            st.markdown('<div class="status-message">👋 Call ended. Thanks for chatting!</div>', unsafe_allow_html=True)
            st.rerun()

# Show permission error help if needed
if st.session_state.permission_error:
    st.warning("""
    ⚠️ Microphone access is needed for the voice assistant to work.
    
    To fix this:
    1. Look for the microphone icon in your browser's address bar
    2. Click it and select "Allow"
    3. Click the TALK NOW button again
    
    If you don't see the icon:
    1. Click the lock/info icon in the address bar
    2. Look for "Microphone" permissions
    3. Set it to "Allow"
    """)
    if st.button("I've allowed access, try again"):
        st.session_state.permission_error = False
        st.session_state.recording = False
        st.session_state.permission_requested = False
        st.rerun()

# Start conversation only after permission is granted
if st.session_state.permission_granted and not st.session_state.conversation_started:
    st.session_state.conversation_started = True
    st.markdown('<div class="status-message">🎉 Voice Assistant activated! Start speaking...</div>', unsafe_allow_html=True)
    try:
        asyncio.run(test_conversation())
    except Exception as e:
        st.error(f"❌ Error during conversation: {str(e)}")
        st.session_state.recording = False
        st.session_state.permission_granted = False
        st.session_state.conversation_started = False
        st.rerun()

# Add footer
st.markdown("---")
st.markdown('<p style="text-align: center;">Made with 💖 by Moon Dev 🌙</p>', unsafe_allow_html=True) 