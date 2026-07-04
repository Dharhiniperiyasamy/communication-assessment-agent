import streamlit as st
import sqlite3
import pandas as pd
import datetime
import language_tool_python
import textstat
import speech_recognition as sr
import re
import io
import wave

# --- 1. DATABASE SETUP ---
DB_FILE = "assessments.db"

def init_db():
    """Initializes the SQLite database and creates the submissions table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            type TEXT,
            context TEXT,
            grammar_score REAL,
            clarity_score REAL,
            vocab_score REAL,
            tone_score REAL,
            overall_score REAL,
            filler_count INTEGER,
            wpm REAL,
            raw_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_submission(type_name, context, g_score, c_score, v_score, t_score, o_score, filler_count, wpm, text):
    """Saves a new assessment result into the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO submissions (timestamp, type, context, grammar_score, clarity_score, 
                                 vocab_score, tone_score, overall_score, filler_count, wpm, raw_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, type_name, context, g_score, c_score, v_score, t_score, o_score, filler_count, wpm, text))
    conn.commit()
    conn.close()

def get_all_submissions():
    """Retrieves all past submissions into a pandas DataFrame."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM submissions", conn)
    conn.close()
    return df

# --- 2. SCORING FUNCTIONS ---
@st.cache_resource
def get_language_tool():
    """Caches the LanguageTool instance to speed up consecutive checks."""
    return language_tool_python.LanguageTool('en-US')

def analyze_grammar(text):
    """Analyzes text for grammar errors and returns a score and tagged errors."""
    if not text.strip():
        return 100, []
    
    tool = get_language_tool()
    matches = tool.check(text)
    
    errors = []
    # Deduct 5 points per error, min score 0
    score = max(0, 100 - (len(matches) * 5))
    
    for match in matches:
        # Map LanguageTool rule types to our severity tags
        category = match.category.lower()
        if 'spelling' in category or 'grammar' in category or 'agreement' in category:
            severity = "Critical"
        elif 'punctuation' in category or 'typography' in category:
            severity = "Minor"
        else:
            severity = "Style Suggestion"
            
        errors.append({
            "msg": match.message,
            "severity": severity,
            "context": match.context,
            "replacement": ", ".join(match.replacements[:3])
        })
        
    return score, errors

def analyze_clarity(text):
    """Calculates clarity score based on Flesch Reading Ease."""
    if not text.strip():
        return 100
    
    # Flesch Reading Ease (0-100, higher is easier to read)
    fre = textstat.flesch_reading_ease(text)
    # Clamp between 0 and 100
    score = max(0, min(100, fre))
    return score

def analyze_vocab(text):
    """Calculates vocabulary score based on average sentence and word length."""
    if not text.strip():
        return 100
    
    avg_sentence_len = textstat.avg_sentence_length(text)
    # Ideal sentence length ~15-20 words. Penalize very short or very long sentences.
    if 10 <= avg_sentence_len <= 20:
        score = 100
    else:
        score = max(0, 100 - abs(15 - avg_sentence_len) * 3)
    return score

def analyze_tone(text, context):
    """Rule-based tone scoring adapted to context."""
    if not text.strip():
        return 100
    
    text_lower = text.lower()
    score = 100
    
    casual_words = ['gonna', 'wanna', 'dunno', 'kinda', 'sorta', 'yeah', 'stuff', 'things']
    casual_count = sum(text_lower.count(w) for w in casual_words)
    
    passive_voice_regex = re.compile(r'\b(am|is|are|was|were|be|been|being)\s+\w+ed\b', re.IGNORECASE)
    passive_count = len(passive_voice_regex.findall(text))
    
    if context in ["Job Interview", "Email", "Presentation"]:
        # Penalize casual words heavily in formal contexts
        score -= casual_count * 5
    elif context == "Casual Chat":
        # Do not penalize casual words, but penalize excessive passive voice
        score -= passive_count * 3
        
    score = max(0, min(100, score))
    return score

def generate_action_items(errors, text, context):
    """Generates 3 prioritized, specific action items based on issues found."""
    items = []
    
    critical_errors = [e for e in errors if e['severity'] == 'Critical']
    minor_errors = [e for e in errors if e['severity'] == 'Minor']
    
    # 1. Grammar focused
    if critical_errors:
        items.append(f"Fix {len(critical_errors)} critical spelling/grammar issues (e.g., '{critical_errors[0]['context']}').")
    elif minor_errors:
        items.append("Review punctuation and minor typographical errors.")
        
    # 2. Sentence Length / Clarity
    avg_len = textstat.avg_sentence_length(text) if text.strip() else 0
    if avg_len > 25:
        items.append(f"Shorten your sentences (currently averaging {avg_len} words). Aim for 15-20 words.")
    elif avg_len < 8 and text.strip():
        items.append("Vary your sentence structure; your sentences are very short and choppy.")
        
    # 3. Tone / Passive Voice
    passive_voice_regex = re.compile(r'\b(am|is|are|was|were|be|been|being)\s+\w+ed\b', re.IGNORECASE)
    passive_count = len(passive_voice_regex.findall(text)) if text.strip() else 0
    if passive_count > 0:
        items.append(f"Reduce passive voice. Found ~{passive_count} instance(s); use active voice for stronger impact.")
        
    # Fill remaining slots with generic helpful advice based on context
    defaults = [
        "Read your text out loud to catch awkward phrasing.",
        f"Keep the '{context}' audience in mind and adjust formality accordingly.",
        "Use more precise vocabulary instead of generic terms like 'things' or 'stuff'."
    ]
    
    for default in defaults:
        if len(items) < 3:
            items.append(default)
            
    return items[:3]

def count_fillers(text):
    """Counts common filler words using regex."""
    if not text.strip():
        return 0, text
        
    fillers = [r'\bum\b', r'\buh\b', r'\blike\b', r'\byou know\b', r'\bactually\b', r'\bbasically\b']
    pattern = re.compile('|'.join(fillers), re.IGNORECASE)
    
    matches = pattern.findall(text)
    
    # Strip fillers for the 'filler-free' comparison
    text_stripped = pattern.sub('', text)
    # clean up double spaces
    text_stripped = re.sub(' +', ' ', text_stripped)
    
    return len(matches), text_stripped

def calculate_wpm(audio_bytes, word_count):
    """Estimates WPM from a wav audio file byte stream."""
    try:
        with wave.open(io.BytesIO(audio_bytes), 'rb') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            duration_seconds = frames / float(rate)
            if duration_seconds > 0:
                wpm = (word_count / duration_seconds) * 60
                return round(wpm)
    except Exception as e:
        pass
    return None

def process_audio(audio_file):
    """Converts uploaded .wav file to text using SpeechRecognition and Google's free API."""
    r = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data)
            return text
    except sr.UnknownValueError:
        return "ERROR: Could not understand the audio."
    except sr.RequestError:
        return "ERROR: Could not request results from the speech recognition service."
    except Exception as e:
        return "ERROR: Processing audio file failed. Ensure it is a valid WAV file."


