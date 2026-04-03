import streamlit as st
import pandas as pd
import re
import smtplib
import time
import requests
from typing import List, Tuple

# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Email Verifier",
    page_icon="📧",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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
        color: #ffffff; font-size: 0.95rem; font-weight: 400; transition: all 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus { border-color: #e2e8f0; box-shadow: 0 0 0 1px rgba(255,255,255,0.2); }
    .stButton button {
        background: #1a1a1a; color: #ffffff; border: none; border-radius: 6px;
        padding: 0.625rem 1.5rem; font-weight: 500; font-size: 0.9rem; transition: all 0.2s ease;
    }
    .stButton button:hover { background: #2d2d2d; transform: translateY(-1px); }
    .metric-box { background: #1a1a1a; padding: 1.5rem; border-radius: 8px; text-align: center; border: 2px solid #ffffff; }
    .metric-num { font-size: 1.75rem; font-weight: 600; color: #ffffff; }
    .metric-label { font-size: 0.75rem; color: #e2e8f0; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500; margin-top: 0.5rem; }
    .badge { display: inline-block; padding: 0.375rem 0.875rem; border-radius: 99px; font-size: 0.8rem; font-weight: 600; }
    .badge-valid { background: #dcfce7; color: #166534; }
    .badge-probably_valid { background: #dbeafe; color: #1e40af; }
    .badge-risky { background: #fef3c7; color: #92400e; }
    .badge-invalid { background: #fee2e2; color: #991b1b; }
    .result-card { background: #1a1a1a; padding: 2rem; border-radius: 12px; border: 2px solid #ffffff; }
    .result-card.valid { border-color: #16a34a; }
    .result-card.probably_valid { border-color: #2563eb; }
    .result-card.risky { border-color: #d97706; }
    .result-card.invalid { border-color: #dc2626; }
    .result-email { font-size: 1.25rem; font-weight: 600; color: #ffffff; margin-bottom: 1rem; }
    .result-text { font-size: 0.9rem; color: #e2e8f0; }
    .result-label { font-weight: 600; color: #ffffff; }
    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------

DISPOSABLE_DOMAINS = {
    "tempmail.com", "throwaway.com", "guerrillamail.com", "mailinator.com",
    "10minutemail.com", "fakeinbox.com", "trashmail.com", "yopmail.com",
    "spam4.me", "maildrop.cc", "dispostable.com", "trashmail.at",
    "trashmail.io", "trashmail.me", "getairmail.com", "discard.email",
    "sharklasers.com", "spambog.com", "spamgourmet.com", "tempemail.com",
    "tempr.email", "throwam.com", "spamex.com", "spamfree24.de",
    "mytrashmail.com", "spamcannon.com", "spambox.us", "yopmail.fr",
    "trashmailer.com", "trashymail.com", "wegwerfemail.com", "filzmail.com",
    "spambox.info", "nomail.pw", "spamoff.de", "zetmail.com",
    "spaml.com", "spaml.de", "spammotel.com", "kurzepost.de",
    "spamday.com", "anonbox.net", "binkmail.com", "tempalias.com",
    "spamkill.info", "mintemail.com", "tempinbox.com",
    "temporaryemail.net", "quickinbox.com", "zoemail.org",
    "grr.la", "guerrillamail.info", "guerrillamail.biz",
}

ROLE_PREFIXES = {
    "admin", "support", "info", "contact", "sales", "marketing",
    "hr", "jobs", "billing", "help", "noreply", "no-reply",
    "postmaster", "webmaster", "abuse", "hostmaster", "security",
    "privacy", "legal", "press", "media", "team", "hello",
    "office", "mail", "email", "enquiries", "service", "services",
    "feedback", "newsletter", "donotreply", "do-not-reply",
    "unsubscribe", "bounce", "mailer-daemon", "daemon",
}

# Providers that always block port-25 — confirmed MX is enough signal
SMTP_BLOCKED_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.co.in",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "aol.com", "icloud.com", "me.com", "mac.com",
    "protonmail.com", "proton.me", "pm.me",
    "zoho.com", "fastmail.com", "fastmail.fm",
    "tutanota.com", "tutanota.de", "tuta.io",
    "gmx.com", "gmx.net", "gmx.de",
    "mail.com", "yandex.com", "yandex.ru",
    "office365.com", "microsoft.com",
}

DOH_ENDPOINTS = [
    "https://dns.google/resolve",
    "https://cloudflare-dns.com/dns-query",
]

# -----------------------------------------------------------------------------
# DNS-OVER-HTTPS  (bypasses unreliable local DNS on Streamlit free tier)
# -----------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def get_mx_doh(domain: str) -> List[str]:
    """
    Fetch MX records via DNS-over-HTTPS.
    Tries Google DoH first, then Cloudflare as fallback.
    Returns sorted list of MX hostnames, empty list if none found.
    """
    for endpoint in DOH_ENDPOINTS:
        try:
            r = requests.get(
                endpoint,
                params={"name": domain, "type": "MX"},
                headers={"Accept": "application/dns-json"},
                timeout=6,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            if data.get("Status") == 3:   # NXDOMAIN — domain doesn't exist
                return []
            mx_list = []
            for ans in data.get("Answer", []):
                if ans.get("type") == 15:  # MX record type ID
                    parts = str(ans["data"]).split(" ", 1)
                    if len(parts) == 2:
                        mx_list.append((int(parts[0]), parts[1].rstrip(".")))
            mx_list.sort(key=lambda x: x[0])
            return [h for _, h in mx_list]
        except Exception:
            continue
    return []


@st.cache_data(ttl=3600, show_spinner=False)
def domain_exists_doh(domain: str) -> bool:
    """Check if domain resolves at all via DoH (A record lookup)."""
    for endpoint in DOH_ENDPOINTS:
        try:
            r = requests.get(
                endpoint,
                params={"name": domain, "type": "A"},
                headers={"Accept": "application/dns-json"},
                timeout=6,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            if data.get("Status") == 3:
                return False
            return len(data.get("Answer", [])) > 0
        except Exception:
            continue
    # If DoH itself fails (network issue), assume domain might exist — don't penalize
    return True


# -----------------------------------------------------------------------------
# SYNTAX
# -----------------------------------------------------------------------------

def validate_syntax(email: str) -> bool:
    if len(email) > 254:
        return False
    local, _, domain_part = email.partition("@")
    if not local or not domain_part:
        return False
    if ".." in local:
        return False
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# -----------------------------------------------------------------------------
# SMTP
# -----------------------------------------------------------------------------

def smtp_check(email: str, mx_list: List[str], timeout: int = 6) -> Tuple[str, str]:
    """
    Returns (result_code, detail).
    Codes: 'accept' | 'reject' | 'greylist' | 'blocked' | 'unknown' | 'error'
    """
    for mx in mx_list[:3]:
        try:
            server = smtplib.SMTP(timeout=timeout)
            server.connect(mx, 25)
            server.ehlo_or_helo_if_needed()
            server.mail("verify@example.com")
            code, msg = server.rcpt(email)
            server.quit()
            msg_s = msg.decode(errors="ignore").lower() if isinstance(msg, bytes) else str(msg).lower()
            if code == 250:
                return "accept", "Accepted"
            elif code in (550, 551, 553):
                if any(k in msg_s for k in ["user", "mailbox", "unknown", "does not exist", "no such", "invalid"]):
                    return "reject", f"User unknown ({code})"
                return "reject", f"Rejected ({code})"
            elif code in (450, 451, 452):
                return "greylist", f"Temp reject ({code})"
            elif code == 252:
                return "unknown", "Catch-all (252)"
            elif code == 421:
                return "blocked", "Service unavailable"
            else:
                return "unknown", f"Code {code}"
        except (ConnectionRefusedError, OSError):
            continue
        except smtplib.SMTPConnectError:
            continue
        except smtplib.SMTPServerDisconnected:
            return "greylist", "Early disconnect"
        except Exception:
            continue
    return "blocked", "Port 25 blocked"


# -----------------------------------------------------------------------------
# SCORING
# -----------------------------------------------------------------------------

def calc_score(
    syntax_ok: bool,
    disposable: bool,
    role: bool,
    mx_records: List[str],
    domain_found: bool,
    smtp_result: str,
    domain: str,
) -> Tuple[int, str, str]:
    """
    Scoring rules:
    - No syntax / disposable → immediately invalid (score 0-5)
    - MX not found + domain not found → probably invalid (-70)
    - MX not found but domain exists → slight penalty (-20)
    - SMTP blocked → NEUTRAL, not a sign of invalidity
    - SMTP accept → confirmed valid (no penalty)
    - SMTP reject → strong negative (-70)
    - SMTP greylist → tiny negative (-3), server responded
    - SMTP catch-all → moderate uncertainty (-18)
    - Role address → tiny note (-3), still deliverable
    """
    if not syntax_ok:
        return 0, "invalid", "Invalid syntax"
    if disposable:
        return 5, "invalid", "Disposable domain"

    score = 100
    reasons: List[str] = []
    mx_ok = len(mx_records) > 0
    is_known = domain in SMTP_BLOCKED_PROVIDERS

    # Domain / MX
    if not mx_ok:
        if not domain_found:
            score -= 70
            reasons.append("Domain not found")
        else:
            score -= 20
            reasons.append("No MX record")

    # SMTP
    if mx_ok:
        if smtp_result == "accept":
            pass  # confirmed
        elif smtp_result == "reject":
            score -= 70
            reasons.append("Mailbox rejected by server")
        elif smtp_result == "blocked":
            # Port 25 firewalled — extremely common, means nothing about validity
            if not is_known:
                score -= 8
                reasons.append("SMTP unverifiable (port blocked)")
            # known providers: zero penalty
        elif smtp_result == "greylist":
            score -= 3
            reasons.append("Greylisted (temporary)")
        elif smtp_result == "unknown":
            score -= 18
            reasons.append("Catch-all server")
        elif smtp_result == "error":
            score -= 8
            reasons.append("SMTP error")

    if role:
        score -= 3
        reasons.append("Role-based address")

    score = max(0, score)

    if score >= 80:
        status = "valid"
    elif score >= 60:
        status = "probably_valid"
    elif score >= 40:
        status = "risky"
    else:
        status = "invalid"

    reason = "; ".join(reasons) if reasons else "All checks passed"
    return score, status, reason


# -----------------------------------------------------------------------------
# VERIFY LOOP
# -----------------------------------------------------------------------------

def verify_emails(emails: List[str]) -> pd.DataFrame:
    results = []
    last_req: dict = {}
    valid_list = [e.strip() for e in emails if e.strip() and "@" in e]

    bar = st.progress(0)
    msg = st.empty()
    total = len(valid_list)

    for i, email in enumerate(valid_list):
        email = email.lower().strip()
        local, _, domain = email.partition("@")

        # Per-domain rate limiting
        now = time.time()
        gap = now - last_req.get(domain, 0)
        if gap < 1.0:
            time.sleep(1.0 - gap)
        last_req[domain] = time.time()

        msg.text(f"Checking {email}...")

        syntax_ok = validate_syntax(email)
        is_disposable = domain in DISPOSABLE_DOMAINS
        is_role = local in ROLE_PREFIXES

        mx_records: List[str] = []
        domain_found = False

        if syntax_ok and not is_disposable:
            mx_records = get_mx_doh(domain)
            if mx_records:
                domain_found = True
            else:
                domain_found = domain_exists_doh(domain)

        smtp_result, smtp_detail = "blocked", "Skipped"
        if syntax_ok and mx_records and not is_disposable:
            smtp_result, smtp_detail = smtp_check(email, mx_records)

        score, status, reason = calc_score(
            syntax_ok, is_disposable, is_role,
            mx_records, domain_found, smtp_result, domain
        )

        results.append({
            "Email": email,
            "Status": status,
            "Score": score,
            "Reason": reason,
            "MX": len(mx_records),
            "SMTP": smtp_detail,
        })

        bar.progress((i + 1) / total)

    bar.empty()
    msg.empty()
    return pd.DataFrame(results)


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

def show_summary(df: pd.DataFrame):
    total     = len(df)
    valid     = len(df[df["Status"] == "valid"])
    uncertain = len(df[df["Status"].isin(["probably_valid", "risky"])])
    invalid   = len(df[df["Status"] == "invalid"])

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-box"><div class="metric-num">{total}</div><div class="metric-label">Total</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-box" style="border-color:#16a34a"><div class="metric-num" style="color:#16a34a">{valid}</div><div class="metric-label">Valid</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-box" style="border-color:#d97706"><div class="metric-num" style="color:#d97706">{uncertain}</div><div class="metric-label">Uncertain</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-box" style="border-color:#dc2626"><div class="metric-num" style="color:#dc2626">{invalid}</div><div class="metric-label">Invalid</div></div>', unsafe_allow_html=True)

    st.divider()

    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "Status": st.column_config.TextColumn(width="small"),
                     "Score":  st.column_config.NumberColumn(width="small"),
                     "MX":     st.column_config.NumberColumn(width="small"),
                     "Reason": st.column_config.TextColumn(width="medium"),
                     "SMTP":   st.column_config.TextColumn(width="small"),
                 })

    st.download_button("Download CSV",
                       data=df.to_csv(index=False).encode("utf-8"),
                       file_name="results.csv", mime="text/csv")


def main():
    st.markdown("<h1>Email Verifier</h1>", unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Validate emails with syntax, domain, and SMTP checks.</p>', unsafe_allow_html=True)

    if "df" not in st.session_state:
        st.session_state.df = None

    tab_single, tab_manual, tab_batch = st.tabs(["Single", "Manual", "Batch"])

    with tab_single:
        single = st.text_input("", placeholder="name@company.com", label_visibility="collapsed")
        if st.button("Verify", key="btn_single"):
            if single.strip():
                result = verify_emails([single.strip()])
                st.session_state.df = result
                if not result.empty:
                    row = result.iloc[0]
                    sc = row["Status"]
                    st.markdown(f"""
                    <div class="result-card {sc}">
                        <div class="result-email">{row['Email']}</div>
                        <div style="display:flex;gap:1rem;align-items:center;margin-bottom:1rem;">
                            <span class="badge badge-{sc}">{sc.replace('_',' ').title()}</span>
                            <span class="result-text">Score: <strong>{row['Score']}</strong>/100</span>
                        </div>
                        <div>
                            <span class="result-label">Reason:</span>
                            <span class="result-text">&nbsp;{row['Reason']}</span><br>
                            <span class="result-label">MX records:</span>
                            <span class="result-text">&nbsp;{row['MX']}</span><br>
                            <span class="result-label">SMTP:</span>
                            <span class="result-text">&nbsp;{row['SMTP']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_manual:
        st.write("Paste emails (one per line):")
        text = st.text_area("", height=180,
                            placeholder="user@example.com\nanother@test.org",
                            label_visibility="collapsed")
        if st.button("Verify", key="btn_manual"):
            if text.strip():
                emails = [l.strip() for l in text.split("\n") if l.strip()]
                if emails:
                    st.session_state.df = verify_emails(emails)

    with tab_batch:
        file = st.file_uploader("Upload CSV with an 'email' column",
                                type=["csv"], label_visibility="collapsed")
        if file:
            try:
                df_in = pd.read_csv(file)
                if "email" not in df_in.columns:
                    st.error("CSV must have an 'email' column.")
                else:
                    emails = df_in["email"].dropna().astype(str).tolist()
                    st.info(f"{len(emails)} emails loaded.")
                    if st.button("Verify", key="btn_batch"):
                        st.session_state.df = verify_emails(emails)
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.df is not None and not st.session_state.df.empty:
        show_summary(st.session_state.df)


if __name__ == "__main__":
    main()
