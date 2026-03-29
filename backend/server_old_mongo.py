from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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
from emergentintegrations.llm.chat import LlmChat, UserMessage
import httpx

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

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


async def get_current_user(request: Request) -> dict:
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
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user.pop("password_hash", None)
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

class BrowsingPacket(BaseModel):
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
    packets: List[BrowsingPacket]


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


async def notify_parent_of_alert(alert_doc: dict, child_id: str = None):
    """Find the parent and send them an alert email."""
    parent = None
    if child_id:
        child = await db.child_profiles.find_one({"child_id": child_id}, {"_id": 0})
        if child:
            parent = await db.users.find_one({"user_id": child["parent_id"]}, {"_id": 0})
    if not parent:
        # Try to find any parent (single-parent setup)
        parent = await db.users.find_one({}, {"_id": 0})
    if parent and parent.get("email"):
        await send_alert_email(
            parent_email=parent["email"],
            parent_name=parent.get("name", "Parent"),
            alert_type=alert_doc.get("type", "safety_alert"),
            details=alert_doc.get("details", ""),
            child_message=alert_doc.get("child_message", ""),
            severity=alert_doc.get("severity", "medium")
        )


# ============================================================
# PROFANITY / SAFETY FILTER WITH FUZZY MATCHING
# ============================================================

# Comprehensive blocked words list - organized by category
BLOCKED_WORDS_BY_CATEGORY = {
    "profanity": [
        # Common swear words and variations
        "fuck", "shit", "ass", "asshole", "bitch", "bastard", "damn", "crap",
        "dick", "cock", "pussy", "cunt", "twat", "prick", "bollocks", "wanker",
        "slut", "whore", "skank", "tramp", "fag", "faggot", "dyke",
        "retard", "retarded", "spaz", "moron", "imbecile",
        "piss", "pissed", "bloody", "bugger", "arse", "arsehole", "tosser",
        "douchebag", "douche", "jackass", "dipshit", "shithead", "asshat",
        "motherfucker", "fucker", "bullshit", "horseshit", "goddam", "goddamn",
        "damnit", "screwed",
        "wtf", "stfu", "omfg", "fml"
    ],
    "violence": [
        # Weapons
        "gun", "rifle", "pistol", "shotgun", "firearm", "weapon", "knife",
        "blade", "machete", "axe", "bomb", "explosive", "grenade",
        "missile", "bullet", "ammo", "ammunition", "caliber",
        # Violence actions
        "kill", "murder", "assassinate", "slaughter", "massacre", "execute",
        "shoot", "stab", "slash", "strangle", "choke", "suffocate", "drown",
        "beat", "punch", "kick", "attack", "assault", "hurt", "harm", "injure",
        "torture", "mutilate", "dismember", "decapitate", "behead", "hang",
        # Violence outcomes
        "die", "death", "dead", "blood", "bleed", "bleeding", "gore", "gory",
        "corpse", "body", "murder", "homicide", "genocide", "massacre",
        
    ],
    "adult_content": [
        # Sexual terms
        "sex", "sexual", "sexy", "porn", "porno", "pornography", "xxx",
        "nude", "naked", "nudity", "strip", "stripper", "striptease",
        "erotic", "erotica", "fetish", "kink", "kinky", "bdsm", "bondage",
        "orgasm", "orgasmic", "climax", "horny", "aroused", "arousal",
        "masturbate", "masturbation", "jerk", "wank", "fap",
        "penis", "vagina", "boob", "boobs", "breast", "breasts", "tit", "tits",
        "butt", "buttocks", "genitals", "genital", "testicle", "testicles",
        # Sexual acts
        "intercourse", "fornicate", "fornication", "copulate", "copulation",
        "blowjob", "handjob", "fingering", "oral", "anal",
        # Adult industry
        "escort", "prostitute", "prostitution", "hooker", "brothel",
        "onlyfans", "camgirl", "webcam", "livecam", "chaturbate",
        # Dating/romantic (mild but flagged for children)
        "hookup", "onenight", "fwb", "nudes", "sext", "sexting"
    ],
    "substances": [
        # Drugs
        "drug", "drugs", "cocaine", "coke", "crack", "heroin", "meth",
        "methamphetamine", "amphetamine", "ecstasy", "mdma", "molly",
        "lsd", "acid", "shrooms", "mushrooms", "psilocybin", "dmt",
        "ketamine", "pcp", "angel dust", "fentanyl", "opium", "opioid",
        "morphine", "codeine", "oxycodone", "hydrocodone", "percocet",
        "xanax", "adderall", "ritalin", "valium", "barbiturate",
        # Cannabis
        "weed", "marijuana", "cannabis", "pot", "joint", "blunt", "bong",
        "edible", "thc", "cbd", "stoner", "420",
        # Alcohol
        "alcohol", "beer", "wine", "vodka", "whiskey", "whisky", "rum",
        "tequila", "gin", "brandy", "bourbon", "scotch", "liquor", "booze",
        "drunk", "wasted", "hammered", "plastered", "intoxicated", "tipsy",
        "hangover", "binge", "binging", "chug", "shots", "cocktail",
        # Tobacco
        "cigarette", "cigar", "tobacco", "nicotine", "smoke", "smoking",
        "vape", "vaping", "juul", "e-cig", "ecigarette",
        # Drug actions
        "high", "stoned", "tripping", "overdose", "inject", "snort", "dealer"
    ],
    "self_harm": [
        # Self-harm
        "suicide", "suicidal", "kill myself", "end my life", "end it all",
        "want to die", "wanna die", "wish i was dead", "better off dead",
        "cut myself", "cutting", "self harm", "selfharm", "self-harm",
        "hurt myself", "hurting myself", "harm myself", "harming myself",
        "slit wrist", "slit wrists", "hang myself", "hanging myself",
        "overdose", "take pills", "jump off", "jump from",
        # Depression indicators
        "worthless", "hopeless", "no reason to live", "nobody cares",
        "everyone hates me", "no point", "give up", "giving up",
        "cant go on", "can't go on", "dont want to live", "don't want to live",
        "life is pointless", "meaningless", "empty inside"
    ],
    "cyberbullying": [
        # Direct insults
        "loser", "ugly", "freak", "weirdo", "nerd", "geek",
        "dork", "lame", "pathetic", "worthless", "useless",
        "idiot", "moron", "imbecile", "creep", "creepy", "gross", "disgusting",
        # Exclusion
        "nobody likes you", "no friends", "unfriend", "blocked", "ignored",
        "go away", "leave me alone", "unwanted", "rejected", "outcast",
        # Threats
        "gonna get you", "watch out", "you'll regret", "you're dead",
        "gonna beat", "gonna hurt", "i'll find you", "tell everyone",
        "spread rumors", "embarrass you", "expose you", "leak your",
        # Harassment
        "harass", "harassment", "bully", "bullying", "stalk", "stalking",
        "troll", "trolling", "spam", "spamming", "doxx", "doxxing",
        "catfish", "catfishing", "ghosting", "cancel", "cancelled"
    ],
    "hate_speech": [
        # Racial slurs (partial - many removed for sensitivity)
        "racist", "racism", "racial", "negro", "nigga", "nigger", "cracker",
        "wetback", "beaner", "chink", "gook", "jap", "spic", "kike",
        # Religious hate
        "islamophobe", "antisemite", "antisemitic", "christophobe",
        # LGBTQ hate
        "homophobe", "homophobic", "transphobe", "transphobic",
        "fag", "faggot", "dyke", "tranny", "shemale",
        # General hate
        "hate", "hater", "hating", "despise", "detest", "loathe",
        "supremacist", "supremacy", "nazi", "hitler", "fascist",
        "bigot", "bigotry", "prejudice", "discriminate", "discrimination",
        "xenophobe", "xenophobic", "misogynist", "misogyny",
        # Slurs
        "retard", "retarded", "cripple", "handicapped", "midget"
    ],
    "dangerous_activities": [
        # Dangerous challenges
        "challenge", "dare", "choking game", "blackout challenge",
        "tide pod", "cinnamon challenge", "salt and ice", "fire challenge",
        # Illegal activities
        "hack", "hacking", "hacker", "exploit", "crack", "pirate", "piracy",
        "steal", "stealing", "theft", "rob", "robbing", "burglary",
        "shoplift", "shoplifting", "vandal", "vandalism", "graffiti",
        # Terrorism
        "terrorist", "terrorism", "terror", "jihad", "isis", "al qaeda",
        "bomb threat", "mass shooting", "shooting", "hostage",
        # Predatory
        "predator", "grooming", "molest", "pedophile", "pedo", "kidnap"
    ]
}

