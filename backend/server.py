from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, desc
from sqlalchemy.orm import selectinload
import os
import logging
import re
import asyncio
import uuid
import bcrypt
import jwt
import resend
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from groq import AsyncGroq
import httpx

# Import database and models
from database import get_db, engine, Base
from models import User, ChildProfile, Conversation, Message, Alert, BrowsingPacket

# LLM
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
EMERGENT_LLM_KEY = GROQ_API_KEY # Kept for variable compatibility
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

class UserMessage:
    def __init__(self, text: str):
        self.text = text

class LlmChat:
    def __init__(self, api_key: str, session_id: str, system_message: str):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.model = "llama3-8b-8192"
        self.history = [{"role": "system", "content": self.system_message}]

    def with_model(self, provider: str, model: str):
        if "mini" in model:
            self.model = "llama3-8b-8192"
        else:
            self.model = "llama3-70b-8192"
        return self

    async def send_message(self, message: UserMessage) -> str:
        if not groq_client:
            raise Exception("GROQ_API_KEY is missing or invalid.")
        self.history.append({"role": "user", "content": message.text})
        response = await groq_client.chat.completions.create(
            messages=self.history,
            model=self.model,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        self.history.append({"role": "assistant", "content": content})
        return content

# JWT
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"

# Resend
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
if RESEND_API_KEY and RESEND_API_KEY != 're_placeholder_key':
    resend.api_key = RESEND_API_KEY

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# PASSWORD HASHING
# ============================================================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ============================================================
# JWT TOKENS
# ============================================================
def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=24), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Get current authenticated user from JWT token."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        result = await db.execute(select(User).where(User.id == payload["sub"]))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ============================================================
# PYDANTIC MODELS
# ============================================================
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class VerifyPasswordRequest(BaseModel):
    password: str

class GoogleSessionRequest(BaseModel):
    session_id: str

class ChildProfileCreate(BaseModel):
    name: str
    age: Optional[int] = None

class MessageCreate(BaseModel):
    conversation_id: Optional[str] = None
    text: str
    device_id: Optional[str] = None
    child_id: Optional[str] = None

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Chat"

class BrowsingPacketModel(BaseModel):
    id: str
    timestamp: str
    device_id: str
    tab_type: str = "normal"
    url: str
    domain: str
    title: Optional[str] = ""
    packet_type: str
    search_query: Optional[str] = None
    search_engine: Optional[str] = None

class PacketBatch(BaseModel):
    device_id: str
    packets: List[BrowsingPacketModel]


class QuizAnswerRequest(BaseModel):
    conversation_id: str
    question_index: int
    answer: str  # A, B, C, or D


class StoryChoiceRequest(BaseModel):
    conversation_id: str
    choice_index: int  # 1, 2, or 3


class WebSearchRequest(BaseModel):
    conversation_id: Optional[str] = None
    query: str
    url: Optional[str] = None  # Optional URL to summarize


# ============================================================
# EMAIL ALERTS
# ============================================================
async def send_alert_email(parent_email: str, parent_name: str, alert_type: str, details: str, child_message: str, severity: str):
    """Send safety alert email to parent."""
    if not RESEND_API_KEY or RESEND_API_KEY == 're_placeholder_key':
        logger.info(f"[EMAIL ALERT SKIPPED - No API Key] To: {parent_email}, Type: {alert_type}, Details: {details}")
        return

    severity_color = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}.get(severity, "#f59e0b")
    severity_bg = {"high": "#fef2f2", "medium": "#fffbeb", "low": "#f0fdf4"}.get(severity, "#fffbeb")

    html = f"""
    <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
      <div style="background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div style="background: linear-gradient(135deg, #38bdf8, #34d399); padding: 24px; text-align: center;">
          <h1 style="color: white; margin: 0; font-size: 24px;">BuddyBot Safety Alert</h1>
        </div>
        <div style="padding: 24px;">
          <p style="font-size: 16px; color: #334155;">Hi {parent_name},</p>
          <div style="background: {severity_bg}; border-left: 4px solid {severity_color}; padding: 16px; border-radius: 8px; margin: 16px 0;">
            <p style="margin: 0 0 8px 0; font-weight: bold; color: {severity_color}; text-transform: uppercase; font-size: 12px; letter-spacing: 1px;">{severity} Severity - {alert_type.replace('_', ' ').title()}</p>
            <p style="margin: 0; color: #475569; font-size: 14px;">{details}</p>
          </div>
          <div style="background: #f1f5f9; padding: 12px 16px; border-radius: 8px; margin: 16px 0;">
            <p style="margin: 0; color: #64748b; font-size: 13px;">Child's message/search:</p>
            <p style="margin: 4px 0 0 0; color: #1e293b; font-size: 15px; font-style: italic;">"{child_message}"</p>
          </div>
          <p style="font-size: 14px; color: #64748b;">Please review this activity in your <strong>Parent Dashboard</strong>.</p>
        </div>
        <div style="background: #f8fafc; padding: 16px; text-align: center; border-top: 1px solid #e2e8f0;">
          <p style="margin: 0; color: #94a3b8; font-size: 12px;">BuddyBot - Keeping kids safe online</p>
        </div>
      </div>
    </div>
    """

    params = {
        "from": SENDER_EMAIL,
        "to": [parent_email],
        "subject": f"[BuddyBot Alert] {severity.upper()} - {alert_type.replace('_', ' ').title()}",
        "html": html
    }

    try:
        email_result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Alert email sent to {parent_email}: {email_result}")
    except Exception as e:
        logger.error(f"Failed to send alert email to {parent_email}: {e}")


async def notify_parent_of_alert(db: AsyncSession, alert_data: dict, child_id: str = None):
    """Find the parent and send them an alert email."""
    parent = None
    if child_id:
        result = await db.execute(select(ChildProfile).where(ChildProfile.id == child_id))
        child = result.scalar_one_or_none()
        if child:
            result = await db.execute(select(User).where(User.id == child.parent_id))
            parent = result.scalar_one_or_none()
    if not parent:
        # Try to find any parent (single-parent setup)
        result = await db.execute(select(User).limit(1))
        parent = result.scalar_one_or_none()
    if parent and parent.email:
        await send_alert_email(
            parent_email=parent.email,
            parent_name=parent.name or "Parent",
            alert_type=alert_data.get("type", "safety_alert"),
            details=alert_data.get("details", ""),
            child_message=alert_data.get("child_message", ""),
            severity=alert_data.get("severity", "medium")
        )


# ============================================================
# EXACT MATCH BLOCKED KEYWORDS (HIGH PRIORITY - STRICT FILTER)
# ============================================================
# These words trigger IMMEDIATE blocking with exact match only (no fuzzy matching)
EXACT_MATCH_BLOCKED = [
    # Most severe profanity
    "fuck", "fucking", "fucker", "shit", "shitting", "cunt", "cock", "dick",
    "pussy", "bitch", "nigger", "nigga", "faggot", "whore", "slut",
    # Severe violence
    "kill", "murder", "suicide", "rape", "molest", "pedophile",
    # Drug references
    "cocaine", "heroin", "meth", "crack",
    # Adult content
    "porn", "pornography", "xxx", "nude", "naked"
]

def check_exact_match_blocked(text: str) -> dict:
    """
    Check for exact match of high-priority blocked words.
    Returns immediately if any match found - no fuzzy matching.
    """
    text_lower = text.lower()
    # Split into words
    words = re.findall(r'\b[a-zA-Z]+\b', text_lower)
    matched = []
    
    for word in words:
        if word in EXACT_MATCH_BLOCKED:
            matched.append(word)
    
    return {
        "is_blocked": len(matched) > 0,
        "matched_words": matched,
        "match_type": "exact"
    }


# ============================================================
# PROFANITY / SAFETY FILTER WITH FUZZY MATCHING
# ============================================================

