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

DISPOSABLE_DOMAINS = {
    "tempmail.com", "throwaway.com", "guerrillamail.com", "mailinator.com",
    "10minutemail.com", "fakeinbox.com", "trashmail.com", "yopmail.com",
    "sharklasers.com", "guerrillamailblock.com", "grr.la", "guerrillamail.info",
    "guerrillamail.biz", "guerrillamail.de", "guerrillamail.net", "guerrillamail.org",
    "spam4.me", "maildrop.cc", "dispostable.com", "mailnull.com", "spamgourmet.com",
    "trashmail.at", "trashmail.io", "trashmail.me", "getairmail.com", "discard.email",
    "wegwerfadresse.de", "spamhere.in", "anonbox.net", "binkmail.com", "bob.email",
    "clrmail.com", "cust.in", "dispostable.com", "filzmail.com", "fivemail.de",
    "haltospam.com", "ieatspam.eu", "ieatspam.info", "inoutmail.de", "jetable.fr.nf",
    "kasmail.com", "klassmaster.com", "kurzepost.de", "lhsdv.com", "lifebyfood.com",
    "link2mail.net", "litedrop.com", "lol.ovpn.to", "lookugly.com", "lordvoldemo.rt",
    "lortemail.dk", "meltmail.com", "mintemail.com", "mt2009.com", "mt2014.com",
    "mytrashmail.com", "netzidiot.de", "nik.kr", "no-spam.ws", "nobulk.com",
    "noclickemail.com", "nogmailspam.info", "nomail.pw", "nomail.xl.cx",
    "nomail2me.com", "nospam.ze.tc", "nospamfor.us", "nospammail.net",
    "nowmymail.com", "objectmail.com", "obobbo.com", "odaymail.com",
    "oneoffemail.com", "onewaymail.com", "online.ms", "oopi.org",
    "owlpic.com", "pookmail.com", "proxymail.eu", "punkass.com",
    "putthisinyourspamdatabase.com", "quickinbox.com", "rcpt.at",
    "re-gister.com", "receiveee.com", "rklips.com", "rppkn.com",
    "rtrtr.com", "s0ny.net", "safe-mail.gq", "safetymail.info",
    "safetypost.de", "sandelf.de", "SendSpamHere.com", "sf.bl.org.ua",
    "sharedmailbox.org", "sharklasers.com", "shieldemail.com", "shiftmail.com",
    "shortmail.net", "shredmail.com", "siliwangi.ga", "sinnlos-mail.de",
    "siteposter.net", "slaskpost.se", "slopsbox.com", "slow-talk.com",
    "smellfear.com", "snakemail.com", "sneakemail.com", "sneakmail.de",
    "snkmail.com", "sofimail.com", "sofort-mail.de", "soisz.com",
    "soodomail.com", "soodonims.com", "spam.la", "spam.su", "spam4.me",
    "spamavert.com", "spambob.com", "spambob.net", "spambob.org",
    "spambog.com", "spambog.de", "spambog.ru", "spambox.info", "spambox.irishspringrealty.com",
    "spambox.us", "spamcannon.com", "spamcannon.net", "spamcero.com",
    "spamcon.org", "spamcorptastic.com", "spamcowboy.com", "spamcowboy.net",
    "spamcowboy.org", "spamday.com", "spamex.com", "spamfree24.de",
    "spamfree24.eu", "spamfree24.info", "spamfree24.net", "spamfree24.org",
    "spamgoes.in", "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "spamherelots.com", "spamhereplease.com", "spamhole.com", "spamify.com",
    "spaminator.de", "spamkill.info", "spaml.com", "spaml.de",
    "spammotel.com", "spamoff.de", "spamslicer.com", "spamspot.com",
    "spamthis.co.uk", "spamthisplease.com", "spamtroll.net",
    "spamwaste.com", "spamx.men", "spamxme.com", "spazmail.com",
    "speed.1s.fr", "splyb.com", "spoofmail.de", "squizzy.net",
    "ssoia.com", "startkeys.com", "stinkefinger.net", "stuffmail.de",
    "super-auswahl.de", "supergreatmail.com", "supermailer.jp",
    "superrito.com", "superstachel.de", "suremail.info", "svk.jp",
    "sweetxxx.de", "tafmail.com", "tagyourself.com", "talkinator.com",
    "teewars.org", "telecomix.pl", "tempalias.com", "tempe-mail.com",
    "tempemail.biz", "tempemail.com", "tempemail.net", "tempinbox.co.uk",
    "tempinbox.com", "tempmail.eu", "tempmail.it", "tempmail2.com",
    "tempomail.fr", "temporarily.de", "temporarioemail.com.br",
    "temporaryemail.net", "temporaryemail.us", "temporaryforwarding.com",
    "temporaryinbox.com", "temporarymail.org", "tempsky.com",
    "tempthe.net", "tempymail.com", "thanksnospam.info", "thankyou2010.com",
    "thc.st", "thelimestones.com", "thisisnotmyrealemail.com",
    "thismail.net", "throwam.com", "throwawayemailaddress.com",
    "throwam.com", "tilien.com", "tittbit.in", "tizi.com",
    "tmailinator.com", "toiea.com", "toomail.biz", "topranklist.de",
    "tradermail.info", "trash-amil.com", "trash-mail.at",
    "trash-mail.cf", "trash-mail.de", "trash-mail.ga", "trash-mail.gq",
    "trash-mail.io", "trash-mail.ml", "trash-mail.tk",
    "trashemail.de", "trashmail.at", "trashmail.com", "trashmail.io",
    "trashmail.me", "trashmail.net", "trashmail.org",
    "trashmailer.com", "trashymail.com", "trasz.com",
    "trbvm.com", "trbvn.com", "trialmail.de", "trickmail.net",
    "trillianpro.com", "tryalert.com", "turual.com", "twzhhq.com",
    "tyldd.com", "uggsrock.com", "umail.net", "unlimit.com",
    "unmail.ru", "uroid.com", "us.af", "utiket.us",
    "uu.gl", "valemail.net", "venompen.com", "veryrealemail.com",
    "viditag.com", "viewcastmedia.com", "viewcastmedia.net",
    "viewcastmedia.org", "viralplays.com", "vpn.st", "vsimcard.com",
    "vubby.com", "walala.org", "walkmail.net", "watchfull.net",
    "webemail.me", "weg-werf-email.de", "wegwerfadresse.de",
    "wegwerfemail.com", "wegwerfemail.de", "wegwerfmail.de",
    "wegwerfmail.info", "wegwerfmail.net", "wegwerfmail.org",
    "wembley.ovh", "wetrainbayarea.com", "wetrainbayarea.org",
    "wh4f.org", "whyspam.me", "willhackforfood.biz",
    "willselfdestruct.com", "winemaven.info", "wronghead.com",
    "wuzupmail.net", "www.e4ward.com", "www.gishpuppy.com",
    "www.mailinator.com", "wwwnew.eu", "xagloo.co", "xagloo.com",
    "xemaps.com", "xents.com", "xmail.biz", "xmail.net", "xmail.org",
    "xmaily.com", "xn--9kq967o.com", "xpectedget.com", "xup.in",
    "xww.ro", "yapped.net", "yeah.net", "yesey.net",
    "yogamaven.com", "yopmail.com", "yopmail.fr", "yoru-dea.com",
    "youmail.ga", "youmailr.com", "ypmail.webarnak.fr.eu.org",
    "yroid.com", "yuurok.com", "z1p.biz", "za.com",
    "zehnminutenmail.de", "zetmail.com", "zoemail.net",
    "zoemail.org", "zomg.inf",
}