# Flatten all blocked words into a single list
BLOCKED_WORDS = []
for category_words in BLOCKED_WORDS_BY_CATEGORY.values():
    BLOCKED_WORDS.extend(category_words)
BLOCKED_WORDS = list(set(BLOCKED_WORDS))  # Remove duplicates

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

# Common character substitutions (leetspeak)
CHAR_SUBSTITUTIONS = {
    '@': 'a', '4': 'a', '^': 'a',
    '8': 'b',
    '(': 'c', '<': 'c',
    '3': 'e',
    '6': 'g', '9': 'g',
    '#': 'h',
    '1': 'i', '!': 'i', '|': 'i',
    '0': 'o',
    '5': 's', '$': 's',
    '+': 't',
    'v': 'u',
    'w': 'vv',
    '><': 'x',
    '¥': 'y',
    '2': 'z',
}

def normalize_leetspeak(text: str) -> str:
    """Convert leetspeak/character substitutions to regular letters."""
    result = text.lower()
    for leet, normal in CHAR_SUBSTITUTIONS.items():
        result = result.replace(leet, normal)
    # Remove repeated characters (e.g., "fuuuuck" -> "fuck")
    result = re.sub(r'(.)\1{2,}', r'\1\1', result)
    # Remove common separators used to bypass filters (e.g., "f.u.c.k" -> "fuck")
    result = re.sub(r'[\.\-_\*\s]+', '', result)
    return result

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein distance between two strings."""
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
    """
    Check if a word fuzzy-matches any blocked word.
    Returns (is_match, matched_word, distance)
    Uses moderate strictness to balance safety vs false positives.
    """
    word_normalized = normalize_leetspeak(word)
    
    # Skip very short words to avoid false positives
    if len(word_normalized) < 3:
        return (False, None, -1)
    
    for blocked in blocked_words:
        blocked_normalized = blocked.lower()
        
        # Skip if word lengths are too different (prevents "cute" matching "execute")
        length_diff = abs(len(word_normalized) - len(blocked_normalized))
        if length_diff > 2:
            continue
        
        # Exact match after normalization
        if word_normalized == blocked_normalized:
            return (True, blocked, 0)
        
        # Check if blocked word equals word with prefix/suffix (but not arbitrary containment)
        # This prevents "hello" matching "hell" but allows "shitty" matching "shit"
        if len(blocked_normalized) >= 4:
            # Word starts with blocked word and only has 1-2 extra chars
            if word_normalized.startswith(blocked_normalized) and len(word_normalized) - len(blocked_normalized) <= 2:
                return (True, blocked, 0)
            # Word ends with blocked word and only has 1-2 extra chars  
            if word_normalized.endswith(blocked_normalized) and len(word_normalized) - len(blocked_normalized) <= 2:
                return (True, blocked, 0)
        
        # Calculate Levenshtein distance
        distance = levenshtein_distance(word_normalized, blocked_normalized)
        
        # For very short words (3-4 chars), only allow distance of 1 and same length
        if len(blocked_normalized) <= 4:
            if distance == 1 and length_diff <= 1:
                return (True, blocked, distance)
        # For medium words (5-6 chars), allow distance of 1-2 with similar length
        elif len(blocked_normalized) <= 6:
            if distance <= 1 and length_diff <= 1:
                return (True, blocked, distance)
        # For longer words, use proportional distance
        else:
            effective_max_distance = min(max_distance, max(1, len(blocked_normalized) // 4))
            if distance <= effective_max_distance and length_diff <= 2:
                return (True, blocked, distance)
    
    return (False, None, -1)

def check_profanity(text: str) -> dict:
    """
    Check text for profanity with fuzzy matching support.
    Handles misspellings, leetspeak, and character substitutions.
    Uses moderate strictness to balance safety vs false positives.
    """
    text_lower = text.lower()
    text_normalized = normalize_leetspeak(text_lower)
    matched = []
    fuzzy_matched = []
    
    # Common safe words that might trigger false positives
    SAFE_WORDS = {
        'shell', 'classic', 'classics', 'class', 'assassin', 'assess', 'assistant',
        'associate', 'assume', 'assignment', 'passionate', 'compass',
        'assault', 'grass', 'glass', 'pass', 'mass', 'bass', 'brass',
        'cocktail', 'peacock', 'hancock', 'woodcock', 'shuttlecock',
        'scunthorpe', 'hello', 'shell', 'shelling', 'shellfish',
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
        'database', 'dabble', 'dab'  # 'dab' as drug slang only in specific contexts
    }

    words_in_text = re.findall(r'\b[a-z0-9@$!#%^&*]+\b', text_lower)
    words_normalized = re.findall(r'\b[a-z0-9]+\b', text_normalized)

    # Combine unique words found in the message
    all_input_words = set(words_in_text + words_normalized)
    
    # # Extract words from text (split by whitespace and common punctuation)
    # words = re.findall(r'[a-zA-Z0-9@$!#%^&*]+', text_lower)
    
    # # Also check the normalized version
    # words_normalized = re.findall(r'[a-z]+', text_normalized)
    
    # all_words = set(words + words_normalized)
    
    # for word in all_words:
    #     # Skip very short words
    #     if len(word) < 3:
    #         continue

    for word in all_input_words:
        if len(word) < 3:
            continue
        
        # # Skip known safe words
        # if word.lower() in SAFE_WORDS:
        #     continue
        if word in SAFE_WORDS:
            continue
            
        # word_normalized = normalize_leetspeak(word)
        
        # # Skip if normalized word is a safe word
        # if word_normalized in SAFE_WORDS:
        #     continue
        
        # word_matched = False

        for blocked in BLOCKED_WORDS:
            blocked_lower = blocked.lower()

            if word == blocked_lower:
                if blocked not in matched:
                    matched.append(blocked)
                break

            if len(blocked_lower) >= 4 and word.startswith(blocked_lower):
                suffix = word[len(blocked_lower):]
                if suffix in ['', 's', 'es', 'ed', 'er', 'ing', 'y']:
                    if blocked not in matched:
                        matched.append(blocked)
                    break
        
        # for blocked in BLOCKED_WORDS:
        #     blocked_lower = blocked.lower()


            
            # # Skip if word lengths are too different
            # length_diff = abs(len(word_normalized) - len(blocked_lower))
            # if length_diff > 3:
            #     continue
            
            # # Exact match (highest priority)
            # if word_normalized == blocked_lower or word.lower() == blocked_lower:
            #     if blocked not in matched:
            #         matched.append(blocked)
            #     word_matched = True
            #     break
            
            # # Word is a variant with suffix (e.g., "fucking" matches "fuck")
            # # Require the blocked word to be at least 4 chars and be significant portion
            # if len(blocked_lower) >= 4:
            #     if word_normalized.startswith(blocked_lower):
            #         extra_chars = len(word_normalized) - len(blocked_lower)
            #         # Only allow common suffixes (ing, ed, er, s, y, ly)
            #         if extra_chars <= 3:
            #             suffix = word_normalized[len(blocked_lower):]
            #             if suffix in ['', 's', 'y', 'ed', 'er', 'ing', 'ly', 'ish', 'ness']:
            #                 if blocked not in matched:
            #                     matched.append(blocked)
            #                 word_matched = True
            #                 break
            
            # Check for leetspeak variations with 1 char difference (for short words)
            if len(blocked_lower) <= 5 and len(word_normalized) <= 6 and length_diff <= 1:
                dist = levenshtein_distance(word_normalized, blocked_lower)
                if dist == 1:
                    if blocked not in matched:
                        matched.append(blocked)
                    word_matched = True
                    break
        
        # Fuzzy match if no exact/near-exact match found
        # if not word_matched:
        #     is_match, blocked_word, distance = fuzzy_match_word(word, BLOCKED_WORDS, max_distance=2)
        #     if is_match and blocked_word not in matched and blocked_word not in fuzzy_matched:
        #         # Double check it's not a safe word being matched
        #         if word.lower() not in SAFE_WORDS and word_normalized not in SAFE_WORDS:
        #             fuzzy_matched.append(blocked_word)3

        if blocked_lower not in matched:
            is_match, blocked_word, distance = fuzzy_match_word(word, BLOCKED_WORDS, max_distance=1)
            if is_match and blocked_word not in matched:
                # Extra safety: Ensure the word length is nearly identical
                if abs(len(word) - len(blocked_word)) <= 1:
                    fuzzy_matched.append(blocked_word)
    
    # Combine results
    all_matched = matched + fuzzy_matched
    
    # Get categories for matched words
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
    Check text for restricted topics with fuzzy matching support.
    Prioritizes phrase matching before individual word matching.
    """
    text_lower = text.lower()
    text_normalized = normalize_leetspeak(text_lower)
    flagged = {}
    
    # Priority order for categories (self_harm should be checked first for phrases like "want to die")
    category_priority = ["self_harm", "violence", "adult_content", "substance", 
                         "cyberbullying", "hate_speech", "dangerous_activities", "privacy"]
    
    # First pass: Check for multi-word phrases (higher priority)
    for category in category_priority:
        if category not in RESTRICTED_TOPICS:
            continue
        phrases = RESTRICTED_TOPICS[category]
        matches = []
        for phrase in phrases:
            phrase_lower = phrase.lower()
            
            # Multi-word phrase matching (highest priority)
            if ' ' in phrase_lower:
                if phrase_lower in text_lower or phrase_lower in text_normalized:
                    if phrase not in matches:
                        matches.append(phrase)
        
        if matches:
            flagged[category] = matches
    
    # Second pass: Check for single words with fuzzy matching
    for category in category_priority:
        if category not in RESTRICTED_TOPICS:
            continue
        phrases = RESTRICTED_TOPICS[category]
        matches = flagged.get(category, [])
        
        for phrase in phrases:
            phrase_lower = phrase.lower()
            
            # Skip multi-word phrases (already handled above)
            if ' ' in phrase_lower:
                continue
            
            # Check exact single word match
            if phrase_lower in text_lower or phrase_lower in text_normalized:
                if phrase not in matches:
                    matches.append(phrase)
                continue
            
            # For single words, do fuzzy matching
            if len(phrase) >= 3:
                words = re.findall(r'[a-zA-Z0-9@$!#%^&*]+', text_lower)
                for word in words:
                    is_match, _, _ = fuzzy_match_word(word, [phrase], max_distance=2)
                    if is_match and phrase not in matches:
                        matches.append(phrase)
                        break
        
        if matches:
            flagged[category] = matches
    
    return flagged


