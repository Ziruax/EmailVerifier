import streamlit as st
import pandas as pd
import re
import dns.resolver
import smtplib
import socket
import time
from typing import List, Tuple

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Email Verifier",
    page_icon="📧",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Minimalist Modern Clean CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    .block-container { padding-top: 3rem; max-width: 800px; }
    
    h1 { font-size: 1.75rem; font-weight: 600; color: #ffffff; margin-bottom: 0.25rem; letter-spacing: -0.02em; }
    .subtitle { color: #e2e8f0; font-size: 0.95rem; margin-bottom: 2.5rem; font-weight: 400; }
    
    .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid #4a5568; gap: 2rem; }
    .stTabs [data-baseweb="tab"] { color: #9ca3af; font-weight: 500; font-size: 0.9rem; padding: 0.5rem 0; background: transparent !important; }
    .stTabs [aria-selected="true"] { color: #ffffff; border-bottom: 2px solid #ffffff; background: transparent !important; border-radius: 0; }
    
    .stTextInput input, .stTextArea textarea { 
        background: #1a1a1a; border: 1px solid #ffffff; border-radius: 6px; 
        color: #ffffff; font-size: 0.95rem; font-weight: 400;
        transition: all 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus { border-color: #e2e8f0; outline: none; box-shadow: 0 0 0 1px rgba(255,255,255,0.2); }
    
    .stButton button {
        background: #1a1a1a; color: #ffffff; border: none; border-radius: 6px;
        padding: 0.625rem 1.5rem; font-weight: 500; font-size: 0.9rem;
        transition: all 0.2s ease;
    }
    .stButton button:hover { background: #2d2d2d; transform: translateY(-1px); }
    
    .metric-box {
        background: #1a1a1a; padding: 1.5rem; border-radius: 8px;
        text-align: center; border: 2px solid #ffffff;
    }
    .metric-num { font-size: 1.75rem; font-weight: 600; color: #ffffff; }
    .metric-label { font-size: 0.75rem; color: #e2e8f0; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500; margin-top: 0.5rem; }
    
    .badge { display: inline-block; padding: 0.375rem 0.875rem; border-radius: 99px; font-size: 0.8rem; font-weight: 600; }
    .badge-valid { background: #dcfce7; color: #166534; }
    .badge-probably_valid { background: #dbeafe; color: #1e40af; }
    .badge-probably { background: #dbeafe; color: #1e40af; }
    .badge-risky { background: #fef3c7; color: #92400e; }
    .badge-invalid { background: #fee2e2; color: #991b1b; }
    
    .result-card {
        background: #1a1a1a; padding: 2rem; border-radius: 12px;
        border: 2px solid #ffffff;
    }
    .result-card.valid { background: #1a1a1a; border-color: #16a34a; }
    .result-card.probably_valid { background: #1a1a1a; border-color: #2563eb; }
    .result-card.risky { background: #1a1a1a; border-color: #d97706; }
    .result-card.invalid { background: #1a1a1a; border-color: #dc2626; }
    
    .result-email { font-size: 1.25rem; font-weight: 600; color: #ffffff; margin-bottom: 1rem; letter-spacing: -0.01em; }
    .result-text { font-size: 0.9rem; color: #e2e8f0; font-weight: 400; }
    .result-label { font-weight: 600; color: #ffffff; }
    
    #MainMenu, footer, header { visibility: hidden; }
    
    .stDataFrame { border: 1px solid #ffffff; border-radius: 8px; }
    .stDataFrame th { background: #1a1a1a; color: #ffffff; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .stDataFrame td { color: #e2e8f0; font-size: 0.9rem; }
    
    .stFileUploader { border: 1px dashed #ffffff; border-radius: 8px; padding: 1.5rem; }
    .stFileUploader:hover { border-color: #e2e8f0; background: #1a1a1a; }
</style>
""", unsafe_allow_html=True)

DISPOSABLE_DOMAINS = {"tempmail.com", "throwaway.com", "guerrillamail.com", "mailinator.com", "10minutemail.com", "fakeinbox.com", "trashmail.com", "yopmail.com"}
ROLE_PREFIXES = {"admin", "support", "info", "contact", "sales", "marketing", "hr", "jobs", "billing", "help", "noreply", "no-reply", "postmaster", "webmaster"}
MAJOR_PROVIDERS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", "icloud.com"}

# -----------------------------------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------------------------------

def validate_syntax(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def check_disposable(domain: str) -> bool:
    return domain.lower() in DISPOSABLE_DOMAINS

def check_role(local: str) -> bool:
    return local.lower() in ROLE_PREFIXES

@st.cache_data(ttl=7200)
def get_mx(domain: str) -> List[str]:
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        return [str(r.exchange).rstrip('.') for r in sorted(answers, key=lambda x: x.preference)]
    except:
        return []

def smtp_check(email: str, mx_list: List[str], timeout: int = 5) -> Tuple[bool, str]:
    if not mx_list:
        return False, "No MX"
    for mx in mx_list[:3]:
        try:
            server = smtplib.SMTP(timeout=timeout)
            server.set_debuglevel(0)
            server.connect(mx, 25)
            server.helo()
            server.mail('verify@example.com')
            code, _ = server.rcpt(email)
            server.quit()
            if code == 250:
                return True, "OK"
            elif code == 550:
                return False, "User unknown"
        except:
            continue
    return False, "Failed"

def calc_score(email: str, syntax: bool, disposable: bool, role: bool, mx_ok: bool, smtp_ok: bool) -> Tuple[int, str, str]:
    if not syntax:
        return 0, "invalid", "Invalid syntax"
    if disposable:
        return 15, "invalid", "Disposable domain"
    
    score = 100
    reasons = []
    
    if role:
        score -= 25
        reasons.append("Role-based")
    if not mx_ok:
        score -= 40
        reasons.append("No MX")
    elif not smtp_ok:
        if any(p in email.lower() for p in MAJOR_PROVIDERS):
            score -= 10
            reasons.append("SMTP blocked (likely valid)")
        else:
            score -= 30
            reasons.append("SMTP rejected")
    
    if any(p in email.lower() for p in MAJOR_PROVIDERS) and not smtp_ok:
        score = min(score, 85)
        status = "probably_valid" if score >= 60 else "risky"
    else:
        if score >= 85: status = "valid"
        elif score >= 60: status = "probably_valid"
        elif score >= 40: status = "risky"
        else: status = "invalid"
    
    reason = "; ".join(reasons) if reasons else "All checks passed"
    return max(0, score), status, reason

def verify_emails(emails: List[str]) -> pd.DataFrame:
    results = []
    last_time = {}
    progress = st.progress(0)
    status = st.empty()
    
    for i, email in enumerate(emails):
        email = email.strip()
        if not email or '@' not in email:
            continue
        
        local, domain = email.lower().split('@', 1)
        
        if domain in last_time and time.time() - last_time[domain] < 1.0:
            time.sleep(1.0 - (time.time() - last_time[domain]))
        last_time[domain] = time.time()
        
        syntax = validate_syntax(email)
        disposable = check_disposable(domain)
        role = check_role(local)
        mx = get_mx(domain)
        mx_ok = len(mx) > 0
        
        smtp_ok = False
        smtp_msg = ""
        if mx_ok and syntax and not disposable:
            smtp_ok, smtp_msg = smtp_check(email, mx)
        
        score, status_val, reason = calc_score(email, syntax, disposable, role, mx_ok, smtp_ok)
        
        results.append({
            "Email": email,
            "Status": status_val,
            "Score": score,
            "Reason": reason,
            "Details": f"MX:{len(mx)} | SMTP:{smtp_msg}"
        })
        
        progress.progress((i + 1) / len(emails))
        status.text(f"Checking {email}...")
    
    progress.empty()
    status.empty()
    return pd.DataFrame(results)

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

def main():
    st.markdown("<h1>Email Verifier</h1>", unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Validate emails with syntax, domain, and SMTP checks.</p>', unsafe_allow_html=True)
    
    tab_batch, tab_manual, tab_single = st.tabs(["Batch", "Manual", "Single"])
    
    if 'df' not in st.session_state:
        st.session_state.df = None
    
    with tab_batch:
        file = st.file_uploader("Upload CSV (column: 'email')", type=['csv'], label_visibility="collapsed")
        if file:
            try:
                df = pd.read_csv(file)
                if 'email' not in df.columns:
                    st.error("CSV must have 'email' column")
                else:
                    emails = df['email'].dropna().astype(str).tolist()
                    if st.button("Verify", key="btn_batch"):
                        st.session_state.df = verify_emails(emails)
            except Exception as e:
                st.error(f"Error: {e}")
    
    with tab_manual:
        st.write("Paste emails (one per line):")
        text = st.text_area("", height=180, placeholder="user@example.com\nanother@test.org", label_visibility="collapsed")
        if st.button("Verify", key="btn_manual"):
            if text:
                emails = [l.strip() for l in text.split('\n') if l.strip()]
                if emails:
                    st.session_state.df = verify_emails(emails)
                else:
                    st.warning("Enter at least one email")
    
    with tab_single:
        single = st.text_input("Email", placeholder="name@company.com", label_visibility="collapsed")
        if st.button("Verify", key="btn_single"):
            if single:
                result = verify_emails([single])
                st.session_state.df = result
                if not result.empty:
                    row = result.iloc[0]
                    status_class = row['Status']
                    st.markdown(f"""
                    <div class="result-card {status_class}">
                        <div class="result-email">{row['Email']}</div>
                        <div style="display:flex;gap:1rem;align-items:center;margin-bottom:1rem;">
                            <span class="badge badge-{status_class}">{status_class.replace('_',' ').title()}</span>
                            <span class="result-text">Score: <strong>{row['Score']}</strong>/100</span>
                        </div>
                        <div style="font-size:1rem;">
                            <span class="result-label">Reason:</span> <span class="result-text">{row['Reason']}</span><br>
                            <span class="result-label">Details:</span> <span class="result-text">{row['Details']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    if st.session_state.df is not None:
        df = st.session_state.df
        total = len(df)
        valid = len(df[df['Status'] == 'valid'])
        uncertain = len(df[df['Status'].isin(['risky', 'probably_valid'])])
        invalid = len(df[df['Status'] == 'invalid'])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="metric-box"><div class="metric-num">{total}</div><div class="metric-label">Total</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-box" style="border-color:#16a34a;"><div class="metric-num" style="color:#16a34a">{valid}</div><div class="metric-label">Valid</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-box" style="border-color:#d97706;"><div class="metric-num" style="color:#d97706">{uncertain}</div><div class="metric-label">Uncertain</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-box" style="border-color:#dc2626;"><div class="metric-num" style="color:#dc2626">{invalid}</div><div class="metric-label">Invalid</div></div>', unsafe_allow_html=True)
        
        st.divider()
        
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={
            "Status": st.column_config.TextColumn(width="small"),
            "Score": st.column_config.NumberColumn(min=0, max=100),
            "Reason": st.column_config.TextColumn(width="medium"),
            "Details": st.column_config.TextColumn(width="small")
        })
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name='results.csv', mime='text/csv')

if __name__ == "__main__":
    main()