# Role prefixes — valid for delivery but not personal
ROLE_PREFIXES = {
    "admin", "support", "info", "contact", "sales", "marketing",
    "hr", "jobs", "billing", "help", "noreply", "no-reply",
    "postmaster", "webmaster", "abuse", "hostmaster", "security",
    "privacy", "legal", "press", "media", "team", "hello",
    "office", "mail", "email", "enquiries", "enquiry", "service",
    "services", "feedback", "newsletter", "donotreply", "do-not-reply",
    "unsubscribe", "bounce", "mailer-daemon", "daemon",
}

MAJOR_PROVIDERS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "aol.com", "icloud.com", "live.com", "msn.com",
    "protonmail.com", "proton.me", "zoho.com", "fastmail.com",
    "tutanota.com", "pm.me", "yahoo.co.uk", "yahoo.co.in",
    "googlemail.com", "mail.com", "gmx.com", "gmx.net",
    "yandex.com", "yandex.ru",
}

# Known providers that always block port-25 SMTP verification
SMTP_ALWAYS_BLOCKED = MAJOR_PROVIDERS | {
    "office365.com", "microsoft.com", "exchange.microsoft.com",
}

# -----------------------------------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------------------------------

def validate_syntax(email: str) -> bool:
    """
    Stricter RFC-5321 syntax check:
    - local part: alphanumerics + . _ % + - (no consecutive dots, not starting/ending with dot)
    - domain: proper hostname segments
    - TLD: 2+ chars
    """
    pattern = r'^(?!.*\.\.)[a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,62}[a-zA-Z0-9]@[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    if len(email) > 254:
        return False
    return bool(re.match(pattern, email))