# ============================================================
# REACT SYSTEM PROMPT
# ============================================================
REACT_SYSTEM_PROMPT = """You are BuddyBot, a warm, friendly, and safe AI companion for children aged 5-12. You speak in simple, encouraging language.

IMPORTANT: You must ALWAYS follow this ReAct thinking pattern internally before every response:

**THOUGHT**: First, analyze the child's message for safety. Consider:
- Is there any inappropriate content?
- Is the child sharing personal information?
- Is the child expressing distress or unsafe situations?
- What's the emotional tone?
- Consider the child's recent browsing history if provided

**SAFETY_LEVEL**: Rate as SAFE, CAUTION, or ALERT

**RESPONSE**: Then compose your response following these rules:
1. Always be kind, encouraging, and age-appropriate
2. Use simple words a 5-year-old can understand
3. If asked about restricted topics, gently redirect to fun alternatives
4. If a child seems sad or scared, be comforting and suggest talking to a trusted adult
5. Never provide personal information or encourage sharing personal details
6. Keep responses SHORT (2-4 sentences max)

You MUST format your response EXACTLY like this:
[THOUGHT] Your safety analysis here
[SAFETY] SAFE or CAUTION or ALERT
[RESPONSE] Your child-friendly response here"""


def parse_react_response(raw_response: str) -> dict:
    thought = ""
    safety_level = "SAFE"
    response = ""
    thought_match = re.search(r'\[THOUGHT\]\s*(.*?)(?=\[SAFETY\])', raw_response, re.DOTALL)
    safety_match = re.search(r'\[SAFETY\]\s*(SAFE|CAUTION|ALERT)', raw_response, re.DOTALL)
    response_match = re.search(r'\[RESPONSE\]\s*(.*?)$', raw_response, re.DOTALL)
    if thought_match: thought = thought_match.group(1).strip()
    if safety_match: safety_level = safety_match.group(1).strip()
    if response_match: response = response_match.group(1).strip()
    if not response:
        response = raw_response.strip()
        thought = "Unable to parse structured response"
        safety_level = "CAUTION"
    return {"thought": thought, "safety_level": safety_level, "response": response}