# Comprehensive blocked words list - organized by category
BLOCKED_WORDS_BY_CATEGORY = {
    "profanity": [
        "fuck", "shit", "ass", "asshole", "bitch", "bastard", "damn", "crap",
        "dick", "cock", "pussy", "cunt", "twat", "prick", "bollocks", "wanker",
        "slut", "whore", "hoe", "skank", "tramp", "fag", "faggot", "dyke",
        "retard", "retarded", "spaz", "moron", "imbecile",
        "piss", "pissed", "bloody", "bugger", "arse", "arsehole", "tosser",
        "douchebag", "douche", "jackass", "dipshit", "shithead", "asshat",
        "motherfucker", "fucker", "bullshit", "horseshit", "goddam", "goddamn",
        "damnit", "screwed", "wtf", "stfu", "omfg", "fml"
    ],
    "violence": [
        "gun", "rifle", "pistol", "shotgun", "firearm", "weapon", "knife",
        "blade", "machete", "axe", "bomb", "explosive", "grenade",
        "missile", "bullet", "ammo", "ammunition", "trigger", "caliber",
        "kill", "murder", "assassinate", "slaughter", "massacre", "execute",
        "shoot", "stab", "slash", "strangle", "choke", "suffocate", "drown",
        "beat", "punch", "kick", "attack", "assault", "hurt", "harm", "injure",
        "torture", "mutilate", "dismember", "decapitate", "behead", "hang",
        "die", "death", "dead", "blood", "bleed", "bleeding", "gore", "gory",
        "corpse", "body", "homicide", "genocide",
        "threat", "threaten", "revenge", "avenge", "destroy", "annihilate",
        "eliminate", "exterminate", "obliterate", "demolish"
    ],
    "adult_content": [
        "sex", "sexual", "sexy", "porn", "porno", "pornography", "xxx",
        "nude", "naked", "nudity", "strip", "stripper", "striptease",
        "erotic", "erotica", "fetish", "kink", "kinky", "bdsm", "bondage",
        "orgasm", "orgasmic", "climax", "horny", "aroused", "arousal",
        "masturbate", "masturbation", "jerk", "wank", "fap",
        "penis", "vagina", "boob", "boobs", "breast", "breasts", "tit", "tits",
        "butt", "buttocks", "genitals", "genital", "testicle", "testicles",
        "intercourse", "fornicate", "fornication", "copulate", "copulation",
        "blowjob", "handjob", "fingering", "oral", "anal",
        "escort", "prostitute", "prostitution", "hooker", "brothel",
        "onlyfans", "camgirl", "webcam", "livecam", "chaturbate",
        "hookup", "onenight", "fwb", "nudes", "sext", "sexting"
    ],
    "substances": [
        "drug", "drugs", "cocaine", "coke", "crack", "heroin", "meth",
        "methamphetamine", "amphetamine", "ecstasy", "mdma", "molly",
        "lsd", "acid", "shrooms", "mushrooms", "psilocybin", "dmt",
        "ketamine", "pcp", "fentanyl", "opium", "opioid",
        "morphine", "codeine", "oxycodone", "hydrocodone", "percocet",
        "xanax", "adderall", "ritalin", "valium", "barbiturate",
        "weed", "marijuana", "cannabis", "pot", "joint", "blunt", "bong",
        "edible", "thc", "cbd", "stoner", "420",
        "alcohol", "beer", "wine", "vodka", "whiskey", "whisky", "rum",
        "tequila", "gin", "brandy", "bourbon", "scotch", "liquor", "booze",
        "drunk", "wasted", "hammered", "plastered", "intoxicated", "tipsy",
        "hangover", "binge", "binging", "chug", "shots",
        "cigarette", "cigar", "tobacco", "nicotine", "smoke", "smoking",
        "vape", "vaping", "juul",
        "high", "stoned", "tripping", "overdose", "inject", "snort", "dealer"
    ],
    "self_harm": [
        "suicide", "suicidal", "kill myself", "end my life", "end it all",
        "want to die", "wanna die", "wish i was dead", "better off dead",
        "cut myself", "cutting", "self harm", "selfharm", "self-harm",
        "hurt myself", "hurting myself", "harm myself", "harming myself",
        "slit wrist", "slit wrists", "hang myself", "hanging myself",
        "overdose", "take pills", "jump off", "jump from",
        "worthless", "hopeless", "no reason to live", "nobody cares",
        "everyone hates me", "no point", "give up", "giving up",
        "cant go on", "can't go on", "dont want to live", "don't want to live",
        "life is pointless", "meaningless", "empty inside"
    ],
    "cyberbullying": [
        "loser", "ugly", "freak", "weirdo", "nerd", "geek",
        "dork", "lame", "pathetic", "worthless", "useless",
        "idiot", "moron", "imbecile", "creep", "creepy", "gross", "disgusting",
        "nobody likes you", "no friends", "unfriend", "blocked", "ignored",
        "go away", "leave me alone", "unwanted", "rejected", "outcast",
        "gonna get you", "watch out", "you'll regret", "you're dead",
        "gonna beat", "gonna hurt", "i'll find you", "tell everyone",
        "spread rumors", "embarrass you", "expose you", "leak your",
        "harass", "harassment", "bully", "bullying", "stalk", "stalking",
        "troll", "trolling", "spam", "spamming", "doxx", "doxxing",
        "catfish", "catfishing", "ghosting", "cancel", "cancelled"
    ],
    "hate_speech": [
        "racist", "racism", "racial", "negro", "nigga", "nigger", "cracker",
        "wetback", "beaner", "chink", "gook", "jap", "spic", "kike",
        "islamophobe", "antisemite", "antisemitic", "christophobe",
        "homophobe", "homophobic", "transphobe", "transphobic",
        "fag", "faggot", "dyke", "tranny", "shemale",
        "hate", "hater", "hating", "despise", "detest", "loathe",
        "supremacist", "supremacy", "nazi", "hitler", "fascist",
        "bigot", "bigotry", "prejudice", "discriminate", "discrimination",
        "xenophobe", "xenophobic", "misogynist", "misogyny",
        "retard", "retarded", "cripple", "handicapped", "midget"
    ],
    "dangerous_activities": [
        "challenge", "dare", "choking game", "blackout challenge",
        "tide pod", "cinnamon challenge", "salt and ice", "fire challenge",
        "hack", "hacking", "hacker", "exploit", "pirate", "piracy",
        "steal", "stealing", "theft", "rob", "robbing", "burglary",
        "shoplift", "shoplifting", "vandal", "vandalism", "graffiti",
        "terrorist", "terrorism", "terror", "jihad", "isis", "al qaeda",
        "bomb threat", "mass shooting", "shooting", "hostage",
        "predator", "grooming", "molest", "pedophile", "pedo", "kidnap"
    ]
}

BLOCKED_WORDS = []
for category_words in BLOCKED_WORDS_BY_CATEGORY.values():
    BLOCKED_WORDS.extend(category_words)
BLOCKED_WORDS = list(set(BLOCKED_WORDS))

RESTRICTED_TOPICS = {
    "violence": BLOCKED_WORDS_BY_CATEGORY["violence"],
    "privacy": [
        "address", "phone number", "credit card", "password", "social security",
        "where do you live", "my name is", "my school", "my teacher", "home address",
        "bank account", "ssn", "pin number", "birth certificate", "drivers license",
        "license plate", "ip address", "full name", "last name", "birthday",
        "where i live", "come to my house", "meet me at", "meet up"
    ],
    "adult_content": BLOCKED_WORDS_BY_CATEGORY["adult_content"],
    "substance": BLOCKED_WORDS_BY_CATEGORY["substances"],
    "self_harm": BLOCKED_WORDS_BY_CATEGORY["self_harm"],
    "cyberbullying": BLOCKED_WORDS_BY_CATEGORY["cyberbullying"],
    "hate_speech": BLOCKED_WORDS_BY_CATEGORY["hate_speech"],
    "dangerous_activities": BLOCKED_WORDS_BY_CATEGORY["dangerous_activities"]
}