def validate_syntax_simple(email: str) -> bool:
    """Fallback for single-char local parts like a@b.com"""
    return bool(re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def check_disposable(domain: str) -> bool:
    return domain.lower() in DISPOSABLE_DOMAINS

def check_role(local: str) -> bool:
    return local.lower() in ROLE_PREFIXES

@st.cache_data(ttl=7200)
def get_mx(domain: str) -> List[str]:
    """Returns sorted list of MX hostnames, empty list on failure."""
    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=8.0)
        return [str(r.exchange).rstrip('.') for r in sorted(answers, key=lambda x: x.preference)]
    except dns.resolver.NXDOMAIN:
        return []
    except dns.resolver.NoAnswer:
        return []
    except Exception:
        return []

@st.cache_data(ttl=7200)
def has_a_record(domain: str) -> bool:
    """Check if domain has at least an A record (fallback when no MX)."""
    try:
        dns.resolver.resolve(domain, 'A', lifetime=5.0)
        return True
    except Exception:
        return False

def smtp_check(email: str, mx_list: List[str], timeout: int = 6) -> Tuple[str, str]:
    """
    Returns (result, detail):
      - 'accept'  : server confirmed mailbox exists (250)
      - 'reject'  : server explicitly rejected mailbox (550/551/553)
      - 'blocked' : connection blocked / port 25 refused (typical for cloud hosts)
      - 'greylist': server issued temporary rejection (450/451) — not invalid
      - 'unknown' : catch-all server or other unknown response
      - 'error'   : unexpected failure
    """
    if not mx_list:
        return 'blocked', 'No MX'

    connect_errors = 0
    for mx in mx_list[:3]:
        try:
            server = smtplib.SMTP(timeout=timeout)
            server.set_debuglevel(0)
            server.connect(mx, 25)
            server.ehlo_or_helo_if_needed()
            server.mail('verify@example.com')
            code, msg = server.rcpt(email)
            server.quit()

            msg_lower = msg.decode(errors='ignore').lower() if isinstance(msg, bytes) else str(msg).lower()

            if code == 250:
                return 'accept', 'Accepted'
            elif code in (550, 551, 553):
                # Distinguish explicit "user unknown" from catch-all rejection
                if any(k in msg_lower for k in ['user', 'mailbox', 'unknown', 'does not exist', 'no such']):
                    return 'reject', f'User unknown ({code})'
                return 'reject', f'Rejected ({code})'
            elif code in (450, 451, 452):
                return 'greylist', f'Temp reject ({code})'
            elif code == 421:
                return 'blocked', 'Service unavailable'
            elif code == 252:
                # Cannot verify but will attempt delivery — effectively unknown but valid-ish
                return 'unknown', 'Cannot verify (252)'
            else:
                return 'unknown', f'Code {code}'

        except (ConnectionRefusedError, OSError) as e:
            # Port 25 blocked (firewall/cloud hosting) — don't treat as invalid
            connect_errors += 1
            continue
        except smtplib.SMTPConnectError:
            connect_errors += 1
            continue
        except smtplib.SMTPServerDisconnected:
            # Server closed connection — often greylisting
            return 'greylist', 'Disconnected early'
        except smtplib.SMTPException as e:
            connect_errors += 1
            continue
        except Exception:
            connect_errors += 1
            continue

    if connect_errors == len(mx_list[:3]):
        return 'blocked', 'Port 25 blocked'
    return 'error', 'All MX failed'