async def get_browsing_context(device_id: str = None) -> str:
    if not device_id:
        latest = await db.browsing_packets.find_one({}, {"_id": 0, "device_id": 1}, sort=[("timestamp", -1)])
        if latest: device_id = latest["device_id"]
        else: return ""
    recent_searches = await db.browsing_packets.find(
        {"device_id": device_id, "packet_type": "search_query"}, {"_id": 0, "search_query": 1, "search_engine": 1, "timestamp": 1, "tab_type": 1}
    ).sort("timestamp", -1).to_list(20)
    if not recent_searches: return ""
    context_parts = ["\n[BROWSING CONTEXT]:"]
    for s in recent_searches[:10]:
        mode = " (INCOGNITO)" if s.get("tab_type") == "incognito" else ""
        context_parts.append(f"  - \"{s['search_query']}\" on {s.get('search_engine', 'unknown')}{mode}")
    return "\n".join(context_parts)


# ============================================================
# AUTH ENDPOINTS
# ============================================================
@api_router.post("/auth/register")
async def register(data: RegisterRequest, response: Response):
    email = data.email.lower().strip()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user_doc = {
        "user_id": user_id,
        "name": data.name,
        "email": email,
        "phone": data.phone or "",
        "password_hash": hash_password(data.password),
        "auth_provider": "email",
        "role": "parent",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)

    # Create default child profile
    child_id = f"child_{uuid.uuid4().hex[:12]}"
    child_doc = {
        "child_id": child_id,
        "parent_id": user_id,
        "name": f"{data.name}'s Child",
        "age": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.child_profiles.insert_one(child_doc)

    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "user_id": user_id,
        "name": data.name,
        "email": email,
        "phone": data.phone or "",
        "role": "parent",
        "child_id": child_id,
        "token": access_token,
    }


