from flask import Flask, jsonify, request
import os
import smtplib
import secrets
import hashlib
from email.message import EmailMessage
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import urllib.error
import json as _json

app = Flask(__name__)

# ── CORS ──────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    origin = request.headers.get("Origin", "")
    allowed = [
        "https://mellymello.tg",
        "http://mellymello.tg",
        "https://www.mellymello.tg",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]
    if origin in allowed or not origin:
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, apikey"
    return response

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return jsonify({}), 200


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — Melly Mello Restaurant
# ══════════════════════════════════════════════════════════════════════════════

EMAIL_ADDRESS  = os.environ.get("EMAIL_ADDRESS",  "mellymello700@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "hroh xxmr lhkq mtbe")
ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "lazaregnahouame@gmail.com")

LOGO_URL      = "https://mellymello-seven.vercel.app/icon.png"
FRONTEND_URL  = "https://mellymello-seven.vercel.app"

# WhatsApp du restaurant (sans le +, sans espace)
WHATSAPP_NUMBER = "22893999667"
WHATSAPP_URL    = f"https://wa.me/{WHATSAPP_NUMBER}"

# Supabase — remplacez par vos propres clés
SUPABASE_URL         = os.environ.get("SUPABASE_URL",         "https://ggluplwglezpazpsrsyj.supabase.co")
SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY",    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdnbHVwbHdnbGV6cGF6cHNyc3lqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgyNTE4MzEsImV4cCI6MjA5MzgyNzgzMX0.u2J2OQ01TLrNBWvFbSAJmKees_-5jT4mOFS0M_8e0JQ")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdnbHVwbHdnbGV6cGF6cHNyc3lqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODI1MTgzMSwiZXhwIjoyMDkzODI3ODMxfQ.uF_HpxNtBQ0GdF3rqPxzk2_iy-WrO7cTdVfjm3HovuQ")

CRON_SECRET = os.environ.get("CRON_SECRET", "melly-mello-cron-2025")

_reset_tokens = {}
TOKEN_EXPIRE_MINUTES = 60


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS GÉNÉRIQUES
# ══════════════════════════════════════════════════════════════════════════════

def _generate_token(email):
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    _reset_tokens[token_hash] = {"email": email, "expires_at": expires_at}
    return token