def calc_score(
    email: str,
    syntax: bool,
    disposable: bool,
    role: bool,
    mx_ok: bool,
    a_record: bool,
    smtp_result: str,
    domain: str,
) -> Tuple[int, str, str]:
    """
    Revised scoring:
    - Syntax failure or disposable = immediately invalid
    - MX absence = strong negative but not automatic invalid
    - SMTP 'blocked' (port 25 firewalled) = neutral — don't penalize for cloud hosting
    - SMTP 'reject' (explicit 550) = strong negative
    - SMTP 'greylist' = slightly positive (server responded)
    - SMTP 'accept' = strong positive
    - SMTP 'unknown' (catch-all) = slight negative
    - Role address = minor note only, not a score penalty
    """
    if not syntax:
        return 0, "invalid", "Invalid syntax"

    if disposable:
        return 5, "invalid", "Disposable email domain"

    score = 100
    reasons = []
    is_known_provider = domain in MAJOR_PROVIDERS

    # --- MX / DNS ---
    if not mx_ok:
        if a_record:
            # Domain exists, uses implicit MX (rare but valid)
            score -= 15
            reasons.append("No MX (A record exists)")
        else:
            # Domain doesn't resolve at all
            score -= 55
            reasons.append("Domain not found")

    # --- SMTP interpretation ---
    if mx_ok:
        if smtp_result == 'accept':
            # Confirmed delivery — best outcome
            pass  # no deduction, score stays 100
        elif smtp_result == 'reject':
            # Server explicitly said this user doesn't exist
            score -= 65
            reasons.append("Mailbox rejected by server")
        elif smtp_result == 'blocked':
            # Port 25 blocked — common on cloud / shared hosting environments
            # Cannot determine, do NOT penalize heavily
            if is_known_provider:
                # Major providers always block; format is well-known, trust MX
                pass
            else:
                score -= 10
                reasons.append("SMTP unverifiable (port blocked)")
        elif smtp_result == 'greylist':
            # Temporary reject — server is alive, probably valid
            score -= 5
            reasons.append("Greylisted (temp)")
        elif smtp_result == 'unknown':
            # Catch-all server — cannot confirm individual mailbox
            score -= 20
            reasons.append("Catch-all server (unverifiable)")
        elif smtp_result == 'error':
            # Technical failure — treat same as blocked
            score -= 10
            reasons.append("SMTP check failed")

    # --- Role address — purely informational, minor deduction ---
    if role:
        score -= 5
        reasons.append("Role-based address")

    score = max(0, score)

    # --- Status thresholds ---
    if score >= 80:
        status = "valid"
    elif score >= 55:
        status = "probably_valid"
    elif score >= 35:
        status = "risky"
    else:
        status = "invalid"

    reason = "; ".join(reasons) if reasons else "All checks passed"
    return score, status, reason


def verify_emails(emails: List[str]) -> pd.DataFrame:
    results = []
    last_time: dict = {}
    progress = st.progress(0)
    status_text = st.empty()

    valid_emails = [e.strip() for e in emails if e.strip() and '@' in e.strip()]

    for i, email in enumerate(valid_emails):
        email = email.lower().strip()
        local, domain = email.split('@', 1)

        # Rate-limit per domain (1 req/s) to avoid bans
        if domain in last_time and time.time() - last_time[domain] < 1.0:
            time.sleep(1.0 - (time.time() - last_time[domain]))
        last_time[domain] = time.time()

        syntax = validate_syntax(email) or validate_syntax_simple(email)
        disposable = check_disposable(domain)
        role = check_role(local)
        mx = get_mx(domain)
        mx_ok = len(mx) > 0
        a_rec = has_a_record(domain) if not mx_ok else False

        smtp_result = 'blocked'
        smtp_detail = 'Skipped'

        if syntax and not disposable:
            if mx_ok:
                smtp_result, smtp_detail = smtp_check(email, mx)
            else:
                smtp_result = 'blocked'
                smtp_detail = 'No MX'

        score, status_val, reason = calc_score(
            email, syntax, disposable, role, mx_ok, a_rec, smtp_result, domain
        )

        results.append({
            "Email": email,
            "Status": status_val,
            "Score": score,
            "Reason": reason,
            "Details": f"MX:{len(mx)} | SMTP:{smtp_detail}",
        })

        progress.progress((i + 1) / len(valid_emails))
        status_text.text(f"Checking {email}...")

    progress.empty()
    status_text.empty()
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
            "Score": st.column_config.NumberColumn(),
            "Reason": st.column_config.TextColumn(width="medium"),
            "Details": st.column_config.TextColumn(width="small"),
        })

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name='results.csv', mime='text/csv')


if __name__ == "__main__":
    main()