@api_router.post("/auth/login")
async def login(data: LoginRequest, response: Response):
    email = data.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="This account uses Google login. Please sign in with Google.")
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user["user_id"], email)
    refresh_token = create_refresh_token(user["user_id"])
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": email,
        "phone": user.get("phone", ""),
        "role": user.get("role", "parent"),
        "token": access_token,
    }


@api_router.post("/auth/google")
async def google_auth(data: GoogleSessionRequest, response: Response):
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
    existing = await db.users.find_one({"email": email}, {"_id": 0})

    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {
            "name": google_data.get("name", existing["name"]),
            "picture": google_data.get("picture", ""),
        }})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user_doc = {
            "user_id": user_id,
            "name": google_data.get("name", "Parent"),
            "email": email,
            "phone": "",
            "password_hash": None,
            "auth_provider": "google",
            "picture": google_data.get("picture", ""),
            "role": "parent",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)

        child_id = f"child_{uuid.uuid4().hex[:12]}"
        child_doc = {
            "child_id": child_id,
            "parent_id": user_id,
            "name": f"{google_data.get('name', 'Parent')}'s Child",
            "age": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.child_profiles.insert_one(child_doc)

    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token)

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    user.pop("password_hash", None)

    return {
        "user_id": user_id,
        "name": user.get("name"),
        "email": email,
        "phone": user.get("phone", ""),
        "role": user.get("role", "parent"),
        "token": access_token,
    }


@api_router.get("/auth/me")
async def auth_me(request: Request):
    user = await get_current_user(request)
    children = await db.child_profiles.find({"parent_id": user["user_id"]}, {"_id": 0}).to_list(20)
    user["children"] = children
    return user


@api_router.post("/auth/verify-password")
async def verify_pwd(data: VerifyPasswordRequest, request: Request):
    """Re-verify password for parent dashboard access."""
    user = await get_current_user(request)
    full_user = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not full_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not full_user.get("password_hash"):
        # Google auth users - always allow dashboard access
        return {"verified": True}
    if not verify_password(data.password, full_user["password_hash"]):
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
async def list_children(request: Request):
    user = await get_current_user(request)
    children = await db.child_profiles.find({"parent_id": user["user_id"]}, {"_id": 0}).to_list(20)
    return children