CHAR_SUBSTITUTIONS = {
    '@': 'a', '4': 'a', '^': 'a', '8': 'b', '(': 'c', '<': 'c',
    '3': 'e', '6': 'g', '9': 'g', '#': 'h', '1': 'i', '!': 'i', '|': 'i',
    '0': 'o', '5': 's', '$': 's', '+': 't', 'v': 'u', '><': 'x', '¥': 'y', '2': 'z',
}

SAFE_WORDS = {
    'shell', 'classic', 'classics', 'class', 'assassin', 'assess', 'assistant',
    'associate', 'assume', 'assignment', 'passionate', 'compass',
    'assault', 'grass', 'glass', 'pass', 'mass', 'bass', 'brass',
    'cocktail', 'peacock', 'hancock', 'woodcock', 'shuttlecock',
    'scunthorpe', 'hello', 'shelling', 'shellfish',
    'analysis', 'analyst', 'analyzed', 'analytical',
    'title', 'titled', 'titles', 'titillate', 'titian',
    'thatch', 'thanks', 'that', 'the', 'them', 'then', 'there',
    'butterscotch', 'scratch', 'watch', 'catch', 'match',
    'executing', 'execution', 'execute', 'executive',
    'document', 'documents', 'documented',
    'cracked', 'cracker', 'crackers', 'cracking', 'firecracker',
    'its', 'hits', 'bits', 'kits', 'sits', 'fits', 'pits', 'wits',
    'classwork', 'classroom', 'classification', 'classical',
    'assassinate', 'assassinated', 'assassinating',
    'beautiful', 'beautifully', 'beauty', 'day', 'days', 'today',
    'database', 'dabble'
}

def normalize_leetspeak(text: str) -> str:
    result = text.lower()
    for leet, normal in CHAR_SUBSTITUTIONS.items():
        result = result.replace(leet, normal)
    result = re.sub(r'(.)\1{2,}', r'\1\1', result)
    result = re.sub(r'[\.\-_\*\s]+', '', result)
    return result