# --- 3. UI AND APP LOGIC ---
st.set_page_config(page_title="Communication Assessment Agent", layout="wide")

# Initialize DB on first run
init_db()

st.title("🗣️ Communication Assessment Agent")
st.write("Assess your written and spoken communication skills, get actionable feedback, and track improvement over time.")

context = st.selectbox(
    "Select Context (adapts scoring criteria):", 
    ["Job Interview", "Casual Chat", "Presentation", "Email"]
)

tab1, tab2, tab3 = st.tabs(["✍️ Written Assessment", "🎙️ Spoken Assessment", "📈 History / Dashboard"])

# --- TAB 1: WRITTEN ASSESSMENT ---
with tab1:
    st.header("Written Communication")
    text_input = st.text_area("Paste or type your text here:", height=200)
    
    if st.button("Assess Written Text"):
        if text_input.strip():
            with st.spinner("Analyzing text..."):
                g_score, errors = analyze_grammar(text_input)
                c_score = analyze_clarity(text_input)
                v_score = analyze_vocab(text_input)
                t_score = analyze_tone(text_input, context)
                
                overall = (g_score + c_score + v_score + t_score) / 4
                
                # Save to DB
                save_submission("Written", context, g_score, c_score, v_score, t_score, overall, 0, 0.0, text_input)
                
                st.subheader(f"Overall Score: {overall:.1f} / 100")
                
                # Bar chart of sub-scores
                scores_df = pd.DataFrame({
                    "Category": ["Grammar", "Clarity", "Vocabulary", "Tone"],
                    "Score": [g_score, c_score, v_score, t_score]
                }).set_index("Category")
                st.bar_chart(scores_df)
                
                st.subheader("Top 3 Action Items")
                actions = generate_action_items(errors, text_input, context)
                for i, action in enumerate(actions, 1):
                    st.write(f"{i}. {action}")
                
                st.subheader("Detailed Errors")
                if errors:
                    for e in errors:
                        if e['severity'] == 'Critical':
                            st.error(f"**{e['severity']}**: {e['msg']} (Context: '{e['context']}') -> Suggestion: {e['replacement']}")
                        elif e['severity'] == 'Minor':
                            st.warning(f"**{e['severity']}**: {e['msg']} (Context: '{e['context']}') -> Suggestion: {e['replacement']}")
                        else:
                            st.info(f"**{e['severity']}**: {e['msg']} (Context: '{e['context']}') -> Suggestion: {e['replacement']}")
                else:
                    st.success("No grammar or spelling errors found!")
        else:
            st.warning("Please enter some text to assess.")