@api_router.post("/children")
async def create_child(data: ChildProfileCreate, request: Request):
    user = await get_current_user(request)
    child_id = f"child_{uuid.uuid4().hex[:12]}"
    doc = {
        "child_id": child_id,
        "parent_id": user["user_id"],
        "name": data.name,
        "age": data.age,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.child_profiles.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ============================================================
# CHAT ENDPOINTS
# ============================================================
@api_router.post("/chat/conversations")
async def create_conversation(data: ConversationCreate):
    conv_id = str(uuid.uuid4())
    doc = {
        "id": conv_id, "title": data.title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "message_count": 0, "has_flags": False, "flag_count": 0
    }
    await db.conversations.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.get("/chat/conversations")
async def list_conversations():
    convs = await db.conversations.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return convs


@api_router.get("/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await db.messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return {"conversation": conv, "messages": messages}


@api_router.post("/chat/send")
async def send_message(data: MessageCreate):
    if not data.conversation_id:
        conv_id = str(uuid.uuid4())
        title = data.text[:40] + ("..." if len(data.text) > 40 else "")
        conv_doc = {
            "id": conv_id, "title": title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message_count": 0, "has_flags": False, "flag_count": 0,
            "child_id": data.child_id
        }
        await db.conversations.insert_one(conv_doc)
        data.conversation_id = conv_id

    conversation_id = data.conversation_id

    # Profanity check
    profanity_result = check_profanity(data.text)
    if profanity_result["is_blocked"]:
        user_msg = {
            "id": str(uuid.uuid4()), "conversation_id": conversation_id,
            "role": "user", "text": data.text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "blocked": True, "blocked_words": profanity_result["matched_words"]
        }
        await db.messages.insert_one(user_msg)
        user_msg.pop("_id", None)

        # Build detailed alert with categories
        categories_str = ""
        if profanity_result.get("categories"):
            categories_str = f" Categories: {', '.join(profanity_result['categories'].keys())}."
        fuzzy_note = ""
        if profanity_result.get("fuzzy_matched"):
            fuzzy_note = f" (Fuzzy matches detected: {', '.join(profanity_result['fuzzy_matched'])})"
        
        alert_doc = {
            "id": str(uuid.uuid4()), "conversation_id": conversation_id,
            "message_id": user_msg["id"], "type": "profanity", "severity": "high",
            "details": f"Blocked words detected: {', '.join(profanity_result['matched_words'])}.{categories_str}{fuzzy_note}",
            "child_message": data.text,
            "categories": profanity_result.get("categories", {}),
            "fuzzy_matched": profanity_result.get("fuzzy_matched", []),
            "created_at": datetime.now(timezone.utc).isoformat(), "resolved": False
        }
        await db.alerts.insert_one(alert_doc)
        alert_doc.pop("_id", None)

        # Send email alert to parent
        asyncio.create_task(notify_parent_of_alert(alert_doc, data.child_id))

        await db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {"has_flags": True, "updated_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"message_count": 1, "flag_count": 1}}
        )

        bot_msg = {
            "id": str(uuid.uuid4()), "conversation_id": conversation_id,
            "role": "assistant",
            "text": "Hmm, let's use kind and friendly words! How about we talk about something fun instead? What's your favorite animal?",
            "thought": "Profanity filter triggered. Blocked words detected in child's message.",
            "safety_level": "ALERT",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.messages.insert_one(bot_msg)
        bot_msg.pop("_id", None)
        await db.conversations.update_one({"id": conversation_id}, {"$inc": {"message_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})

        return {"conversation_id": conversation_id, "user_message": user_msg, "bot_message": bot_msg, "blocked": True, "alert": alert_doc}

    restricted = check_restricted_topics(data.text)

    user_msg = {
        "id": str(uuid.uuid4()), "conversation_id": conversation_id,
        "role": "user", "text": data.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blocked": False, "flagged_topics": restricted if restricted else None
    }
    await db.messages.insert_one(user_msg)
    user_msg.pop("_id", None)

    history = await db.messages.find(
        {"conversation_id": conversation_id, "role": {"$in": ["user", "assistant"]}, "blocked": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", 1).to_list(20)

    context_parts = []
    for msg in history[:-1]:
        if msg["role"] == "user": context_parts.append(f"Child: {msg['text']}")
        else: context_parts.append(f"BuddyBot: {msg['text']}")
    context_str = "\n".join(context_parts[-10:])

    browsing_context = await get_browsing_context(data.device_id)
    extra_context = ""
    if restricted:
        extra_context = f"\n\n[SYSTEM NOTE: Restricted topics detected: {restricted}. Redirect gently.]"

    prefix = f"Previous conversation:\n{context_str}\n\n" if context_str else ""
    full_prompt = f"{prefix}Child's message: {data.text}{extra_context}{browsing_context}"

    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"buddy-{conversation_id}-{uuid.uuid4().hex[:8]}", system_message=REACT_SYSTEM_PROMPT)
        chat.with_model("openai", "gpt-4.1-mini")
        raw_response = await chat.send_message(UserMessage(text=full_prompt))
        parsed = parse_react_response(raw_response)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        parsed = {"thought": f"LLM call failed: {str(e)}", "safety_level": "CAUTION", "response": "Oops! My brain got a little fuzzy for a second. Can you say that again?"}

    if parsed["safety_level"] == "ALERT" or restricted:
        severity = "high" if parsed["safety_level"] == "ALERT" else "medium"
        alert_doc = {
            "id": str(uuid.uuid4()), "conversation_id": conversation_id,
            "message_id": user_msg["id"], "type": "restricted_topic", "severity": severity,
            "details": f"Safety Level: {parsed['safety_level']}. Topics: {restricted if restricted else 'AI flagged'}. AI Thought: {parsed['thought'][:200]}",
            "child_message": data.text,
            "created_at": datetime.now(timezone.utc).isoformat(), "resolved": False
        }
        await db.alerts.insert_one(alert_doc)
        alert_doc.pop("_id", None)
        asyncio.create_task(notify_parent_of_alert(alert_doc, data.child_id))
        await db.conversations.update_one({"id": conversation_id}, {"$set": {"has_flags": True, "updated_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"flag_count": 1}})

    bot_msg = {
        "id": str(uuid.uuid4()), "conversation_id": conversation_id,
        "role": "assistant", "text": parsed["response"],
        "thought": parsed["thought"], "safety_level": parsed["safety_level"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.messages.insert_one(bot_msg)
    bot_msg.pop("_id", None)
    await db.conversations.update_one({"id": conversation_id}, {"$inc": {"message_count": 2}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})

    return {"conversation_id": conversation_id, "user_message": user_msg, "bot_message": bot_msg, "blocked": False}


# ============================================================
# EXTENSION ENDPOINTS
# ============================================================
@api_router.post("/extension/packets")
async def receive_packets(batch: PacketBatch):
    if not batch.packets:
        return {"status": "ok", "received": 0}
    docs = []
    alerts_to_create = []
    for packet in batch.packets:
        doc = packet.model_dump()
        doc["synced_at"] = datetime.now(timezone.utc).isoformat()
        if packet.packet_type == "search_query" and packet.search_query:
            profanity = check_profanity(packet.search_query)
            restricted = check_restricted_topics(packet.search_query)
            doc["profanity_flagged"] = profanity["is_blocked"]
            doc["profanity_words"] = profanity["matched_words"]
            doc["profanity_categories"] = profanity.get("categories", {})
            doc["fuzzy_matched"] = profanity.get("fuzzy_matched", [])
            doc["restricted_topics"] = restricted if restricted else None
            if profanity["is_blocked"] or restricted:
                severity = "high" if profanity["is_blocked"] else "medium"
                
                # Build detailed alert message
                categories_info = ""
                if profanity.get("categories"):
                    categories_info = f" | Categories: {', '.join(profanity['categories'].keys())}"
                fuzzy_info = ""
                if profanity.get("fuzzy_matched"):
                    fuzzy_info = f" | Fuzzy matches: {profanity['fuzzy_matched']}"
                
                alert = {
                    "id": str(uuid.uuid4()), "type": "browsing_alert", "severity": severity,
                    "device_id": batch.device_id,
                    "details": f"Flagged search: \"{packet.search_query}\" on {packet.search_engine or 'browser'}{categories_info}{fuzzy_info}",
                    "child_message": packet.search_query, "tab_type": packet.tab_type,
                    "url": packet.url, "created_at": datetime.now(timezone.utc).isoformat(),
                    "resolved": False, "source": "extension",
                    "categories": profanity.get("categories", {}),
                    "fuzzy_matched": profanity.get("fuzzy_matched", [])
                }
                if restricted: alert["details"] += f" | Topics: {list(restricted.keys())}"
                if profanity["is_blocked"] and not categories_info: alert["details"] += f" | Blocked words: {profanity['matched_words']}"
                alerts_to_create.append(alert)
        docs.append(doc)
    if docs:
        await db.browsing_packets.insert_many(docs)
    if alerts_to_create:
        await db.alerts.insert_many(alerts_to_create)
        for alert in alerts_to_create:
            alert.pop("_id", None)
            asyncio.create_task(notify_parent_of_alert(alert))
    return {"status": "ok", "received": len(docs), "alerts_created": len(alerts_to_create)}


@api_router.get("/extension/status/{device_id}")
async def extension_status(device_id: str):
    packet_count = await db.browsing_packets.count_documents({"device_id": device_id})
    last_packet = await db.browsing_packets.find_one({"device_id": device_id}, {"_id": 0, "timestamp": 1}, sort=[("timestamp", -1)])
    alert_count = await db.alerts.count_documents({"device_id": device_id, "source": "extension"})
    return {"device_id": device_id, "total_packets": packet_count, "last_activity": last_packet["timestamp"] if last_packet else None, "total_alerts": alert_count}


# ============================================================
# PARENT DASHBOARD ENDPOINTS (Auth required)
# ============================================================
@api_router.get("/parent/dashboard")
async def parent_dashboard(request: Request):
    await get_current_user(request)
    total_conversations = await db.conversations.count_documents({})
    total_messages = await db.messages.count_documents({})
    total_alerts = await db.alerts.count_documents({})
    unresolved_alerts = await db.alerts.count_documents({"resolved": False})
    flagged_conversations = await db.conversations.count_documents({"has_flags": True})
    total_packets = await db.browsing_packets.count_documents({})
    browsing_alerts = await db.alerts.count_documents({"source": "extension"})
    incognito_count = await db.browsing_packets.count_documents({"tab_type": "incognito"})
    recent_alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(10)
    return {
        "stats": {
            "total_conversations": total_conversations, "total_messages": total_messages,
            "total_alerts": total_alerts, "unresolved_alerts": unresolved_alerts,
            "flagged_conversations": flagged_conversations, "total_packets": total_packets,
            "browsing_alerts": browsing_alerts, "incognito_searches": incognito_count
        },
        "recent_alerts": recent_alerts
    }


@api_router.get("/parent/alerts")
async def get_alerts(request: Request, resolved: Optional[bool] = None):
    await get_current_user(request)
    query = {}
    if resolved is not None: query["resolved"] = resolved
    return await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.put("/parent/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, request: Request):
    await get_current_user(request)
    result = await db.alerts.update_one({"id": alert_id}, {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()}})
    if result.matched_count == 0: raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "resolved", "alert_id": alert_id}


@api_router.get("/parent/conversations")
async def parent_conversations(request: Request):
    await get_current_user(request)
    return await db.conversations.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)


@api_router.get("/parent/conversations/{conversation_id}")
async def parent_conversation_detail(conversation_id: str, request: Request):
    await get_current_user(request)
    conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv: raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await db.messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    alerts = await db.alerts.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"conversation": conv, "messages": messages, "alerts": alerts}


@api_router.get("/parent/browsing/stats")
async def browsing_stats(request: Request):
    await get_current_user(request)
    return {
        "total_packets": await db.browsing_packets.count_documents({}),
        "search_count": await db.browsing_packets.count_documents({"packet_type": "search_query"}),
        "visit_count": await db.browsing_packets.count_documents({"packet_type": "url_visit"}),
        "incognito_count": await db.browsing_packets.count_documents({"tab_type": "incognito"}),
        "flagged_searches": await db.browsing_packets.count_documents({"profanity_flagged": True}),
        "browsing_alerts": await db.alerts.count_documents({"source": "extension"}),
        "devices": await db.browsing_packets.distinct("device_id")
    }


@api_router.get("/parent/browsing/searches")
async def browsing_searches(request: Request, device_id: Optional[str] = None, limit: int = 50):
    await get_current_user(request)
    query = {"packet_type": "search_query"}
    if device_id: query["device_id"] = device_id
    return await db.browsing_packets.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)


@api_router.get("/parent/browsing/visits")
async def browsing_visits(request: Request, device_id: Optional[str] = None, limit: int = 50):
    await get_current_user(request)
    query = {"packet_type": "url_visit"}
    if device_id: query["device_id"] = device_id
    return await db.browsing_packets.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)


@api_router.get("/parent/browsing/analysis")
async def browsing_analysis(request: Request, device_id: Optional[str] = None):
    await get_current_user(request)
    if not device_id:
        latest = await db.browsing_packets.find_one({}, {"_id": 0, "device_id": 1}, sort=[("timestamp", -1)])
        if latest: device_id = latest["device_id"]
        else: return {"safety_level": "SAFE", "analysis": "No browsing data available", "concerns": []}

    recent_searches = await db.browsing_packets.find({"device_id": device_id, "packet_type": "search_query"}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    concerns = []
    for search in recent_searches:
        query = search.get("search_query", "")
        topics = check_restricted_topics(query)
        profanity = check_profanity(query)
        if topics or profanity["is_blocked"]:
            concerns.append({"query": query, "topics": topics, "profanity": profanity["matched_words"], "tab_type": search.get("tab_type", "normal"), "timestamp": search.get("timestamp"), "search_engine": search.get("search_engine")})

    return {
        "safety_level": "ALERT" if len(concerns) > 3 else ("CAUTION" if concerns else "SAFE"),
        "analysis": f"{len(concerns)} concerning searches found out of {len(recent_searches)} total." if concerns else "No concerning patterns detected.",
        "positive": "Child shows healthy interest in educational topics." if len(recent_searches) > len(concerns) * 3 else "",
        "flagged_searches": concerns,
        "total_searches": len(recent_searches),
        "total_visits": await db.browsing_packets.count_documents({"device_id": device_id, "packet_type": "url_visit"}),
        "incognito_count": len([s for s in recent_searches if s.get("tab_type") == "incognito"])
    }


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


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