def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def fuzzy_match_word(word: str, blocked_words: list, max_distance: int = 2) -> tuple:
    word_normalized = normalize_leetspeak(word)
    if len(word_normalized) < 3:
        return (False, None, -1)
    for blocked in blocked_words:
        blocked_normalized = blocked.lower()
        length_diff = abs(len(word_normalized) - len(blocked_normalized))
        if length_diff > 2:
            continue
        if word_normalized == blocked_normalized:
            return (True, blocked, 0)
        if len(blocked_normalized) >= 4:
            if word_normalized.startswith(blocked_normalized) and len(word_normalized) - len(blocked_normalized) <= 2:
                return (True, blocked, 0)
            if word_normalized.endswith(blocked_normalized) and len(word_normalized) - len(blocked_normalized) <= 2:
                return (True, blocked, 0)
        distance = levenshtein_distance(word_normalized, blocked_normalized)
        if len(blocked_normalized) <= 4:
            if distance == 1 and length_diff <= 1:
                return (True, blocked, distance)
        elif len(blocked_normalized) <= 6:
            if distance <= 1 and length_diff <= 1:
                return (True, blocked, distance)
        else:
            effective_max_distance = min(max_distance, max(1, len(blocked_normalized) // 4))
            if distance <= effective_max_distance and length_diff <= 2:
                return (True, blocked, distance)
    return (False, None, -1)

def check_profanity(text: str) -> dict:
    text_lower = text.lower()
    text_normalized = normalize_leetspeak(text_lower)
    matched = []
    fuzzy_matched = []
    words = re.findall(r'[a-zA-Z0-9@$!#%^&*]+', text_lower)
    words_normalized = re.findall(r'[a-z]+', text_normalized)
    all_words = set(words + words_normalized)
    
    for word in all_words:
        if len(word) < 3:
            continue
        if word.lower() in SAFE_WORDS:
            continue
        word_normalized = normalize_leetspeak(word)
        if word_normalized in SAFE_WORDS:
            continue
        word_matched = False
        for blocked in BLOCKED_WORDS:
            blocked_lower = blocked.lower()
            length_diff = abs(len(word_normalized) - len(blocked_lower))
            if length_diff > 3:
                continue
            if word_normalized == blocked_lower or word.lower() == blocked_lower:
                if blocked not in matched:
                    matched.append(blocked)
                word_matched = True
                break
            if len(blocked_lower) >= 4:
                if word_normalized.startswith(blocked_lower):
                    extra_chars = len(word_normalized) - len(blocked_lower)
                    if extra_chars <= 3:
                        suffix = word_normalized[len(blocked_lower):]
                        if suffix in ['', 's', 'y', 'ed', 'er', 'ing', 'ly', 'ish', 'ness']:
                            if blocked not in matched:
                                matched.append(blocked)
                            word_matched = True
                            break
            if len(blocked_lower) <= 5 and len(word_normalized) <= 6 and length_diff <= 1:
                dist = levenshtein_distance(word_normalized, blocked_lower)
                if dist == 1:
                    if blocked not in matched:
                        matched.append(blocked)
                    word_matched = True
                    break
        if not word_matched:
            is_match, blocked_word, distance = fuzzy_match_word(word, BLOCKED_WORDS, max_distance=2)
            if is_match and blocked_word not in matched and blocked_word not in fuzzy_matched:
                if word.lower() not in SAFE_WORDS and word_normalized not in SAFE_WORDS:
                    fuzzy_matched.append(blocked_word)
    
    all_matched = matched + fuzzy_matched
    matched_categories = {}
    for word in all_matched:
        word_lower = word.lower()
        for category, words_list in BLOCKED_WORDS_BY_CATEGORY.items():
            if word_lower in [w.lower() for w in words_list]:
                if category not in matched_categories:
                    matched_categories[category] = []
                matched_categories[category].append(word)
                break
    
    return {
        "is_blocked": len(all_matched) > 0,
        "matched_words": all_matched,
        "fuzzy_matched": fuzzy_matched,
        "exact_matched": matched,
        "categories": matched_categories
    }

def check_restricted_topics(text: str) -> dict:
    """
    Check text for restricted topics using EXACT MATCH ONLY.
    No fuzzy matching - only exact word/phrase matches trigger flags.
    This prevents false positives on safe words like 'word', 'friend', etc.
    """
    text_lower = text.lower()
    flagged = {}
    
    category_priority = ["self_harm", "violence", "adult_content", "substance", 
                         "cyberbullying", "hate_speech", "dangerous_activities", "privacy"]
    
    # Extract words from text for exact matching
    words_in_text = set(re.findall(r'\b[a-zA-Z]+\b', text_lower))
    
    for category in category_priority:
        if category not in RESTRICTED_TOPICS:
            continue
        phrases = RESTRICTED_TOPICS[category]
        matches = []
        
        for phrase in phrases:
            phrase_lower = phrase.lower()
            
            # Multi-word phrase: check if entire phrase exists in text
            if ' ' in phrase_lower:
                if phrase_lower in text_lower:
                    if phrase not in matches:
                        matches.append(phrase)
            else:
                # Single word: EXACT match only (word must be in text as complete word)
                if phrase_lower in words_in_text:
                    if phrase not in matches:
                        matches.append(phrase)
        
        if matches:
            flagged[category] = matches
    
    return flagged


# ============================================================
# SYSTEM PROMPTS FOR DIFFERENT MODES
# ============================================================

REACT_SYSTEM_PROMPT = """You are BuddyBot, a warm, friendly, and safe AI companion for children aged 5-12. You speak in simple, encouraging language.

IMPORTANT: You must ALWAYS follow this ReAct thinking pattern internally before every response:

**THOUGHT**: First, analyze the child's message for safety. Consider:
- Is there any inappropriate content?
- Is the child sharing personal information?
- Is the child expressing distress or unsafe situations?
- What's the emotional tone?

**SAFETY_LEVEL**: Rate as SAFE, CAUTION, or ALERT

**RESPONSE**: Then compose your response following these rules:
1. Always be kind, encouraging, and age-appropriate
2. Use simple words a 5-year-old can understand
3. If asked about restricted topics, gently redirect to fun alternatives
4. If a child seems sad or scared, be comforting and suggest talking to a trusted adult
5. Never provide personal information or encourage sharing personal details
6. Keep responses SHORT (2-4 sentences max)

**FOLLOW_UPS**: After your response, ALWAYS generate exactly 3 follow-up question suggestions that the child might want to ask next. These should be context-aware and age-appropriate.

You MUST format your response EXACTLY like this:
[THOUGHT] Your safety analysis here
[SAFETY] SAFE or CAUTION or ALERT
[RESPONSE] Your child-friendly response here
[FOLLOWUPS]
1. First suggested follow-up question
2. Second suggested follow-up question
3. Third suggested follow-up question"""


QUIZ_SYSTEM_PROMPT = """You are BuddyBot's Quiz Master mode! Generate fun, educational multiple-choice quizzes for children aged 5-12.

Based on the conversation topic provided, create a quiz with the following format:

RULES:
1. Generate 3-5 multiple-choice questions
2. Each question should have 4 options (A, B, C, D)
3. Questions should be age-appropriate and educational
4. Include fun facts or explanations for the correct answers
5. Make it engaging and encouraging!

You MUST format your response EXACTLY like this:
[QUIZ_TITLE] Fun Quiz About [Topic]!
[QUESTION_1]
Q: Your question here?
A) Option A
B) Option B
C) Option C
D) Option D
CORRECT: A
FUN_FACT: A fun fact about the answer!

[QUESTION_2]
... (same format)

[END_QUIZ]"""


STORY_SYSTEM_PROMPT = """You are BuddyBot's Storyteller mode! Create magical, age-appropriate "Choose Your Own Adventure" stories for children aged 5-12.

RULES:
1. Stories should be imaginative, fun, and child-safe
2. Each story segment should be 2-3 short paragraphs
3. End each segment with 2-3 numbered choices for what happens next
4. Keep vocabulary simple and engaging
5. Include positive themes like friendship, bravery, kindness, and curiosity
6. NEVER include scary, violent, or inappropriate content

You MUST format your response EXACTLY like this:
[STORY_TITLE] Your Story Title Here
[SEGMENT]
Your story segment here... (2-3 paragraphs of the adventure)

[CHOICES]
1. First choice - what could happen
2. Second choice - another option
3. Third choice - yet another path (optional)

[STORY_STATUS] CONTINUE or END"""


WEBSEARCH_SYSTEM_PROMPT = """You are BuddyBot helping to summarize web content for children aged 5-12.

RULES:
1. Summarize the content in simple, child-friendly language
2. Remove any inappropriate or adult content
3. Highlight interesting facts
4. Keep the summary to 2-3 paragraphs maximum
5. If the content is not appropriate for children, say so politely and suggest a different topic

Format:
[SUMMARY] Your child-friendly summary here
[KEY_FACTS]
- Fact 1
- Fact 2
- Fact 3
[SAFETY_CHECK] SAFE or RESTRICTED (if restricted, explain why briefly)"""


def parse_react_response(raw_response: str) -> dict:
    """Parse the ReAct response including follow-up suggestions."""
    thought = ""
    safety_level = "SAFE"
    response = ""
    followups = []
    
    thought_match = re.search(r'\[THOUGHT\]\s*(.*?)(?=\[SAFETY\])', raw_response, re.DOTALL)
    safety_match = re.search(r'\[SAFETY\]\s*(SAFE|CAUTION|ALERT)', raw_response, re.DOTALL)
    response_match = re.search(r'\[RESPONSE\]\s*(.*?)(?=\[FOLLOWUPS\]|$)', raw_response, re.DOTALL)
    followups_match = re.search(r'\[FOLLOWUPS\]\s*(.*?)$', raw_response, re.DOTALL)
    
    if thought_match:
        thought = thought_match.group(1).strip()
    if safety_match:
        safety_level = safety_match.group(1).strip()
    if response_match:
        response = response_match.group(1).strip()
    if followups_match:
        followups_text = followups_match.group(1).strip()
        # Parse numbered follow-ups
        followup_lines = re.findall(r'\d+\.\s*(.+)', followups_text)
        followups = [f.strip() for f in followup_lines[:3]]
    
    if not response:
        response = raw_response.strip()
        thought = "Unable to parse structured response"
        safety_level = "CAUTION"
    
    return {
        "thought": thought,
        "safety_level": safety_level,
        "response": response,
        "followups": followups
    }


def parse_quiz_response(raw_response: str) -> dict:
    """Parse the quiz response into structured data."""
    quiz_data = {
        "title": "Fun Quiz!",
        "questions": [],
        "total_questions": 0
    }
    
    # Extract title
    title_match = re.search(r'\[QUIZ_TITLE\]\s*(.+)', raw_response)
    if title_match:
        quiz_data["title"] = title_match.group(1).strip()
    
    # Extract questions
    question_pattern = r'\[QUESTION_\d+\]\s*Q:\s*(.+?)\s*A\)\s*(.+?)\s*B\)\s*(.+?)\s*C\)\s*(.+?)\s*D\)\s*(.+?)\s*CORRECT:\s*([ABCD])\s*FUN_FACT:\s*(.+?)(?=\[QUESTION_|\[END_QUIZ\]|$)'
    questions = re.findall(question_pattern, raw_response, re.DOTALL)
    
    for q in questions:
        quiz_data["questions"].append({
            "question": q[0].strip(),
            "options": {
                "A": q[1].strip(),
                "B": q[2].strip(),
                "C": q[3].strip(),
                "D": q[4].strip()
            },
            "correct": q[5].strip(),
            "fun_fact": q[6].strip()
        })
    
    quiz_data["total_questions"] = len(quiz_data["questions"])
    return quiz_data


def parse_story_response(raw_response: str) -> dict:
    """Parse the story response into structured data."""
    story_data = {
        "title": "",
        "segment": "",
        "choices": [],
        "status": "CONTINUE"
    }
    
    title_match = re.search(r'\[STORY_TITLE\]\s*(.+)', raw_response)
    if title_match:
        story_data["title"] = title_match.group(1).strip()
    
    segment_match = re.search(r'\[SEGMENT\]\s*(.*?)(?=\[CHOICES\])', raw_response, re.DOTALL)
    if segment_match:
        story_data["segment"] = segment_match.group(1).strip()
    
    choices_match = re.search(r'\[CHOICES\]\s*(.*?)(?=\[STORY_STATUS\]|$)', raw_response, re.DOTALL)
    if choices_match:
        choices_text = choices_match.group(1).strip()
        choice_lines = re.findall(r'\d+\.\s*(.+)', choices_text)
        story_data["choices"] = [c.strip() for c in choice_lines]
    
    status_match = re.search(r'\[STORY_STATUS\]\s*(CONTINUE|END)', raw_response)
    if status_match:
        story_data["status"] = status_match.group(1).strip()
    
    return story_data


async def get_browsing_context(db: AsyncSession, device_id: str = None) -> str:
    if not device_id:
        result = await db.execute(
            select(BrowsingPacket).order_by(desc(BrowsingPacket.timestamp)).limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest:
            device_id = latest.device_id
        else:
            return ""
    
    result = await db.execute(
        select(BrowsingPacket)
        .where(BrowsingPacket.device_id == device_id, BrowsingPacket.packet_type == "search_query")
        .order_by(desc(BrowsingPacket.timestamp))
        .limit(20)
    )
    recent_searches = result.scalars().all()
    
    if not recent_searches:
        return ""
    
    context_parts = ["\n[BROWSING CONTEXT]:"]
    for s in recent_searches[:10]:
        mode = " (INCOGNITO)" if s.tab_type == "incognito" else ""
        context_parts.append(f"  - \"{s.search_query}\" on {s.search_engine or 'unknown'}{mode}")
    return "\n".join(context_parts)


# ============================================================
# AUTH ENDPOINTS
# ============================================================
@api_router.post("/auth/register")
async def register(data: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = data.email.lower().strip()
    
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user = User(
        email=email,
        name=data.name,
        phone=data.phone or "",
        password_hash=hash_password(data.password),
        auth_provider="email",
        role="parent",
        created_at=datetime.now(timezone.utc)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create default child profile
    child = ChildProfile(
        parent_id=user.id,
        name=f"{data.name}'s Child",
        created_at=datetime.now(timezone.utc)
    )
    db.add(child)
    await db.commit()
    await db.refresh(child)

    access_token = create_access_token(user.id, email)
    refresh_token = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "user_id": user.id,
        "name": user.name,
        "email": email,
        "phone": user.phone or "",
        "role": "parent",
        "child_id": child.id,
        "token": access_token,
        "extension_installed": False,  # New users haven't installed extension yet
    }


@api_router.post("/auth/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = data.email.lower().strip()
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.password_hash:
        raise HTTPException(status_code=401, detail="This account uses Google login. Please sign in with Google.")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user.id, email)
    refresh_token = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "user_id": user.id,
        "name": user.name,
        "email": email,
        "phone": user.phone or "",
        "role": user.role or "parent",
        "token": access_token,
        "extension_installed": user.extension_installed or False,
    }


@api_router.post("/auth/google")
async def google_auth(data: GoogleSessionRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Exchange Emergent Google OAuth session_id for our JWT tokens."""
    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": data.session_id}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google session")
            google_data = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google auth failed: {str(e)}")

    email = google_data["email"].lower()
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()

    if existing:
        existing.name = google_data.get("name", existing.name)
        existing.picture = google_data.get("picture", "")
        await db.commit()
        user = existing
    else:
        user = User(
            email=email,
            name=google_data.get("name", "Parent"),
            phone="",
            password_hash=None,
            auth_provider="google",
            picture=google_data.get("picture", ""),
            role="parent",
            created_at=datetime.now(timezone.utc)
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        child = ChildProfile(
            parent_id=user.id,
            name=f"{google_data.get('name', 'Parent')}'s Child",
            created_at=datetime.now(timezone.utc)
        )
        db.add(child)
        await db.commit()

    access_token = create_access_token(user.id, email)
    refresh_token = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, refresh_token)

    is_new_user = not existing
    return {
        "user_id": user.id,
        "name": user.name,
        "email": email,
        "phone": user.phone or "",
        "role": user.role or "parent",
        "token": access_token,
        "extension_installed": user.extension_installed or False,
        "is_new_user": is_new_user,
    }


@api_router.get("/auth/me")
async def auth_me(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    
    result = await db.execute(select(ChildProfile).where(ChildProfile.parent_id == user.id))
    children = result.scalars().all()
    
    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone or "",
        "role": user.role or "parent",
        "picture": user.picture or "",
        "extension_installed": user.extension_installed or False,
        "extension_device_id": user.extension_device_id,
        "children": [{"child_id": c.id, "name": c.name, "age": c.age} for c in children]
    }


class ExtensionConfirmRequest(BaseModel):
    device_id: str


@api_router.post("/auth/confirm-extension")
async def confirm_extension(data: ExtensionConfirmRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Confirm that the user has installed the browser extension."""
    user = await get_current_user(request, db)
    
    user.extension_installed = True
    user.extension_device_id = data.device_id
    await db.commit()
    
    return {
        "status": "confirmed",
        "extension_installed": True,
        "device_id": data.device_id
    }


@api_router.get("/auth/extension-status")
async def extension_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Check if current user has installed the extension."""
    user = await get_current_user(request, db)
    return {
        "extension_installed": user.extension_installed or False,
        "device_id": user.extension_device_id
    }


@api_router.post("/auth/verify-password")
async def verify_pwd(data: VerifyPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user.password_hash:
        # Google auth users - always allow dashboard access
        return {"verified": True}
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"verified": True}


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"status": "logged out"}


# ============================================================
# CHILD PROFILE ENDPOINTS
# ============================================================
@api_router.get("/children")
async def list_children(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(ChildProfile).where(ChildProfile.parent_id == user.id))
    children = result.scalars().all()
    return [{"child_id": c.id, "parent_id": c.parent_id, "name": c.name, "age": c.age, "created_at": c.created_at.isoformat() if c.created_at else None} for c in children]


@api_router.post("/children")
async def create_child(data: ChildProfileCreate, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    child = ChildProfile(
        parent_id=user.id,
        name=data.name,
        age=data.age,
        created_at=datetime.now(timezone.utc)
    )
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return {"child_id": child.id, "parent_id": child.parent_id, "name": child.name, "age": child.age, "created_at": child.created_at.isoformat()}


# ============================================================
# CHAT ENDPOINTS (Requires Authentication)
# ============================================================
@api_router.post("/chat/conversations")
async def create_conversation(data: ConversationCreate, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    conv = Conversation(
        user_id=user.id,
        title=data.title,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "message_count": 0,
        "has_flags": False,
        "flag_count": 0
    }


@api_router.get("/chat/conversations")
async def list_conversations(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(desc(Conversation.updated_at))
    )
    convs = result.scalars().all()
    return [{
        "id": c.id,
        "title": c.title,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "message_count": c.message_count or 0,
        "has_flags": c.has_flags or False,
        "flag_count": c.flag_count or 0
    } for c in convs]


@api_router.get("/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    
    return {
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "message_count": conv.message_count or 0,
            "has_flags": conv.has_flags or False,
            "flag_count": conv.flag_count or 0
        },
        "messages": [{
            "id": m.id,
            "conversation_id": m.conversation_id,
            "role": m.role,
            "text": m.text,
            "blocked": m.blocked or False,
            "blocked_words": m.blocked_words,
            "flagged_topics": m.flagged_topics,
            "thought": m.thought,
            "safety_level": m.safety_level,
            "created_at": m.created_at.isoformat() if m.created_at else None
        } for m in messages]
    }


@api_router.post("/chat/send")
async def send_message(data: MessageCreate, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    
    conversation_id = data.conversation_id
    text_lower = data.text.lower().strip()
    
    # Detect special modes
    is_quiz_mode = text_lower.startswith("/quiz") or text_lower == "quiz" or "start a quiz" in text_lower
    is_story_mode = text_lower.startswith("/story") or text_lower == "story" or "tell me a story" in text_lower or "start a story" in text_lower
    
    # Create new conversation if needed
    if not conversation_id:
        if is_quiz_mode:
            title = "🎯 Quiz Time!"
        elif is_story_mode:
            title = "📖 Story Adventure"
        else:
            title = data.text[:40] + ("..." if len(data.text) > 40 else "")
        conv = Conversation(
            user_id=user.id,
            child_id=data.child_id,
            title=title,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conversation_id = conv.id
    else:
        # Verify conversation belongs to user
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # EXACT MATCH blocking first (Feature #5 - Strict Filter)
    exact_block = check_exact_match_blocked(data.text)
    if exact_block["is_blocked"]:
        # Save blocked user message
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            text=data.text,
            blocked=True,
            blocked_words=exact_block["matched_words"],
            created_at=datetime.now(timezone.utc)
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # Create alert with exact match flag
        alert = Alert(
            conversation_id=conversation_id,
            message_id=user_msg.id,
            type="profanity",
            severity="high",
            details=f"EXACT MATCH blocked: {', '.join(exact_block['matched_words'])}",
            child_message=data.text,
            categories={"exact_match": exact_block["matched_words"]},
            created_at=datetime.now(timezone.utc)
        )
        db.add(alert)

        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                has_flags=True,
                updated_at=datetime.now(timezone.utc),
                message_count=Conversation.message_count + 1,
                flag_count=Conversation.flag_count + 1
            )
        )
        await db.commit()

        asyncio.create_task(notify_parent_of_alert(db, {
            "type": "profanity",
            "severity": "high",
            "details": f"EXACT MATCH blocked: {exact_block['matched_words']}",
            "child_message": data.text
        }, data.child_id))

        bot_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            text="Hmm, let's use kind and friendly words! How about we talk about something fun instead? What's your favorite animal? 🐾",
            thought="Exact match profanity filter triggered.",
            safety_level="ALERT",
            created_at=datetime.now(timezone.utc)
        )
        db.add(bot_msg)
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(message_count=Conversation.message_count + 1, updated_at=datetime.now(timezone.utc))
        )
        await db.commit()
        await db.refresh(bot_msg)

        return {
            "conversation_id": conversation_id,
            "user_message": {
                "id": user_msg.id,
                "role": "user",
                "text": data.text,
                "blocked": True,
                "blocked_words": exact_block["matched_words"],
                "created_at": user_msg.created_at.isoformat()
            },
            "bot_message": {
                "id": bot_msg.id,
                "role": "assistant",
                "text": bot_msg.text,
                "thought": bot_msg.thought,
                "safety_level": bot_msg.safety_level,
                "created_at": bot_msg.created_at.isoformat(),
                "followups": ["What's your favorite color?", "Do you have any pets?", "What did you do today?"]
            },
            "blocked": True,
            "mode": "chat"
        }

    # Check restricted topics
    restricted = check_restricted_topics(data.text)

    # Save user message
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        text=data.text,
        blocked=False,
        flagged_topics=restricted if restricted else None,
        created_at=datetime.now(timezone.utc)
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Get conversation history for context
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.blocked != True)
        .order_by(Message.created_at)
        .limit(20)
    )
    history = result.scalars().all()

    context_parts = []
    for msg in history[:-1]:
        if msg.role == "user":
            context_parts.append(f"Child: {msg.text}")
        else:
            context_parts.append(f"BuddyBot: {msg.text}")
    context_str = "\n".join(context_parts[-10:])

    browsing_context = await get_browsing_context(db, data.device_id)
    extra_context = ""
    if restricted:
        extra_context = f"\n\n[SYSTEM NOTE: Restricted topics detected: {restricted}. Redirect gently.]"

    # Determine mode and system prompt
    mode = "chat"
    system_prompt = REACT_SYSTEM_PROMPT
    
    if is_quiz_mode:
        mode = "quiz"
        system_prompt = QUIZ_SYSTEM_PROMPT
        # Extract topic from conversation context
        topic = "general knowledge"
        if context_str:
            topic = f"the topics discussed: {context_str[-500:]}"
        full_prompt = f"Generate a fun quiz based on {topic}. The child said: {data.text}"
    elif is_story_mode:
        mode = "story"
        system_prompt = STORY_SYSTEM_PROMPT
        full_prompt = f"Start an exciting adventure story for a child. The child said: {data.text}"
    else:
        prefix = f"Previous conversation:\n{context_str}\n\n" if context_str else ""
        full_prompt = f"{prefix}Child's message: {data.text}{extra_context}{browsing_context}"

    # Call LLM
    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"buddy-{conversation_id}-{uuid.uuid4().hex[:8]}", system_message=system_prompt)
        chat.with_model("openai", "gpt-4.1-mini")
        raw_response = await chat.send_message(UserMessage(text=full_prompt))
        
        if mode == "quiz":
            parsed = parse_quiz_response(raw_response)
            response_text = f"🎯 {parsed['title']}\n\nLet's start! Here's your first question:\n\n"
            if parsed["questions"]:
                q = parsed["questions"][0]
                response_text += f"**{q['question']}**\n\n"
                response_text += f"A) {q['options']['A']}\n"
                response_text += f"B) {q['options']['B']}\n"
                response_text += f"C) {q['options']['C']}\n"
                response_text += f"D) {q['options']['D']}\n\n"
                response_text += "Click your answer below! 👇"
            parsed_response = {
                "thought": "Quiz mode activated",
                "safety_level": "SAFE",
                "response": response_text,
                "followups": [],
                "quiz_data": parsed
            }
        elif mode == "story":
            parsed = parse_story_response(raw_response)
            response_text = f"📖 **{parsed['title']}**\n\n{parsed['segment']}"
            parsed_response = {
                "thought": "Story mode activated",
                "safety_level": "SAFE",
                "response": response_text,
                "followups": [],
                "story_data": parsed
            }
        else:
            parsed_response = parse_react_response(raw_response)
            
    except Exception as e:
        logger.error(f"LLM error: {e}")
        parsed_response = {
            "thought": f"LLM call failed: {str(e)}",
            "safety_level": "CAUTION",
            "response": "Oops! My brain got a little fuzzy for a second. Can you say that again?",
            "followups": ["What would you like to talk about?", "Tell me about your day!", "Want to play a game?"]
        }

    # Create alert if needed
    if parsed_response.get("safety_level") == "ALERT" or restricted:
        severity = "high" if parsed_response.get("safety_level") == "ALERT" else "medium"
        alert = Alert(
            conversation_id=conversation_id,
            message_id=user_msg.id,
            type="restricted_topic",
            severity=severity,
            details=f"Safety Level: {parsed_response.get('safety_level')}. Topics: {restricted if restricted else 'AI flagged'}. AI Thought: {parsed_response.get('thought', '')[:200]}",
            child_message=data.text,
            created_at=datetime.now(timezone.utc)
        )
        db.add(alert)
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(has_flags=True, flag_count=Conversation.flag_count + 1)
        )
        asyncio.create_task(notify_parent_of_alert(db, {
            "type": "restricted_topic",
            "severity": severity,
            "details": alert.details,
            "child_message": data.text
        }, data.child_id))

    # Save bot response
    bot_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        text=parsed_response.get("response", ""),
        thought=parsed_response.get("thought", ""),
        safety_level=parsed_response.get("safety_level", "SAFE"),
        created_at=datetime.now(timezone.utc)
    )
    db.add(bot_msg)
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(message_count=Conversation.message_count + 2, updated_at=datetime.now(timezone.utc))
    )
    await db.commit()
    await db.refresh(bot_msg)

    response_data = {
        "conversation_id": conversation_id,
        "user_message": {
            "id": user_msg.id,
            "role": "user",
            "text": data.text,
            "blocked": False,
            "flagged_topics": restricted if restricted else None,
            "created_at": user_msg.created_at.isoformat()
        },
        "bot_message": {
            "id": bot_msg.id,
            "role": "assistant",
            "text": bot_msg.text,
            "thought": bot_msg.thought,
            "safety_level": bot_msg.safety_level,
            "created_at": bot_msg.created_at.isoformat(),
            "followups": parsed_response.get("followups", [])
        },
        "blocked": False,
        "mode": mode
    }
    
    # Add mode-specific data
    if mode == "quiz" and "quiz_data" in parsed_response:
        response_data["quiz_data"] = parsed_response["quiz_data"]
    elif mode == "story" and "story_data" in parsed_response:
        response_data["story_data"] = parsed_response["story_data"]
    
    return response_data


# ============================================================
# QUIZ ENDPOINTS (Feature #1)
# ============================================================
@api_router.post("/chat/quiz/answer")
async def answer_quiz(data: QuizAnswerRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Handle quiz answer submission and return result with next question."""
    user = await get_current_user(request, db)
    
    # For now, we'll generate feedback using LLM
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"quiz-{data.conversation_id}", system_message="You are a friendly quiz host for children. Give encouraging feedback on their answer.")
    chat.with_model("openai", "gpt-4.1-mini")
    
    prompt = f"The child answered '{data.answer}' for question #{data.question_index + 1}. Give brief, encouraging feedback (1-2 sentences) whether right or wrong."
    response = await chat.send_message(UserMessage(text=prompt))
    
    return {
        "feedback": response,
        "question_index": data.question_index,
        "answer": data.answer
    }


# ============================================================
# STORY ENDPOINTS (Feature #2)
# ============================================================
@api_router.post("/chat/story/choice")
async def story_choice(data: StoryChoiceRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Handle story choice and continue the adventure."""
    user = await get_current_user(request, db)
    
    # Get conversation history
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == data.conversation_id)
        .order_by(desc(Message.created_at))
        .limit(5)
    )
    recent_msgs = result.scalars().all()
    
    story_context = "\n".join([m.text for m in reversed(recent_msgs)])
    
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"story-{data.conversation_id}", system_message=STORY_SYSTEM_PROMPT)
    chat.with_model("openai", "gpt-4.1-mini")
    
    prompt = f"Previous story:\n{story_context}\n\nThe child chose option {data.choice_index}. Continue the adventure!"
    raw_response = await chat.send_message(UserMessage(text=prompt))
    parsed = parse_story_response(raw_response)
    
    # Save the choice and continuation
    user_msg = Message(
        conversation_id=data.conversation_id,
        role="user",
        text=f"[Chose option {data.choice_index}]",
        created_at=datetime.now(timezone.utc)
    )
    db.add(user_msg)
    
    bot_msg = Message(
        conversation_id=data.conversation_id,
        role="assistant",
        text=parsed["segment"],
        thought="Story continuation",
        safety_level="SAFE",
        created_at=datetime.now(timezone.utc)
    )
    db.add(bot_msg)
    await db.commit()
    
    return {
        "story_data": parsed,
        "segment": parsed["segment"],
        "choices": parsed["choices"],
        "status": parsed["status"]
    }


# ============================================================
# WEB SEARCH ENDPOINT (Feature #4)
# ============================================================
@api_router.post("/chat/search")
async def web_search_chat(data: WebSearchRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Search the web or summarize a URL for child-safe content."""
    user = await get_current_user(request, db)
    
    # Safety check on the query first
    exact_block = check_exact_match_blocked(data.query)
    if exact_block["is_blocked"]:
        return {
            "safe": False,
            "summary": "I can't search for that. Let's look up something fun instead!",
            "blocked_reason": "restricted_query"
        }
    
    restricted = check_restricted_topics(data.query)
    if restricted:
        return {
            "safe": False,
            "summary": "That topic might not be the best for kids. How about we explore something else?",
            "blocked_reason": "restricted_topic",
            "topics": list(restricted.keys())
        }
    
    # Use LLM to generate a child-safe response about the topic
    # (In production, you'd integrate actual web search here)
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"search-{uuid.uuid4().hex[:8]}", system_message=WEBSEARCH_SYSTEM_PROMPT)
    chat.with_model("openai", "gpt-4.1-mini")
    
    if data.url:
        prompt = f"The child wants to learn about content from this URL: {data.url}. Provide a child-friendly summary about the topic. If you can't access it, give general educational info about the topic."
    else:
        prompt = f"The child wants to learn about: {data.query}. Provide a child-friendly educational summary."
    
    raw_response = await chat.send_message(UserMessage(text=prompt))
    
    # Parse the response
    summary_match = re.search(r'\[SUMMARY\]\s*(.*?)(?=\[KEY_FACTS\]|$)', raw_response, re.DOTALL)
    facts_match = re.search(r'\[KEY_FACTS\]\s*(.*?)(?=\[SAFETY_CHECK\]|$)', raw_response, re.DOTALL)
    safety_match = re.search(r'\[SAFETY_CHECK\]\s*(SAFE|RESTRICTED)', raw_response)
    
    summary = summary_match.group(1).strip() if summary_match else raw_response
    
    key_facts = []
    if facts_match:
        facts_text = facts_match.group(1).strip()
        key_facts = [f.strip().lstrip('-').strip() for f in facts_text.split('\n') if f.strip()]
    
    is_safe = True
    if safety_match and safety_match.group(1) == "RESTRICTED":
        is_safe = False
        summary = "This topic might not be appropriate for kids. Let's explore something else!"
    
    return {
        "safe": is_safe,
        "summary": summary,
        "key_facts": key_facts[:5],
        "query": data.query
    }


# ============================================================
# EXTENSION ENDPOINTS
# ============================================================
@api_router.post("/extension/packets")
async def receive_packets(batch: PacketBatch, db: AsyncSession = Depends(get_db)):
    if not batch.packets:
        return {"status": "ok", "received": 0}
    
    alerts_to_create = []
    
    for packet in batch.packets:
        bp = BrowsingPacket(
            id=packet.id,
            device_id=packet.device_id,
            timestamp=packet.timestamp,
            tab_type=packet.tab_type,
            url=packet.url,
            domain=packet.domain,
            title=packet.title,
            packet_type=packet.packet_type,
            search_query=packet.search_query,
            search_engine=packet.search_engine,
            synced_at=datetime.now(timezone.utc)
        )
        
        if packet.packet_type == "search_query" and packet.search_query:
            profanity = check_profanity(packet.search_query)
            restricted = check_restricted_topics(packet.search_query)
            bp.profanity_flagged = profanity["is_blocked"]
            bp.profanity_words = profanity["matched_words"]
            bp.profanity_categories = profanity.get("categories", {})
            bp.fuzzy_matched = profanity.get("fuzzy_matched", [])
            bp.restricted_topics = restricted if restricted else None
            
            if profanity["is_blocked"] or restricted:
                severity = "high" if profanity["is_blocked"] else "medium"
                categories_info = f" | Categories: {', '.join(profanity['categories'].keys())}" if profanity.get("categories") else ""
                
                alert = Alert(
                    type="browsing_alert",
                    severity=severity,
                    device_id=batch.device_id,
                    details=f"Flagged search: \"{packet.search_query}\" on {packet.search_engine or 'browser'}{categories_info}",
                    child_message=packet.search_query,
                    tab_type=packet.tab_type,
                    url=packet.url,
                    source="extension",
                    categories=profanity.get("categories", {}),
                    fuzzy_matched=profanity.get("fuzzy_matched", []),
                    created_at=datetime.now(timezone.utc)
                )
                if restricted:
                    alert.details += f" | Topics: {list(restricted.keys())}"
                alerts_to_create.append(alert)
        
        db.add(bp)
    
    for alert in alerts_to_create:
        db.add(alert)
        asyncio.create_task(notify_parent_of_alert(db, {
            "type": alert.type,
            "severity": alert.severity,
            "details": alert.details,
            "child_message": alert.child_message
        }))
    
    await db.commit()
    
    return {"status": "ok", "received": len(batch.packets), "alerts_created": len(alerts_to_create)}


@api_router.get("/extension/status/{device_id}")
async def get_device_extension_status(device_id: str, db: AsyncSession = Depends(get_db)):
    packet_count = await db.execute(select(func.count()).select_from(BrowsingPacket).where(BrowsingPacket.device_id == device_id))
    packet_count = packet_count.scalar()
    
    result = await db.execute(
        select(BrowsingPacket)
        .where(BrowsingPacket.device_id == device_id)
        .order_by(desc(BrowsingPacket.timestamp))
        .limit(1)
    )
    last_packet = result.scalar_one_or_none()
    
    alert_count = await db.execute(
        select(func.count()).select_from(Alert)
        .where(Alert.device_id == device_id, Alert.source == "extension")
    )
    alert_count = alert_count.scalar()
    
    return {
        "device_id": device_id,
        "total_packets": packet_count,
        "last_activity": last_packet.timestamp if last_packet else None,
        "total_alerts": alert_count
    }


# ============================================================
# PARENT DASHBOARD ENDPOINTS (Auth required)
# ============================================================
@api_router.get("/parent/dashboard")
async def parent_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    
    total_conversations = await db.execute(select(func.count()).select_from(Conversation).where(Conversation.user_id == user.id))
    total_conversations = total_conversations.scalar()
    
    total_messages = await db.execute(
        select(func.count()).select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
    )
    total_messages = total_messages.scalar()
    
    total_alerts = await db.execute(
        select(func.count()).select_from(Alert)
        .join(Conversation, Alert.conversation_id == Conversation.id, isouter=True)
        .where((Conversation.user_id == user.id) | (Alert.conversation_id == None))
    )
    total_alerts = total_alerts.scalar()
    
    unresolved_alerts = await db.execute(
        select(func.count()).select_from(Alert)
        .where(Alert.resolved == False)
    )
    unresolved_alerts = unresolved_alerts.scalar()
    
    flagged_conversations = await db.execute(
        select(func.count()).select_from(Conversation)
        .where(Conversation.user_id == user.id, Conversation.has_flags == True)
    )
    flagged_conversations = flagged_conversations.scalar()
    
    total_packets = await db.execute(select(func.count()).select_from(BrowsingPacket))
    total_packets = total_packets.scalar()
    
    browsing_alerts = await db.execute(
        select(func.count()).select_from(Alert).where(Alert.source == "extension")
    )
    browsing_alerts = browsing_alerts.scalar()
    
    incognito_count = await db.execute(
        select(func.count()).select_from(BrowsingPacket).where(BrowsingPacket.tab_type == "incognito")
    )
    incognito_count = incognito_count.scalar()
    
    result = await db.execute(select(Alert).order_by(desc(Alert.created_at)).limit(10))
    recent_alerts = result.scalars().all()
    
    return {
        "stats": {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_alerts": total_alerts,
            "unresolved_alerts": unresolved_alerts,
            "flagged_conversations": flagged_conversations,
            "total_packets": total_packets,
            "browsing_alerts": browsing_alerts,
            "incognito_searches": incognito_count
        },
        "recent_alerts": [{
            "id": a.id,
            "type": a.type,
            "severity": a.severity,
            "details": a.details,
            "child_message": a.child_message,
            "resolved": a.resolved,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in recent_alerts]
    }


@api_router.get("/parent/alerts")
async def get_alerts(request: Request, resolved: Optional[bool] = None, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    
    query = select(Alert)
    if resolved is not None:
        query = query.where(Alert.resolved == resolved)
    query = query.order_by(desc(Alert.created_at)).limit(100)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    return [{
        "id": a.id,
        "conversation_id": a.conversation_id,
        "message_id": a.message_id,
        "type": a.type,
        "severity": a.severity,
        "details": a.details,
        "child_message": a.child_message,
        "categories": a.categories,
        "resolved": a.resolved,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None
    } for a in alerts]


@api_router.put("/parent/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"status": "resolved", "alert_id": alert_id}


@api_router.get("/parent/conversations")
async def parent_conversations(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(desc(Conversation.updated_at))
        .limit(100)
    )
    convs = result.scalars().all()
    
    return [{
        "id": c.id,
        "title": c.title,
        "message_count": c.message_count or 0,
        "has_flags": c.has_flags or False,
        "flag_count": c.flag_count or 0,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None
    } for c in convs]


@api_router.get("/parent/conversations/{conversation_id}")
async def parent_conversation_detail(conversation_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    
    result = await db.execute(
        select(Alert).where(Alert.conversation_id == conversation_id).order_by(desc(Alert.created_at))
    )
    alerts = result.scalars().all()
    
    return {
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "message_count": conv.message_count or 0,
            "has_flags": conv.has_flags or False,
            "flag_count": conv.flag_count or 0,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
        },
        "messages": [{
            "id": m.id,
            "role": m.role,
            "text": m.text,
            "blocked": m.blocked or False,
            "blocked_words": m.blocked_words,
            "thought": m.thought,
            "safety_level": m.safety_level,
            "created_at": m.created_at.isoformat() if m.created_at else None
        } for m in messages],
        "alerts": [{
            "id": a.id,
            "type": a.type,
            "severity": a.severity,
            "details": a.details,
            "resolved": a.resolved,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in alerts]
    }


@api_router.get("/parent/browsing/stats")
async def browsing_stats(request: Request, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    
    total = await db.execute(select(func.count()).select_from(BrowsingPacket))
    search_count = await db.execute(select(func.count()).select_from(BrowsingPacket).where(BrowsingPacket.packet_type == "search_query"))
    visit_count = await db.execute(select(func.count()).select_from(BrowsingPacket).where(BrowsingPacket.packet_type == "url_visit"))
    incognito = await db.execute(select(func.count()).select_from(BrowsingPacket).where(BrowsingPacket.tab_type == "incognito"))
    flagged = await db.execute(select(func.count()).select_from(BrowsingPacket).where(BrowsingPacket.profanity_flagged == True))
    browsing_alerts = await db.execute(select(func.count()).select_from(Alert).where(Alert.source == "extension"))
    
    result = await db.execute(select(BrowsingPacket.device_id).distinct())
    devices = [r[0] for r in result.fetchall()]
    
    return {
        "total_packets": total.scalar(),
        "search_count": search_count.scalar(),
        "visit_count": visit_count.scalar(),
        "incognito_count": incognito.scalar(),
        "flagged_searches": flagged.scalar(),
        "browsing_alerts": browsing_alerts.scalar(),
        "devices": devices
    }


@api_router.get("/parent/browsing/searches")
async def browsing_searches(request: Request, device_id: Optional[str] = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    
    query = select(BrowsingPacket).where(BrowsingPacket.packet_type == "search_query")
    if device_id:
        query = query.where(BrowsingPacket.device_id == device_id)
    query = query.order_by(desc(BrowsingPacket.timestamp)).limit(limit)
    
    result = await db.execute(query)
    packets = result.scalars().all()
    
    return [{
        "id": p.id,
        "device_id": p.device_id,
        "timestamp": p.timestamp,
        "tab_type": p.tab_type,
        "search_query": p.search_query,
        "search_engine": p.search_engine,
        "profanity_flagged": p.profanity_flagged,
        "profanity_words": p.profanity_words,
        "restricted_topics": p.restricted_topics
    } for p in packets]


@api_router.get("/parent/browsing/visits")
async def browsing_visits(request: Request, device_id: Optional[str] = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    
    query = select(BrowsingPacket).where(BrowsingPacket.packet_type == "url_visit")
    if device_id:
        query = query.where(BrowsingPacket.device_id == device_id)
    query = query.order_by(desc(BrowsingPacket.timestamp)).limit(limit)
    
    result = await db.execute(query)
    packets = result.scalars().all()
    
    return [{
        "id": p.id,
        "device_id": p.device_id,
        "timestamp": p.timestamp,
        "tab_type": p.tab_type,
        "url": p.url,
        "domain": p.domain,
        "title": p.title
    } for p in packets]


@api_router.get("/parent/browsing/analysis")
async def browsing_analysis(request: Request, device_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    
    if not device_id:
        result = await db.execute(
            select(BrowsingPacket.device_id).order_by(desc(BrowsingPacket.timestamp)).limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest:
            device_id = latest
        else:
            return {"safety_level": "SAFE", "analysis": "No browsing data available", "concerns": []}

    recent_searches_query = select(BrowsingPacket).where(
        BrowsingPacket.device_id == device_id, 
        BrowsingPacket.packet_type == "search_query"
    ).order_by(desc(BrowsingPacket.timestamp)).limit(50)
    
    result = await db.execute(recent_searches_query)
    recent_searches = result.scalars().all()
    
    concerns = []
    for search in recent_searches:
        query_text = search.search_query or ""
        topics = check_restricted_topics(query_text)
        profanity = check_profanity(query_text)
        if topics or profanity["is_blocked"]:
            concerns.append({
                "query": query_text, 
                "topics": topics, 
                "profanity": profanity["matched_words"], 
                "tab_type": search.tab_type or "normal", 
                "timestamp": search.timestamp, 
                "search_engine": search.search_engine
            })
            
    total_visits_query = select(func.count()).select_from(BrowsingPacket).where(
        BrowsingPacket.device_id == device_id, 
        BrowsingPacket.packet_type == "url_visit"
    )
    result = await db.execute(total_visits_query)
    total_visits = result.scalar()
    
    incognito_count = len([s for s in recent_searches if s.tab_type == "incognito"])
    
    return {
        "safety_level": "ALERT" if len(concerns) > 3 else ("CAUTION" if concerns else "SAFE"),
        "analysis": f"{len(concerns)} concerning searches found out of {len(recent_searches)} total." if concerns else "No concerning patterns detected.",
        "positive": "Child shows healthy interest in educational topics." if len(recent_searches) > len(concerns) * 3 else "",
        "flagged_searches": concerns,
        "total_searches": len(recent_searches),
        "total_visits": total_visits or 0,
        "incognito_count": incognito_count
    }

@api_router.get("/init-db")
async def init_db():
    try:
        from database import engine, Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return {"status": "success", "message": "All database tables safely created!"}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}


@api_router.get("/")
async def root():
    return {"message": "BuddyBot API is running"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