# --- TAB 2: SPOKEN ASSESSMENT ---
with tab2:
    st.header("Spoken Communication")
    st.write("Upload a `.wav` file of your speech.")
    audio_file = st.file_uploader("Upload Audio", type=["wav"])
    
    if st.button("Assess Spoken Audio"):
        if audio_file is not None:
            with st.spinner("Transcribing and analyzing audio... (This may take a moment)"):
                audio_bytes = audio_file.read()
                audio_file.seek(0) # reset pointer for speech_recognition
                
                transcript = process_audio(audio_file)
                
                if transcript.startswith("ERROR:"):
                    st.error(transcript)
                else:
                    st.write("**Transcript:**")
                    st.write(f"> {transcript}")
                    
                    word_count = len(transcript.split())
                    wpm = calculate_wpm(audio_bytes, word_count)
                    filler_count, transcript_no_fillers = count_fillers(transcript)
                    
                    # Original scores
                    g_score, errors = analyze_grammar(transcript)
                    c_score = analyze_clarity(transcript)
                    v_score = analyze_vocab(transcript)
                    t_score = analyze_tone(transcript, context)
                    overall = (g_score + c_score + v_score + t_score) / 4
                    
                    # Filler-free scores
                    _, _ = analyze_grammar(transcript_no_fillers) # usually same
                    c_score_ff = analyze_clarity(transcript_no_fillers)
                    v_score_ff = analyze_vocab(transcript_no_fillers)
                    t_score_ff = analyze_tone(transcript_no_fillers, context)
                    overall_ff = (g_score + c_score_ff + v_score_ff + t_score_ff) / 4
                    
                    # Save to DB
                    save_submission("Spoken", context, g_score, c_score, v_score, t_score, overall, filler_count, wpm or 0.0, transcript)
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Overall Score", f"{overall:.1f}")
                    col2.metric("Filler Words", filler_count)
                    col3.metric("WPM", f"{wpm}" if wpm else "N/A")
                    
                    st.subheader("Filler-Free Potential")
                    st.write(f"If you removed filler words, your overall score might improve to **{overall_ff:.1f}**.")
                    
                    st.subheader("Sub-Scores")
                    scores_df = pd.DataFrame({
                        "Category": ["Grammar", "Clarity", "Vocabulary", "Tone"],
                        "Raw Score": [g_score, c_score, v_score, t_score],
                        "Filler-Free Score": [g_score, c_score_ff, v_score_ff, t_score_ff]
                    }).set_index("Category")
                    st.bar_chart(scores_df)
                    
                    st.subheader("Top 3 Action Items")
                    actions = generate_action_items(errors, transcript, context)
                    if filler_count >= 3:
                        actions[0] = f"Reduce filler words. You used {filler_count} fillers like 'um' or 'like'."
                    
                    for i, action in enumerate(actions[:3], 1):
                        st.write(f"{i}. {action}")
                        
        else:
            st.warning("Please upload a .wav file first.")

# --- TAB 3: HISTORY / DASHBOARD ---
with tab3:
    st.header("Performance History")
    df = get_all_submissions()
    
    if df.empty:
        st.info("No assessments yet. Complete a written or spoken assessment to see your history.")
    else:
        st.subheader("Overall Score Trend")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_sorted = df.sort_values('timestamp')
        
        # Line chart of overall score over time
        chart_data = df_sorted[['timestamp', 'overall_score']].set_index('timestamp')
        st.line_chart(chart_data)
        
        # Averages
        written_avg = df[df['type'] == 'Written']['overall_score'].mean()
        spoken_avg = df[df['type'] == 'Spoken']['overall_score'].mean()
        
        col1, col2 = st.columns(2)
        col1.metric("Avg Written Score", f"{written_avg:.1f}" if pd.notna(written_avg) else "N/A")
        col2.metric("Avg Spoken Score", f"{spoken_avg:.1f}" if pd.notna(spoken_avg) else "N/A")
        
        # Auto-generated insight
        st.subheader("AI Insight")
        if pd.notna(written_avg) and pd.notna(spoken_avg):
            if written_avg > spoken_avg + 5:
                st.write("💡 Your written communication is stronger than your spoken. Focus on reducing filler words and speaking confidently.")
            elif spoken_avg > written_avg + 5:
                st.write("💡 Your spoken communication is stronger than your written. Review grammar and sentence structure in your writing.")
            else:
                st.write("💡 Your written and spoken communication are well-balanced. Keep practicing to raise both scores!")
        else:
            st.write("💡 Complete at least one written and one spoken assessment to get comparative insights.")
            
        st.subheader("Submission Log")
        st.dataframe(df[['timestamp', 'type', 'context', 'overall_score', 'grammar_score', 'clarity_score', 'filler_count', 'wpm']])
