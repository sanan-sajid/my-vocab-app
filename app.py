import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import json
from datetime import datetime, timedelta
import random

# --- CONFIGURATION ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except FileNotFoundError:
    st.error("❌ Secrets file not found. If running locally, make sure you have .streamlit/secrets.toml")
    st.stop()
except KeyError as e:
    st.error(f"❌ Missing Secret: {e}. Check your spelling.")
    st.stop()

# Initialize
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# --- ROBUST FUNCTIONS ---

def get_ai_meanings(word):
    """Fetches with better error handling"""
    # Using gemini-pro as it's often more stable for JSON tasks
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are a dictionary API. Define '{word}'.
    You must return VALID JSON only. No markdown, no backticks.
    Format:
    {{
        "meanings": ["Formal def", "Simple def", "Creative def"],
        "examples": "Two sentences."
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        
        # Clean up potential markdown from AI (e.g., ```json ... ```)
        text = text.replace("```json", "").replace("```", "").strip()
        
        return json.loads(text)
    except Exception as e:
        st.error(f"⚠️ AI Error: {e}")
        st.write("Raw AI response was:", text) # Show what failed
        return None

def save_word(word, data, note):
    """Saves with explicit error printing"""
    try:
        # Check connection first
        result = supabase.table('vocab').insert({
            "word": word,
            "meanings": data['meanings'],
            "examples": data['examples'],
            "custom_note": note,
            "mastery_score": 0,
            "next_review": datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error(f"❌ Database Error: {e}")
        st.info("Did you disable RLS in Supabase? (Authentication > Policies > Disable RLS)")
        return False

def update_mastery(word_id, current_score, remembered):
    if remembered:
        new_score = current_score + 1
        days = [0, 1, 3, 7, 14, 30][min(new_score, 5)]
    else:
        new_score = 0 
        days = 0 
    
    next_date = datetime.now() + timedelta(days=days)
    
    try:
        supabase.table('vocab').update({
            "mastery_score": new_score,
            "next_review": next_date.isoformat()
        }).eq("id", word_id).execute()
    except Exception as e:
        st.error(f"Update failed: {e}")

# --- APP UI ---
st.set_page_config(page_title="Vocab Builder", page_icon="🧠")
st.title("🧠 Smart Vocab Debugger")

# Check Database Connection Immediately
try:
    supabase.table('vocab').select("count", count='exact').execute()
    st.toast("Database Connected ✅", icon="🟢")
except Exception as e:
    st.error(f"Cannot connect to Database: {e}")

tab1, tab2 = st.tabs(["➕ Add Word", "📚 Review"])

with tab1:
    new_word = st.text_input("Enter word:")
    if st.button("Analyze"):
        with st.spinner("Calling AI..."):
            result = get_ai_meanings(new_word)
            if result:
                st.session_state['temp_data'] = result
                st.session_state['current_word'] = new_word
    
    if 'temp_data' in st.session_state:
        data = st.session_state['temp_data']
        st.write(data) # Debug view to see raw data
        
        note = st.text_input("Note:")
        if st.button("Save Word"):
            if save_word(st.session_state['current_word'], data, note):
                st.success("Saved!")
                del st.session_state['temp_data']
                st.rerun()

with tab2:
    try:
        # Fetch data
        response = supabase.table('vocab').select("*").execute()
        words = response.data
        if words:
            st.write(f"Found {len(words)} words.")
            for w in words:
                st.text(f"{w['word']} - {w['meanings'][1]}")
        else:
            st.info("Database is empty.")
    except Exception as e:
        st.error(f"Fetch Error: {e}")