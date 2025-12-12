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

# --- HELPER FUNCTIONS ---

def get_ai_meanings(word):
    """Fetches AI-generated definitions"""
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    You are a dictionary API. Define '{word}'.
    You must return VALID JSON only. No markdown, no backticks.
    Format:
    {{
        "meanings": ["Formal definition", "Simple definition", "Creative definition"],
        "examples": "Two example sentences using this word."
    }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        st.error(f"⚠️ AI Error: {e}")
        return None

def save_word(word, data, note):
    """Saves word to database"""
    try:
        supabase.table('vocab').insert({
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
        return False

def update_mastery(word_id, current_score, remembered):
    """Updates spaced repetition score"""
    if remembered:
        new_score = min(current_score + 1, 5)
        days = [0, 1, 3, 7, 14, 30][new_score]
    else:
        new_score = 0 
        days = 0 
    
    next_date = datetime.now() + timedelta(days=days)
    
    try:
        supabase.table('vocab').update({
            "mastery_score": new_score,
            "next_review": next_date.isoformat()
        }).eq("id", word_id).execute()
        return True
    except Exception as e:
        st.error(f"Update failed: {e}")
        return False

def get_all_words():
    """Fetch all words from database"""
    try:
        response = supabase.table('vocab').select("*").execute()
        return response.data
    except Exception as e:
        st.error(f"Fetch Error: {e}")
        return []

def delete_word(word_id):
    """Delete a word from database"""
    try:
        supabase.table('vocab').delete().eq("id", word_id).execute()
        return True
    except Exception as e:
        st.error(f"Delete Error: {e}")
        return False

# --- UI STYLING ---
st.set_page_config(page_title="Vocab Master", page_icon="🎮", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(255,255,255,0.2);
        border-radius: 8px;
        color: white;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: white !important;
        color: #667eea !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #667eea;
    }
    .word-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    .game-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 30px;
        border-radius: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    }
    .mastery-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9rem;
    }
    .mastery-0 { background-color: #ff6b6b; color: white; }
    .mastery-1 { background-color: #ffa500; color: white; }
    .mastery-2 { background-color: #ffd93d; color: black; }
    .mastery-3 { background-color: #6bcf7f; color: white; }
    .mastery-4 { background-color: #4d96ff; color: white; }
    .mastery-5 { background-color: #9333ea; color: white; }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown("<h1 style='text-align: center; color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);'>🎮 Vocab Master</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: white; font-size: 1.2rem;'>Level up your vocabulary with AI-powered learning</p>", unsafe_allow_html=True)

# Database connection check
try:
    supabase.table('vocab').select("count", count='exact').execute()
except Exception as e:
    st.error(f"⚠️ Cannot connect to Database: {e}")
    st.stop()

# --- STATS DASHBOARD ---
words = get_all_words()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📚 Total Words", len(words))
with col2:
    mastered = len([w for w in words if w['mastery_score'] >= 4])
    st.metric("🏆 Mastered", mastered)
with col3:
    learning = len([w for w in words if 0 < w['mastery_score'] < 4])
    st.metric("📖 Learning", learning)
with col4:
    new = len([w for w in words if w['mastery_score'] == 0])
    st.metric("🆕 New", new)

st.markdown("---")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add Word", "🎮 Play Games", "📚 Review & Study", "📊 My Collection"])

# TAB 1: ADD WORD
with tab1:
    st.markdown("<div class='word-card'>", unsafe_allow_html=True)
    st.subheader("Add a New Word")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_word = st.text_input("Enter word:", placeholder="e.g., serendipity")
    with col2:
        analyze_btn = st.button("🔍 Analyze", use_container_width=True, type="primary")
    
    if analyze_btn and new_word:
        with st.spinner("🤖 AI is thinking..."):
            result = get_ai_meanings(new_word)
            if result:
                st.session_state['temp_data'] = result
                st.session_state['current_word'] = new_word
                st.success("✅ Analysis complete!")
    
    if 'temp_data' in st.session_state:
        data = st.session_state['temp_data']
        
        st.markdown("### 📖 Definitions")
        for i, meaning in enumerate(data['meanings'], 1):
            st.info(f"**{i}.** {meaning}")
        
        st.markdown("### 💬 Example Usage")
        st.success(data['examples'])
        
        note = st.text_area("Add your personal note (optional):", placeholder="Your own thoughts, memory tricks, etc.")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("💾 Save to Collection", use_container_width=True, type="primary"):
                if save_word(st.session_state['current_word'], data, note):
                    st.balloons()
                    st.success(f"🎉 '{st.session_state['current_word']}' added to your collection!")
                    del st.session_state['temp_data']
                    del st.session_state['current_word']
                    st.rerun()
        with col2:
            if st.button("🔄 Try Another Word", use_container_width=True):
                del st.session_state['temp_data']
                del st.session_state['current_word']
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

# TAB 2: GAMES
with tab2:
    if len(words) < 4:
        st.warning("⚠️ You need at least 4 words to play games. Add more words first!")
    else:
        game_mode = st.radio("Choose a game mode:", 
                            ["🎯 Definition Match", "🔤 Fill in the Blank", "⚡ Quick Fire Quiz"],
                            horizontal=True)
        
        st.markdown("---")
        
        # Initialize game state
        if 'game_active' not in st.session_state:
            st.session_state['game_active'] = False
            st.session_state['game_score'] = 0
            st.session_state['game_questions'] = 0
        
        # GAME 1: Definition Match
        if game_mode == "🎯 Definition Match":
            st.markdown("<div class='game-card'>", unsafe_allow_html=True)
            st.markdown("### 🎯 Definition Match")
            st.markdown("Match the word with its correct definition!")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if st.button("🎮 Start Game", use_container_width=True, type="primary"):
                st.session_state['game_active'] = True
                st.session_state['game_score'] = 0
                st.session_state['game_questions'] = 0
                st.session_state['current_question'] = random.choice(words)
                
                # Generate wrong options
                other_words = [w for w in words if w['id'] != st.session_state['current_question']['id']]
                wrong_options = random.sample(other_words, min(3, len(other_words)))
                
                options = [st.session_state['current_question']] + wrong_options
                random.shuffle(options)
                st.session_state['options'] = options
                st.rerun()
            
            if st.session_state['game_active']:
                question = st.session_state['current_question']
                options = st.session_state['options']
                
                st.markdown(f"### Question {st.session_state['game_questions'] + 1}")
                st.markdown(f"## 🎯 **{question['word'].upper()}**")
                st.markdown("Which definition is correct?")
                
                for i, opt in enumerate(options):
                    if st.button(opt['meanings'][0], key=f"opt_{i}", use_container_width=True):
                        st.session_state['game_questions'] += 1
                        if opt['id'] == question['id']:
                            st.session_state['game_score'] += 1
                            st.success("✅ Correct!")
                            update_mastery(question['id'], question['mastery_score'], True)
                        else:
                            st.error(f"❌ Wrong! The correct answer was: {question['meanings'][0]}")
                            update_mastery(question['id'], question['mastery_score'], False)
                        
                        st.info(f"Score: {st.session_state['game_score']}/{st.session_state['game_questions']}")
                        
                        if st.session_state['game_questions'] < 10:
                            if st.button("Next Question ➡️"):
                                # Load next question
                                st.session_state['current_question'] = random.choice(words)
                                other_words = [w for w in words if w['id'] != st.session_state['current_question']['id']]
                                wrong_options = random.sample(other_words, min(3, len(other_words)))
                                options = [st.session_state['current_question']] + wrong_options
                                random.shuffle(options)
                                st.session_state['options'] = options
                                st.rerun()
                        else:
                            st.balloons()
                            percentage = (st.session_state['game_score'] / st.session_state['game_questions']) * 100
                            st.success(f"🎉 Game Over! Your score: {st.session_state['game_score']}/{st.session_state['game_questions']} ({percentage:.0f}%)")
                            if st.button("Play Again"):
                                st.session_state['game_active'] = False
                                st.rerun()
        
        # GAME 2: Fill in the Blank
        elif game_mode == "🔤 Fill in the Blank":
            st.markdown("<div class='game-card'>", unsafe_allow_html=True)
            st.markdown("### 🔤 Fill in the Blank")
            st.markdown("Complete the sentence with the correct word!")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if st.button("🎮 Start Game", use_container_width=True, type="primary"):
                st.session_state['game_active'] = True
                st.session_state['game_score'] = 0
                st.session_state['game_questions'] = 0
                st.session_state['current_question'] = random.choice(words)
                st.rerun()
            
            if st.session_state['game_active']:
                question = st.session_state['current_question']
                
                st.markdown(f"### Question {st.session_state['game_questions'] + 1}")
                
                # Show example with blank
                example = question['examples']
                word_to_hide = question['word']
                hidden_example = example.replace(word_to_hide, "______")
                hidden_example = hidden_example.replace(word_to_hide.capitalize(), "______")
                hidden_example = hidden_example.replace(word_to_hide.upper(), "______")
                
                st.markdown(f"### 📝 {hidden_example}")
                
                user_answer = st.text_input("Your answer:", key=f"answer_{st.session_state['game_questions']}")
                
                if st.button("Submit Answer", type="primary"):
                    st.session_state['game_questions'] += 1
                    if user_answer.lower().strip() == word_to_hide.lower():
                        st.session_state['game_score'] += 1
                        st.success(f"✅ Correct! The word is '{word_to_hide}'")
                        update_mastery(question['id'], question['mastery_score'], True)
                    else:
                        st.error(f"❌ Wrong! The correct word is '{word_to_hide}'")
                        update_mastery(question['id'], question['mastery_score'], False)
                    
                    st.info(f"Score: {st.session_state['game_score']}/{st.session_state['game_questions']}")
                    
                    if st.session_state['game_questions'] < 10:
                        if st.button("Next Question ➡️"):
                            st.session_state['current_question'] = random.choice(words)
                            st.rerun()
                    else:
                        st.balloons()
                        percentage = (st.session_state['game_score'] / st.session_state['game_questions']) * 100
                        st.success(f"🎉 Game Over! Your score: {st.session_state['game_score']}/{st.session_state['game_questions']} ({percentage:.0f}%)")
                        if st.button("Play Again"):
                            st.session_state['game_active'] = False
                            st.rerun()
        
        # GAME 3: Quick Fire Quiz
        elif game_mode == "⚡ Quick Fire Quiz":
            st.markdown("<div class='game-card'>", unsafe_allow_html=True)
            st.markdown("### ⚡ Quick Fire Quiz")
            st.markdown("True or False? Test your knowledge fast!")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if st.button("🎮 Start Game", use_container_width=True, type="primary"):
                st.session_state['game_active'] = True
                st.session_state['game_score'] = 0
                st.session_state['game_questions'] = 0
                
                # Generate question
                question_word = random.choice(words)
                is_correct = random.choice([True, False])
                
                if is_correct:
                    shown_definition = question_word['meanings'][0]
                else:
                    other_word = random.choice([w for w in words if w['id'] != question_word['id']])
                    shown_definition = other_word['meanings'][0]
                
                st.session_state['current_question'] = question_word
                st.session_state['shown_definition'] = shown_definition
                st.session_state['is_correct'] = is_correct
                st.rerun()
            
            if st.session_state['game_active']:
                question = st.session_state['current_question']
                
                st.markdown(f"### Question {st.session_state['game_questions'] + 1}")
                st.markdown(f"## **{question['word'].upper()}**")
                st.markdown(f"### Definition: {st.session_state['shown_definition']}")
                st.markdown("#### Is this the correct definition?")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ TRUE", use_container_width=True, type="primary"):
                        st.session_state['game_questions'] += 1
                        if st.session_state['is_correct']:
                            st.session_state['game_score'] += 1
                            st.success("✅ Correct!")
                            update_mastery(question['id'], question['mastery_score'], True)
                        else:
                            st.error(f"❌ Wrong! Correct definition: {question['meanings'][0]}")
                            update_mastery(question['id'], question['mastery_score'], False)
                        
                        st.info(f"Score: {st.session_state['game_score']}/{st.session_state['game_questions']}")
                        
                        if st.session_state['game_questions'] < 15:
                            if st.button("Next Question ➡️"):
                                question_word = random.choice(words)
                                is_correct = random.choice([True, False])
                                
                                if is_correct:
                                    shown_definition = question_word['meanings'][0]
                                else:
                                    other_word = random.choice([w for w in words if w['id'] != question_word['id']])
                                    shown_definition = other_word['meanings'][0]
                                
                                st.session_state['current_question'] = question_word
                                st.session_state['shown_definition'] = shown_definition
                                st.session_state['is_correct'] = is_correct
                                st.rerun()
                        else:
                            st.balloons()
                            percentage = (st.session_state['game_score'] / st.session_state['game_questions']) * 100
                            st.success(f"🎉 Game Over! Your score: {st.session_state['game_score']}/{st.session_state['game_questions']} ({percentage:.0f}%)")
                            if st.button("Play Again"):
                                st.session_state['game_active'] = False
                                st.rerun()
                
                with col2:
                    if st.button("❌ FALSE", use_container_width=True):
                        st.session_state['game_questions'] += 1
                        if not st.session_state['is_correct']:
                            st.session_state['game_score'] += 1
                            st.success(f"✅ Correct! Real definition: {question['meanings'][0]}")
                            update_mastery(question['id'], question['mastery_score'], True)
                        else:
                            st.error("❌ Wrong! This was the correct definition")
                            update_mastery(question['id'], question['mastery_score'], False)
                        
                        st.info(f"Score: {st.session_state['game_score']}/{st.session_state['game_questions']}")
                        
                        if st.session_state['game_questions'] < 15:
                            if st.button("Next Question ➡️", key="next2"):
                                question_word = random.choice(words)
                                is_correct = random.choice([True, False])
                                
                                if is_correct:
                                    shown_definition = question_word['meanings'][0]
                                else:
                                    other_word = random.choice([w for w in words if w['id'] != question_word['id']])
                                    shown_definition = other_word['meanings'][0]
                                
                                st.session_state['current_question'] = question_word
                                st.session_state['shown_definition'] = shown_definition
                                st.session_state['is_correct'] = is_correct
                                st.rerun()
                        else:
                            st.balloons()
                            percentage = (st.session_state['game_score'] / st.session_state['game_questions']) * 100
                            st.success(f"🎉 Game Over! Your score: {st.session_state['game_score']}/{st.session_state['game_questions']} ({percentage:.0f}%)")
                            if st.button("Play Again", key="replay2"):
                                st.session_state['game_active'] = False
                                st.rerun()

# TAB 3: REVIEW & STUDY
with tab3:
    st.subheader("📚 Spaced Repetition Review")
    
    due_words = [w for w in words if datetime.fromisoformat(w['next_review']) <= datetime.now()]
    
    if not due_words:
        st.success("🎉 No words due for review! Come back later or practice in Games mode.")
    else:
        st.info(f"📝 {len(due_words)} words are due for review")
        
        if 'review_index' not in st.session_state:
            st.session_state['review_index'] = 0
        
        if st.session_state['review_index'] < len(due_words):
            word = due_words[st.session_state['review_index']]
            
            st.markdown("<div class='word-card'>", unsafe_allow_html=True)
            st.markdown(f"## 📖 {word['word']}")
            
            with st.expander("💡 Show Definition", expanded=False):
                for i, meaning in enumerate(word['meanings'], 1):
                    st.write(f"**{i}.** {meaning}")
                st.markdown(f"**Examples:** {word['examples']}")
                if word['custom_note']:
                    st.info(f"📝 Your note: {word['custom_note']}")
            
            st.markdown("### Did you remember this word?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, I knew it!", use_container_width=True, type="primary"):
                    update_mastery(word['id'], word['mastery_score'], True)
                    st.session_state['review_index'] += 1
                    st.success("Great job! 🎉")
                    st.rerun()
            with col2:
                if st.button("❌ No, I forgot", use_container_width=True):
                    update_mastery(word['id'], word['mastery_score'], False)
                    st.session_state['review_index'] += 1
                    st.info("That's okay! You'll see it again soon.")
                    st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)
            st.progress((st.session_state['review_index'] + 1) / len(due_words))
            st.caption(f"Progress: {st.session_state['review_index'] + 1}/{len(due_words)}")
        else:
            st.balloons()
            st.success("🎉 Review session complete!")
            if st.button("Start New Review"):
                st.session_state['review_index'] = 0
                st.rerun()

# TAB 4: MY COLLECTION
with tab4:
    st.subheader("📊 Your Vocabulary Collection")
    
    if not words:
        st.info("Your collection is empty. Add some words to get started!")
    else:
        # Filter options
        filter_option = st.selectbox("Filter by mastery level:", 
                                    ["All Words", "New (0)", "Learning (1-3)", "Mastered (4-5)"])
        
        filtered_words = words
        if filter_option == "New (0)":
            filtered_words = [w for w in words if w['mastery_score'] == 0]
        elif filter_option == "Learning (1-3)":
            filtered_words = [w for w in words if 1 <= w['mastery_score'] <= 3]
        elif filter_option == "Mastered (4-5)":
            filtered_words = [w for w in words if w['mastery_score'] >= 4]
        
        st.write(f"Showing {len(filtered_words)} words")
        
        for word in sorted(filtered_words, key=lambda x: x['word']):
            with st.expander(f"**{word['word']}** - {word['meanings'][1][:50]}..."):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("**Definitions:**")
                    for i, meaning in enumerate(word['meanings'], 1):
                        st.write(f"{i}. {meaning}")
                    
                    st.markdown(f"**Examples:** {word['examples']}")
                    
                    if word['custom_note']:
                        st.info(f"📝 Your note: {word['custom_note']}")
                
                with col2:
                    mastery = word['mastery_score']
                    st.markdown(f"<span class='mastery-badge mastery-{mastery}'>Level {mastery}</span>", 
                              unsafe_allow_html=True)
                    
                    next_review = datetime.fromisoformat(word['next_review'])
                    if next_review <= datetime.now():
                        st.warning("⏰ Due now")
                    else:
                        days_until = (next_review - datetime.now()).days
                        st.success(f"📅 Review in {days_until}d")
                    
                    if st.button("🗑️ Delete", key=f"del_{word['id']}"):
                        if delete_word(word['id']):
                            st.success("Deleted!")
                            st.rerun()

st.markdown("---")
st.markdown("<p style='text-align: center; color: white;'>Made with ❤️ | Keep learning and growing! 🌱</p>", unsafe_allow_html=True)