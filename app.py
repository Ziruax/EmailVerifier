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

# Minimalist CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    .block-container { padding-top: 2rem; max-width: 900px; }
    
    h1 { font-size: 2rem; font-weight: 700; color: #1a1a1a; margin-bottom: 0.5rem; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    .subtitle { color: #333333; font-size: 1rem; margin-bottom: 2rem; font-weight: 500; }
    
    .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #333333; gap: 1rem; }
    .stTabs [data-baseweb="tab"] { color: #333333; font-weight: 600; font-size: 1rem; padding: 0.75rem 1.5rem; }
    .stTabs [aria-selected="true"] { color: #ffffff; background: #2563eb; border-bottom: none; border-radius: 8px 8px 0 0; }
    
    .stTextInput input, .stTextArea textarea { 
        background: #ffffff; border: 2px solid #333333; border-radius: 8px; 
        color: #000000; font-size: 1rem; font-weight: 500;
    }
    .stTextInput input:focus, .stTextArea textarea:focus { border-color: #2563eb; outline: none; box-shadow: 0 0 0 3px rgba(37,99,235,0.2); }
    
    .stButton button {
        background: #2563eb; color: #ffffff; border: none; border-radius: 8px;
        padding: 0.75rem 2rem; font-weight: 600; font-size: 1rem;
        box-shadow: 0 2px 4px rgba(37,99,235,0.3);
    }
    .stButton button:hover { background: #1d4ed8; box-shadow: 0 4px 8px rgba(37,99,235,0.4); }
    
    .metric-box {
        background: #ffffff; padding: 1.25rem; border-radius: 12px;
        text-align: center; border: 3px solid #333333; box-shadow: 4px 4px 0px rgba(0,0,0,0.1);
    }
    .metric-num { font-size: 2rem; font-weight: 700; color: #1a1a1a; }
    .metric-label { font-size: 0.85rem; color: #333333; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-top: 0.5rem; }
    
    .badge { display: inline-block; padding: 0.5rem 1rem; border-radius: 99px; font-size: 0.9rem; font-weight: 700; border: 2px solid #000000; }
    .badge-valid { background: #22c55e; color: #ffffff; }
    .badge-probably_valid { background: #3b82f6; color: #ffffff; }
    .badge-probably { background: #3b82f6; color: #ffffff; }
    .badge-risky { background: #f59e0b; color: #000000; }
    .badge-invalid { background: #ef4444; color: #ffffff; }
    
    .result-card {
        background: #ffffff; padding: 1.5rem; border-radius: 12px;
        border: 3px solid #333333; box-shadow: 4px 4px 0px rgba(0,0,0,0.15);
    }
    .result-card.valid { background: #dcfce7; border-color: #16a34a; }
    .result-card.probably_valid { background: #dbeafe; border-color: #2563eb; }
    .result-card.risky { background: #fef3c7; border-color: #d97706; }
    .result-card.invalid { background: #fee2e2; border-color: #dc2626; }
    
    .result-email { font-size: 1.4rem; font-weight: 700; color: #1a1a1a; margin-bottom: 0.75rem; }
    .result-text { font-size: 1rem; color: #1a1a1a; font-weight: 600; }
    .result-label { font-weight: 700; color: #1a1a1a; }
    
    #MainMenu, footer, header { visibility: hidden; }
    
    .stDataFrame { border: 2px solid #333333; border-radius: 8px; }
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