def _verify_token(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    entry = _reset_tokens.get(token_hash)
    if not entry:
        return None
    if datetime.utcnow() > entry["expires_at"]:
        del _reset_tokens[token_hash]
        return None
    return entry["email"]

def _consume_token(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    entry = _reset_tokens.pop(token_hash, None)
    if not entry:
        return None
    if datetime.utcnow() > entry["expires_at"]:
        return None
    return entry["email"]


def _supabase_admin_request(method, path, data=None):
    url = f"{SUPABASE_URL}{path}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    body = _json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, _json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        try:
            return e.code, _json.loads(err_body) if err_body else {"msg": f"HTTP {e.code}"}
        except:
            return e.code, {"msg": err_body or f"HTTP {e.code}"}
    except Exception as e:
        return 500, {"msg": str(e)}


def _supabase_rest(method, table, query_params="", data=None):
    """Requête vers l'API REST Supabase (PostgREST)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if query_params:
        url += f"?{query_params}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    body = _json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return _json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"[Supabase REST] {method} {table} -> {e.code}: {err_body}")
        return []
    except Exception as e:
        print(f"[Supabase REST] Exception: {e}")
        return []


def _find_user_by_email(email):
    status, data = _supabase_admin_request("GET", "/auth/v1/admin/users?page=1&per_page=50")
    if status != 200:
        return None
    users_list = data.get("users", data) if isinstance(data, dict) else data
    if not isinstance(users_list, list):
        return None
    for user in users_list:
        if user.get("email", "").lower() == email.lower():
            return user
    return None


def _verify_cron_secret():
    auth = request.headers.get("Authorization", "")
    secret_param = request.args.get("secret", "")
    return auth == f"Bearer {CRON_SECRET}" or secret_param == CRON_SECRET


def _nice_date(date_str, time_str=""):
    """Formate une date en français : ex. 'vendredi 9 mai 2025 à 12:30'."""
    try:
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        mois  = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        result = f"{jours[d.weekday()]} {d.day} {mois[d.month]} {d.year}"
        if time_str:
            result += f" à {time_str[:5]}"
        return result
    except:
        return f"{date_str} {time_str}"


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE EMAIL — Melly Mello
# ══════════════════════════════════════════════════════════════════════════════

def get_html_template(title, content):
    """Template HTML universel aux couleurs de Melly Mello (doré + orange terracotta)."""
    return f"""
    <html>
    <body style="font-family:'Segoe UI',sans-serif;background-color:#faf8f4;padding:20px;color:#0d0d0d;margin:0;">
        <div style="max-width:600px;margin:0 auto;background:white;border-radius:20px;
                    box-shadow:0 10px 40px rgba(0,0,0,0.08);overflow:hidden;">

            <!-- En-tête -->
            <div style="background:linear-gradient(135deg,#0d0d0d 0%,#1a1204 100%);
                        padding:32px 30px;text-align:center;">
                <img src="{LOGO_URL}" alt="Melly Mello"
                     style="width:80px;height:80px;border-radius:50%;
                            border:3px solid #c9a84c;object-fit:cover;margin-bottom:14px;"
                     onerror="this.style.display='none'">
                <h1 style="color:#c9a84c;font-size:26px;margin:0 0 4px;
                           letter-spacing:2px;font-weight:800;">MELLY MELLO</h1>
                <p style="color:#e07c45;font-size:12px;margin:0;
                          letter-spacing:3px;text-transform:uppercase;">Restaurant Africain · Lomé</p>
            </div>

            <!-- Titre de la section -->
            <div style="background:linear-gradient(135deg,#c9a84c,#e07c45);
                        padding:16px 30px;text-align:center;">
                <h2 style="color:#0d0d0d;font-size:20px;margin:0;font-weight:700;">{title}</h2>
            </div>

            <!-- Contenu -->
            <div style="padding:30px;font-size:15px;line-height:1.7;color:#333;">
                {content}
            </div>

            <!-- Pied de page -->
            <div style="background:#f9f6f0;padding:20px 30px;text-align:center;
                        border-top:1px solid #f0ece4;">
                <p style="font-size:13px;color:#555;margin:0 0 8px;">
                    📍 Dabarakondji, non loin du Château d'eau, Lomé, Togo
                </p>
                <p style="font-size:13px;color:#555;margin:0 0 12px;">
                    📞 +228 93 99 96 67 &nbsp;|&nbsp;
                    <a href="{WHATSAPP_URL}" style="color:#25D366;text-decoration:none;font-weight:700;">
                        WhatsApp
                    </a>
                </p>
                <p style="font-size:11px;color:#aaa;margin:0;">
                    © {datetime.utcnow().year} Melly Mello — Saveurs africaines authentiques
                </p>
            </div>
        </div>
    </body>
    </html>"""


def _send_one_mail(to_email, subject, text_body, html_body):
    """Envoie un email via SMTP Gmail."""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From']    = f"Melly Mello Restaurant <{EMAIL_ADDRESS}>"
    msg['To']      = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype='html')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 0 — Config publique Supabase
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "supabase_url": SUPABASE_URL,
        "supabase_key": SUPABASE_ANON_KEY
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 1 — Emails déclenchés par une action utilisateur
# Types: signup, booking, admin_confirmation, cancellation,
#        direct_message, feedback_request, loyalty_milestone, promo_notification
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/index', methods=['POST'])
def send_email():
    data         = request.json or {}
    email_type   = data.get('type')
    client_name  = data.get('name', 'Client')
    client_email = data.get('email')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            def send_mail(to, subject, text, html):
                msg = EmailMessage()
                msg['Subject'] = subject
                msg['From']    = f"Melly Mello Restaurant <{EMAIL_ADDRESS}>"
                msg['To']      = to
                msg.set_content(text)
                msg.add_alternative(html, subtype='html')
                smtp.send_message(msg)

            # ── INSCRIPTION ────────────────────────────────────────────────
            if email_type == 'signup':
                text = (f"Bonjour {client_name},\n"
                        "Bienvenue chez Melly Mello ! 20 points de fidélité offerts.")
                html = get_html_template("Bienvenue chez Melly Mello ! 🎉", f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <p>Votre compte a été créé avec succès. Nous sommes ravis de vous accueillir dans la famille Melly Mello ! 🍽️</p>
                    <div style="background:linear-gradient(135deg,#0d0d0d,#1a1204);border-radius:16px;
                                padding:24px;text-align:center;margin:24px 0;">
                        <span style="font-size:40px;">🎁</span>
                        <p style="color:#c9a84c;font-weight:700;font-size:22px;margin:10px 0 4px;">
                            20 points de fidélité offerts
                        </p>
                        <p style="color:#999;font-size:13px;margin:0;">
                            150 points = 500 FCFA de réduction sur votre prochaine commande
                        </p>
                    </div>
                    <p style="text-align:center;">
                        <a href="{FRONTEND_URL}"
                           style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                                  color:white;text-decoration:none;font-weight:700;
                                  padding:14px 36px;border-radius:50px;font-size:15px;">
                            🍽️ Découvrir notre menu
                        </a>
                    </p>
                    <p style="text-align:center;margin-top:16px;">
                        <a href="{WHATSAPP_URL}"
                           style="display:inline-block;background:#25D366;color:white;
                                  text-decoration:none;font-weight:700;
                                  padding:12px 28px;border-radius:50px;font-size:14px;">
                            📱 Nous contacter sur WhatsApp
                        </a>
                    </p>""")
                send_mail(client_email,
                          "Bienvenue chez Melly Mello ! 🎉",
                          text, html)

            # ── NOUVELLE COMMANDE (confirmation au client) ─────────────────
            elif email_type == 'booking':
                service_name = data.get('service', '')
                nice_date    = data.get('nice_date', '')
                mode         = data.get('mode', 'Sur place')
                total        = data.get('total', '')

                text_c = (f"Bonjour {client_name},\n"
                          f"Votre commande de {service_name} pour le {nice_date} a bien été reçue.")

                html_c = get_html_template("Commande reçue ! ⏳", f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <p>Votre commande a bien été reçue et est <strong>en attente de confirmation</strong>.</p>
                    <div style="background:#f9f6f0;border:1px solid #e0d5c5;border-radius:14px;
                                padding:20px 24px;margin:20px 0;">
                        <table style="width:100%;border-collapse:collapse;">
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;width:40%;">🍴 Plat</td>
                                <td style="padding:8px 0;font-weight:700;">{service_name}</td>
                            </tr>
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;">📅 Date & heure</td>
                                <td style="padding:8px 0;font-weight:700;color:#c9a84c;">{nice_date}</td>
                            </tr>
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;">🏠 Mode</td>
                                <td style="padding:8px 0;font-weight:700;">{mode}</td>
                            </tr>
                            {f'<tr><td style="padding:8px 0;color:#888;font-size:13px;">💰 Total</td><td style="padding:8px 0;font-weight:700;color:#c9a84c;">{total} FCFA</td></tr>' if total else ''}
                        </table>
                    </div>
                    <div style="background:#fff8e7;border-left:4px solid #c9a84c;
                                border-radius:0 10px 10px 0;padding:14px 18px;margin:20px 0;">
                        ⏳ <em>Votre commande sera <strong>confirmée par le restaurant via WhatsApp</strong>.
                        Vous recevrez un message au +228 93 99 96 67.</em>
                    </div>
                    <p style="text-align:center;">
                        <a href="{WHATSAPP_URL}"
                           style="display:inline-block;background:#25D366;color:white;
                                  text-decoration:none;font-weight:700;
                                  padding:14px 32px;border-radius:50px;">
                            📱 Suivre sur WhatsApp
                        </a>
                    </p>""")

                send_mail(client_email,
                          f"Commande reçue — {service_name} ⏳",
                          text_c, html_c)

                # Notification admin
                html_a = get_html_template("🔴 Nouvelle Commande !", f"""
                    <p>Une nouvelle commande vient d'arriver :</p>
                    <div style="background:#f9f6f0;border-radius:14px;padding:20px 24px;margin:20px 0;">
                        <table style="width:100%;border-collapse:collapse;">
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;width:40%;">👤 Client</td>
                                <td style="padding:8px 0;font-weight:700;">{client_name}</td>
                            </tr>
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;">📧 Email</td>
                                <td style="padding:8px 0;">{client_email}</td>
                            </tr>
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;">🍴 Plat</td>
                                <td style="padding:8px 0;font-weight:700;">{service_name}</td>
                            </tr>
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;">📅 Date</td>
                                <td style="padding:8px 0;font-weight:700;color:#c9a84c;">{nice_date}</td>
                            </tr>
                            <tr style="border-bottom:1px solid #f0ece4;">
                                <td style="padding:8px 0;color:#888;font-size:13px;">🏠 Mode</td>
                                <td style="padding:8px 0;font-weight:700;">{mode}</td>
                            </tr>
                            {f'<tr><td style="padding:8px 0;color:#888;font-size:13px;">💰 Total</td><td style="padding:8px 0;font-weight:700;color:#c9a84c;">{total} FCFA</td></tr>' if total else ''}
                        </table>
                    </div>
                    <div style="text-align:center;">
                        <a href="{FRONTEND_URL}"
                           style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                                  color:white;text-decoration:none;font-weight:700;
                                  padding:12px 28px;border-radius:50px;">
                            🔧 Ouvrir l'admin
                        </a>
                    </div>""")

                send_mail(ADMIN_EMAIL,
                          f"🔴 NOUVELLE COMMANDE — {client_name} ({service_name})",
                          f"Nouvelle commande: {client_name} - {service_name} - {nice_date}",
                          html_a)

            # ── CONFIRMATION PAR L'ADMIN ───────────────────────────────────
            elif email_type == 'admin_confirmation':
                service_name = data.get('service', '')
                nice_date    = data.get('nice_date', '')
                mode         = data.get('mode', 'Sur place')

                html = get_html_template("Commande Confirmée ! ✅", f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <p>Votre commande a été <strong>confirmée</strong> par le restaurant. À tout à l'heure ! 🎉</p>
                    <div style="background:#f0faf4;border:2px solid #10b981;border-radius:16px;
                                padding:24px;text-align:center;margin:24px 0;">
                        <p style="font-size:40px;margin:0;">✅</p>
                        <p style="font-size:18px;font-weight:700;margin:10px 0 4px;">{service_name}</p>
                        <p style="font-size:16px;font-weight:700;color:#c9a84c;margin:0;">📅 {nice_date}</p>
                        <p style="font-size:14px;color:#555;margin:8px 0 0;">🏠 {mode}</p>
                    </div>
                    <div style="background:#fff8e7;border-left:4px solid #c9a84c;
                                border-radius:0 10px 10px 0;padding:14px 18px;margin:20px 0;">
                        <strong>À retenir :</strong><br>
                        📍 Dabarakondji, non loin du Château d'eau, Lomé<br>
                        📞 +228 93 99 96 67<br>
                        💳 Paiement sur place : Espèces, Flooz ou T-Money
                    </div>
                    <p style="text-align:center;">
                        <a href="{WHATSAPP_URL}"
                           style="display:inline-block;background:#25D366;color:white;
                                  text-decoration:none;font-weight:700;
                                  padding:14px 32px;border-radius:50px;">
                            📱 Contacter le restaurant
                        </a>
                    </p>""")

                send_mail(client_email,
                          f"✅ Commande confirmée — {service_name}",
                          f"Commande confirmée: {service_name} le {nice_date}",
                          html)

            # ── ANNULATION ─────────────────────────────────────────────────
            elif email_type == 'cancellation':
                service_name = data.get('service', '')
                nice_date    = data.get('nice_date', '')
                cancelled_by = data.get('cancelled_by', 'client')
                reason       = data.get('reason', '')

                if cancelled_by == 'admin':
                    title = "Commande annulée par le restaurant 😔"
                    intro = "Nous sommes désolés, votre commande a dû être annulée par notre équipe."
                    reason_html = f'<p style="margin-top:8px;"><strong>Raison :</strong> {reason}</p>' if reason else ''
                else:
                    title = "Annulation confirmée"
                    intro = "Votre commande a bien été annulée comme demandé."
                    reason_html = ""

                html = get_html_template(title, f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <p>{intro}</p>
                    <div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:14px;
                                padding:20px 24px;text-align:center;margin:20px 0;">
                        <p style="font-size:16px;font-weight:700;color:#7f1d1d;margin:0 0 6px;">
                            ❌ {service_name}
                        </p>
                        <p style="font-size:14px;color:#991b1b;margin:0;">{nice_date}</p>
                        {reason_html}
                    </div>
                    <p style="text-align:center;">
                        <a href="{FRONTEND_URL}"
                           style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                                  color:white;text-decoration:none;font-weight:700;
                                  padding:14px 36px;border-radius:50px;">
                            🍽️ Passer une nouvelle commande
                        </a>
                    </p>""")

                send_mail(client_email,
                          f"Commande annulée — {service_name}",
                          f"{intro} {service_name} {nice_date}",
                          html)

            # ── MESSAGE DIRECT ─────────────────────────────────────────────
            elif email_type == 'direct_message':
                subject = data.get('subject', "Message de Melly Mello")
                message = data.get('message', '')
                html = get_html_template(subject, f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <div style="background:#f9f6f0;border-radius:12px;padding:18px 20px;
                                margin:16px 0;border-left:4px solid #c9a84c;">
                        {message}
                    </div>
                    <p style="text-align:center;">
                        <a href="{WHATSAPP_URL}"
                           style="display:inline-block;background:#25D366;color:white;
                                  text-decoration:none;font-weight:700;
                                  padding:12px 28px;border-radius:50px;">
                            📱 Répondre sur WhatsApp
                        </a>
                    </p>""")
                send_mail(client_email,
                          subject,
                          f"Bonjour {client_name},\n\n{message}",
                          html)

            # ── DEMANDE D'AVIS APRÈS COMMANDE ──────────────────────────────
            elif email_type == 'feedback_request':
                service_name = data.get('service', '')
                nice_date    = data.get('nice_date', '')
                html = get_html_template("Comment était votre expérience ? ⭐", f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <p>Nous espérons que votre <strong>{service_name}</strong>
                       du <strong>{nice_date}</strong> vous a régalé ! 😋</p>
                    <div style="background:linear-gradient(135deg,#fff8e7,#fef3cd);
                                border:2px solid #c9a84c;border-radius:16px;
                                padding:24px;text-align:center;margin:20px 0;">
                        <p style="font-size:40px;margin:0;">⭐⭐⭐⭐⭐</p>
                        <p style="font-weight:700;color:#78350f;margin:8px 0 4px;">
                            Votre avis nous aide à nous améliorer !
                        </p>
                        <p style="font-size:13px;color:#555;margin:0;">
                            +25 points de fidélité pour chaque avis publié
                        </p>
                    </div>
                    <p style="text-align:center;">
                        <a href="{FRONTEND_URL}"
                           style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                                  color:white;text-decoration:none;font-weight:700;
                                  padding:14px 36px;border-radius:50px;">
                            ✍️ Laisser un avis
                        </a>
                    </p>""")
                send_mail(client_email,
                          f"Votre avis sur {service_name} ⭐ — Melly Mello",
                          f"Comment était votre {service_name} du {nice_date} ?",
                          html)

            # ── PALIER FIDÉLITÉ ATTEINT ────────────────────────────────────
            elif email_type == 'loyalty_milestone':
                new_tier = data.get('new_tier', 'Silver')
                points   = data.get('points', 0)
                reward   = data.get('reward', '')

                tier_styles = {
                    "Silver":  {"bg": "#f3f4f6", "border": "#9ca3af", "text": "#374151", "emoji": "🥈"},
                    "Gold":    {"bg": "#fffbeb", "border": "#f59e0b", "text": "#78350f", "emoji": "🏆"},
                    "Premium": {"bg": "#fdf4ff", "border": "#d8b4fe", "text": "#581c87", "emoji": "💎"},
                }
                tc = tier_styles.get(new_tier, tier_styles["Silver"])
                reward_html = (
                    f'<div style="background:#f0faf4;border-left:4px solid #10b981;'
                    f'border-radius:0 10px 10px 0;padding:14px 18px;margin:20px 0;">'
                    f'<strong>🎁 Votre récompense :</strong> {reward}</div>'
                ) if reward else ''

                html = get_html_template(f"Félicitations ! Vous êtes {new_tier} {tc['emoji']}", f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <p>Grâce à votre fidélité, vous avez atteint un nouveau palier !</p>
                    <div style="background:{tc['bg']};border:2px solid {tc['border']};
                                border-radius:16px;padding:28px;text-align:center;margin:24px 0;">
                        <p style="font-size:50px;margin:0;">{tc['emoji']}</p>
                        <p style="font-size:28px;font-weight:700;color:{tc['text']};margin:10px 0 4px;">
                            {new_tier}
                        </p>
                        <p style="font-size:14px;color:{tc['text']};margin:0;">
                            {points} points accumulés
                        </p>
                    </div>
                    {reward_html}
                    <p style="text-align:center;">
                        <a href="{FRONTEND_URL}"
                           style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                                  color:white;text-decoration:none;font-weight:700;
                                  padding:14px 36px;border-radius:50px;">
                            👑 Mon espace fidélité
                        </a>
                    </p>""")

                send_mail(client_email,
                          f"Félicitations ! Niveau {new_tier} atteint {tc['emoji']}",
                          f"Vous êtes {new_tier} avec {points} points !",
                          html)

            # ── CODE PROMO ─────────────────────────────────────────────────
            elif email_type == 'promo_notification':
                promo_code    = data.get('promo_code', '')
                discount      = data.get('discount', '')
                discount_type = data.get('discount_type', 'percentage')
                description   = data.get('description', '')
                valid_until   = data.get('valid_until', '')
                disc_display  = f"{discount}{'%' if discount_type == 'percentage' else ' FCFA'}"
                valid_html    = (
                    f'<p style="color:#999;font-size:12px;text-align:center;">'
                    f'⏱️ Valable jusqu\'au <strong>{valid_until}</strong></p>'
                ) if valid_until else ''

                html = get_html_template("Offre Exclusive pour vous ! 🎁", f"""
                    <p>Bonjour <strong>{client_name}</strong>,</p>
                    <p>Nous avons une offre spéciale rien que pour vous :</p>
                    <div style="background:linear-gradient(135deg,#0d0d0d,#1a1204);
                                border-radius:16px;padding:32px;text-align:center;margin:24px 0;">
                        <p style="color:#c9a84c;font-size:13px;letter-spacing:3px;
                                  text-transform:uppercase;margin:0 0 8px;">Code Promo</p>
                        <p style="color:white;font-size:34px;font-weight:700;
                                  letter-spacing:6px;margin:0 0 12px;font-family:monospace;">
                            {promo_code}
                        </p>
                        <p style="color:#e07c45;font-size:44px;font-weight:700;margin:0;">
                            -{disc_display}
                        </p>
                        <p style="color:#999;font-size:13px;margin:10px 0 0;">{description}</p>
                    </div>
                    {valid_html}
                    <p style="text-align:center;">
                        <a href="{FRONTEND_URL}"
                           style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                                  color:white;text-decoration:none;font-weight:700;
                                  padding:14px 36px;border-radius:50px;">
                            🍽️ Commander maintenant
                        </a>
                    </p>""")

                send_mail(client_email,
                          f"🎁 -{disc_display} avec le code {promo_code} — Melly Mello",
                          f"Code promo: {promo_code} = -{disc_display}",
                          html)

            else:
                return jsonify({"error": f"Type inconnu : '{email_type}'"}), 400

        return jsonify({"status": "Email envoyé !"}), 200

    except Exception as e:
        print(f"Erreur email [{email_type}] : {e}")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES — Réinitialisation mot de passe
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data  = request.json or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({"error": "Email requis"}), 400

    token      = _generate_token(email)
    reset_link = f"{FRONTEND_URL}?page=reset&token={token}"
    name       = email.split('@')[0].capitalize()

    try:
        html = get_html_template("Réinitialisation mot de passe 🔐", f"""
            <p>Bonjour <strong>{name}</strong>,</p>
            <p>Cliquez sur le bouton ci-dessous pour réinitialiser votre mot de passe :</p>
            <div style="text-align:center;margin:30px 0;">
                <a href="{reset_link}"
                   style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                          color:white;text-decoration:none;font-weight:700;
                          font-size:16px;padding:16px 40px;border-radius:50px;">
                    🔐 Réinitialiser mon mot de passe
                </a>
            </div>
            <p style="color:#888;font-size:13px;text-align:center;">
                ⏱️ Ce lien est valable <strong>1 heure</strong>.<br>
                Ignorez cet email si vous n'êtes pas à l'origine de cette demande.
            </p>""")
        _send_one_mail(email,
                       "🔐 Réinitialisation mot de passe — Melly Mello",
                       f"Lien de réinitialisation : {reset_link}",
                       html)
    except Exception as e:
        print(f"Erreur email reset : {e}")

    return jsonify({
        "success": True,
        "message": "Si cet email est enregistré, un lien de réinitialisation a été envoyé."
    }), 200


@app.route('/api/auth/verify-reset-token', methods=['GET'])
def verify_reset_token():
    token = request.args.get('token', '')
    email = _verify_token(token)
    if not email:
        return jsonify({"valid": False, "detail": "Lien expiré ou invalide."}), 400
    return jsonify({"valid": True, "email": email}), 200


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data         = request.json or {}
    token        = data.get('token', '')
    new_password = data.get('new_password', '')

    if len(new_password) < 6:
        return jsonify({"detail": "Mot de passe trop court (minimum 6 caractères)"}), 400

    email = _consume_token(token)
    if not email:
        return jsonify({"detail": "Lien expiré ou invalide."}), 400

    try:
        user = _find_user_by_email(email)
        if not user:
            return jsonify({"detail": f"Aucun compte trouvé pour {email}."}), 404

        status, resp = _supabase_admin_request(
            "PUT",
            f"/auth/v1/admin/users/{user['id']}",
            {"password": new_password}
        )
        if status < 200 or status >= 300:
            return jsonify({"detail": f"Erreur Supabase : {resp.get('msg', '')}"}), 500

        return jsonify({"success": True, "message": "Mot de passe mis à jour avec succès."}), 200

    except Exception as e:
        return jsonify({"detail": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# CRON ENDPOINTS — Automatisations (appelés par Vercel Cron / un scheduler)
# Protégés par CRON_SECRET dans le header Authorization
# ══════════════════════════════════════════════════════════════════════════════

# ── CRON 1 : Rappels 24h et 2h avant une réservation (toutes les heures) ─────
@app.route('/api/cron/reminders', methods=['GET'])
def cron_reminders():
    if not _verify_cron_secret():
        return jsonify({"error": "Unauthorized"}), 401

    now           = datetime.utcnow()
    today         = now.strftime("%Y-%m-%d")
    after_tomorrow = (now + timedelta(days=2)).strftime("%Y-%m-%d")

    appts = _supabase_rest(
        "GET", "appointments",
        f"status=eq.confirmed&date=gte.{today}&date=lte.{after_tomorrow}&select=*"
    )
    sent_24h, sent_2h = 0, 0

    for apt in appts:
        try:
            apt_dt = datetime.strptime(f"{apt['date']}T{apt['time'][:5]}", "%Y-%m-%dT%H:%M")
            diff_h = (apt_dt - now).total_seconds() / 3600
            nice   = _nice_date(apt['date'], apt.get('time', ''))
            cn     = apt.get('client_name', '')
            sn     = apt.get('service_name', '')
            ce     = apt.get('client_email', '')
            mode   = apt.get('preferences', {}).get('movie', 'Sur place') if apt.get('preferences') else 'Sur place'

            # Rappel 24h (entre 23h et 25h avant)
            if 23 <= diff_h <= 25 and not apt.get('reminder_24h_sent'):
                html = get_html_template("Rappel : Votre commande est demain ! 📅", f"""
                    <p>Bonjour <strong>{cn}</strong>,</p>
                    <p>Votre commande est prévue pour <strong>demain</strong> chez Melly Mello !</p>
                    <div style="background:linear-gradient(135deg,#fff8e7,#fef3cd);
                                border:2px solid #c9a84c;border-radius:16px;
                                padding:24px;text-align:center;margin:20px 0;">
                        <p style="font-size:20px;font-weight:700;margin:0 0 6px;">{sn}</p>
                        <p style="font-size:22px;font-weight:700;color:#c9a84c;margin:0;">
                            📅 {nice}
                        </p>
                        <p style="font-size:14px;color:#555;margin:8px 0 0;">🏠 {mode}</p>
                    </div>
                    <div style="background:#f0faf4;border-left:4px solid #10b981;
                                border-radius:0 10px 10px 0;padding:14px 18px;margin:20px 0;">
                        <strong>Rappel :</strong><br>
                        📍 Dabarakondji, non loin du Château d'eau, Lomé<br>
                        💳 Paiement sur place : Espèces, Flooz, T-Money
                    </div>""")
                _send_one_mail(ce,
                               f"📅 Rappel : Commande demain — Melly Mello",
                               f"Rappel: {sn} le {nice}",
                               html)
                _supabase_rest("PATCH", "appointments",
                               f"id=eq.{apt['id']}", {"reminder_24h_sent": True})
                sent_24h += 1

            # Rappel 2h (entre 1h30 et 2h30 avant)
            elif 1.5 <= diff_h <= 2.5 and not apt.get('reminder_2h_sent'):
                html = get_html_template("C'est bientôt ! ⏰", f"""
                    <p>Bonjour <strong>{cn}</strong>,</p>
                    <p>Votre commande est dans <strong>environ 2 heures</strong> !</p>
                    <div style="background:linear-gradient(135deg,#e07c45,#c06a35);
                                border-radius:16px;padding:24px;text-align:center;margin:20px 0;">
                        <p style="font-size:18px;font-weight:700;color:white;margin:0 0 6px;">
                            {sn}
                        </p>
                        <p style="font-size:22px;font-weight:700;color:white;margin:0;">
                            ⏰ {apt.get('time', '')[:5]}
                        </p>
                    </div>
                    <p>📍 Dabarakondji, non loin du Château d'eau, Lomé</p>
                    <p>📞 +228 93 99 96 67</p>""")
                _send_one_mail(ce,
                               f"⏰ Commande dans 2h — Melly Mello",
                               f"Rappel: {sn} à {apt.get('time', '')[:5]}",
                               html)
                _supabase_rest("PATCH", "appointments",
                               f"id=eq.{apt['id']}", {"reminder_2h_sent": True})
                sent_2h += 1

        except Exception as e:
            print(f"[cron_reminders] Error: {e}")

    return jsonify({"sent_24h": sent_24h, "sent_2h": sent_2h}), 200


# ── CRON 2 : Demande d'avis après commande (chaque jour à 20h) ───────────────
@app.route('/api/cron/feedback-requests', methods=['GET'])
def cron_feedback_requests():
    if not _verify_cron_secret():
        return jsonify({"error": "Unauthorized"}), 401

    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    today     = datetime.utcnow().strftime("%Y-%m-%d")

    appts = _supabase_rest(
        "GET", "appointments",
        f"status=eq.completed&date=gte.{yesterday}&date=lte.{today}"
        f"&feedback_sent=is.null&select=*"
    )
    sent = 0

    for apt in appts:
        try:
            nice = _nice_date(apt['date'], apt.get('time', ''))
            html = get_html_template("Votre avis compte ! ⭐", f"""
                <p>Bonjour <strong>{apt.get('client_name', '')}</strong>,</p>
                <p>Comment s'est passée votre commande de
                   <strong>{apt.get('service_name', '')}</strong>
                   du <strong>{nice}</strong> ? 😋</p>
                <div style="background:linear-gradient(135deg,#fff8e7,#fef3cd);
                            border:2px solid #c9a84c;border-radius:16px;
                            padding:24px;text-align:center;margin:20px 0;">
                    <p style="font-size:40px;margin:0;">⭐⭐⭐⭐⭐</p>
                    <p style="font-weight:700;color:#78350f;margin:8px 0 4px;">
                        +25 points de fidélité pour chaque avis !
                    </p>
                </div>
                <p style="text-align:center;">
                    <a href="{FRONTEND_URL}"
                       style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                              color:white;text-decoration:none;font-weight:700;
                              padding:14px 36px;border-radius:50px;">
                        ✍️ Laisser un avis
                    </a>
                </p>""")
            _send_one_mail(apt['client_email'],
                           f"Votre avis sur votre commande ⭐ — Melly Mello",
                           f"Donnez votre avis sur {apt.get('service_name', '')}",
                           html)
            _supabase_rest("PATCH", "appointments",
                           f"id=eq.{apt['id']}", {"feedback_sent": True})
            sent += 1
        except Exception as e:
            print(f"[cron_feedback] Error: {e}")

    return jsonify({"sent": sent}), 200


# ── CRON 3 : Récap hebdomadaire admin (chaque lundi à 8h) ────────────────────
@app.route('/api/cron/weekly-recap', methods=['GET'])
def cron_weekly_recap():
    if not _verify_cron_secret():
        return jsonify({"error": "Unauthorized"}), 401

    now        = datetime.utcnow()
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = now.strftime("%Y-%m-%d")
    next_week  = (now + timedelta(days=7)).strftime("%Y-%m-%d")

    past      = _supabase_rest("GET", "appointments",
                               f"date=gte.{week_start}&date=lt.{week_end}&select=*")
    upcoming  = _supabase_rest("GET", "appointments",
                               f"date=gte.{week_end}&date=lt.{next_week}"
                               f"&status=eq.confirmed&select=*")
    new_users = _supabase_rest("GET", "users",
                               f"created_at=gte.{week_start}T00:00:00&role=eq.client&select=id")

    completed = [a for a in past if a.get('status') == 'completed']
    cancelled = [a for a in past if a.get('status') == 'cancelled']
    pending   = [a for a in past if a.get('status') == 'pending']
    revenue   = sum(
        float(a.get('total_price', 0) or a.get('price', 0) or 0)
        for a in completed
    )

    rows = "".join(
        f'<tr style="border-bottom:1px solid #f0f0f0;">'
        f'<td style="padding:8px 12px;font-size:13px;">{a.get("client_name","?")}</td>'
        f'<td style="padding:8px 12px;font-size:13px;">{a.get("service_name","?")}</td>'
        f'<td style="padding:8px 12px;font-size:13px;color:#c9a84c;font-weight:700;">'
        f'{_nice_date(a["date"], a.get("time",""))}</td></tr>'
        for a in upcoming[:10]
    )

    pending_alert = (
        f'<div style="background:#fff8e7;border-left:4px solid #f59e0b;'
        f'border-radius:0 10px 10px 0;padding:12px 16px;margin:16px 0;">'
        f'<strong>⚠️ {len(pending)} commande(s) en attente</strong> de confirmation !</div>'
    ) if pending else ''

    table_html = (
        f'<table style="width:100%;border-collapse:collapse;border:1px solid #eee;">'
        f'<thead><tr style="background:#f9f9f9;">'
        f'<th style="padding:8px 12px;text-align:left;font-size:12px;color:#999;">Client</th>'
        f'<th style="padding:8px 12px;text-align:left;font-size:12px;color:#999;">Plat</th>'
        f'<th style="padding:8px 12px;text-align:left;font-size:12px;color:#999;">Date</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
    ) if rows else '<p style="color:#999;">Aucune commande confirmée à venir.</p>'

    html = get_html_template("📊 Récap Hebdomadaire", f"""
        <p>Voici le résumé de la semaine pour <strong>Melly Mello</strong> :</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0;"><tr>
            <td style="background:#f0faf4;border-radius:12px;padding:16px;text-align:center;width:25%;">
                <div style="font-size:28px;font-weight:700;color:#064e3b;">✅ {len(completed)}</div>
                <div style="font-size:12px;color:#555;">Terminées</div>
            </td>
            <td style="background:#fee2e2;border-radius:12px;padding:16px;text-align:center;width:25%;">
                <div style="font-size:28px;font-weight:700;color:#7f1d1d;">❌ {len(cancelled)}</div>
                <div style="font-size:12px;color:#555;">Annulées</div>
            </td>
            <td style="background:#fffbeb;border-radius:12px;padding:16px;text-align:center;width:25%;">
                <div style="font-size:22px;font-weight:700;color:#78350f;">
                    💰 {revenue:.0f} F
                </div>
                <div style="font-size:12px;color:#555;">CA (FCFA)</div>
            </td>
            <td style="background:#ede9fe;border-radius:12px;padding:16px;text-align:center;width:25%;">
                <div style="font-size:28px;font-weight:700;color:#3730a3;">👤 {len(new_users)}</div>
                <div style="font-size:12px;color:#555;">Nouveaux</div>
            </td>
        </tr></table>
        {pending_alert}
        <h3 style="color:#c9a84c;font-size:16px;margin:24px 0 12px;">
            📅 Prochaines commandes ({len(upcoming)})
        </h3>
        {table_html}
        <div style="text-align:center;margin:24px 0;">
            <a href="{FRONTEND_URL}"
               style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                      color:white;text-decoration:none;font-weight:700;
                      padding:12px 32px;border-radius:50px;">
                🔧 Ouvrir le panel admin
            </a>
        </div>""")

    _send_one_mail(ADMIN_EMAIL,
                   f"📊 Récap semaine — Melly Mello",
                   f"Semaine: {len(completed)} terminées, {revenue:.0f} FCFA CA",
                   html)

    return jsonify({
        "completed": len(completed),
        "cancelled": len(cancelled),
        "revenue":   revenue,
        "new_clients": len(new_users)
    }), 200


# ── CRON 4 : Relance clients inactifs (1er du mois) ──────────────────────────
@app.route('/api/cron/inactive-clients', methods=['GET'])
def cron_inactive_clients():
    if not _verify_cron_secret():
        return jsonify({"error": "Unauthorized"}), 401

    cutoff      = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d")
    all_clients = _supabase_rest(
        "GET", "users",
        "role=eq.client&select=id,name,email,last_visit,created_at"
    )
    sent = 0

    for cl in all_clients:
        try:
            last = cl.get('last_visit') or cl.get('created_at', '')
            if last and last[:10] < cutoff:
                name = cl.get('name', 'Cher client')
                html = get_html_template("Vous nous manquez ! 🍽️", f"""
                    <p>Bonjour <strong>{name}</strong>,</p>
                    <p>Cela fait un moment que nous ne vous avons pas vu(e) chez Melly Mello… 😢</p>
                    <div style="background:linear-gradient(135deg,#0d0d0d,#1a1204);
                                border-radius:16px;padding:28px;text-align:center;margin:20px 0;">
                        <p style="font-size:44px;margin:0;">🍽️</p>
                        <p style="font-weight:700;color:#c9a84c;font-size:20px;margin:10px 0 4px;">
                            -10% sur votre prochaine commande
                        </p>
                        <p style="font-size:13px;color:#999;margin:0;">
                            Rien que pour vous, notre client fidèle !
                        </p>
                    </div>
                    <p style="text-align:center;">
                        <a href="{FRONTEND_URL}"
                           style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8893a);
                                  color:white;text-decoration:none;font-weight:700;
                                  padding:14px 36px;border-radius:50px;">
                            🍴 Commander maintenant
                        </a>
                    </p>
                    <p style="text-align:center;margin-top:12px;">
                        <a href="{WHATSAPP_URL}"
                           style="display:inline-block;background:#25D366;color:white;
                                  text-decoration:none;font-weight:700;
                                  padding:12px 28px;border-radius:50px;">
                            📱 Nous contacter sur WhatsApp
                        </a>
                    </p>
                    <p style="color:#999;font-size:12px;text-align:center;margin-top:16px;">
                        Vos points de fidélité vous attendent ! ✨
                    </p>""")
                _send_one_mail(cl['email'],
                               f"Vous nous manquez, {name.split(' ')[0]} ! 🍽️",
                               "Revenez commander chez Melly Mello avec -10%",
                               html)
                sent += 1
                if sent >= 50:
                    break
        except Exception as e:
            print(f"[cron_inactive] Error: {e}")

    return jsonify({"sent": sent}), 200


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE LOCAL
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app.run(debug=True, port=5000)
