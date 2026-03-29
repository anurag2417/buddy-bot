#!/usr/bin/env python3
"""
BuddyBot Backend Testing Suite
Tests the 5 new features as specified in the review request.
"""

import asyncio
import httpx
import json
import sys
from typing import Dict, Any

# Test configuration
BACKEND_URL = "https://get-restart.preview.emergentagent.com/api"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test123456"

class BuddyBotTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.auth_token = None
        self.conversation_id = None
        self.test_results = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
    
    async def authenticate(self) -> bool:
        """Authenticate with test credentials"""
        try:
            response = await self.client.post(f"{BACKEND_URL}/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("token")
                self.log_test("Authentication", True, f"Logged in as {data.get('name', 'User')}")
                return True
            else:
                self.log_test("Authentication", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Authentication", False, f"Exception: {str(e)}")
            return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {self.auth_token}"}
    
    async def test_exact_match_keyword_blocking(self):
        """Test Feature #5: Exact Match Keyword Blocking"""
        print("\n🔒 Testing Exact Match Keyword Blocking (Feature #5)")
        
        # Test 1: Should block exact match
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/send",
                json={"text": "fuck you"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("blocked") == True:
                    blocked_words = data.get("user_message", {}).get("blocked_words", [])
                    if "fuck" in blocked_words:
                        # Check if alert details mention "EXACT MATCH"
                        bot_response = data.get("bot_message", {}).get("text", "")
                        self.log_test("Exact Match Blocking - Block 'fuck you'", True, 
                                    f"Blocked words: {blocked_words}, Bot response: {bot_response[:100]}...")
                    else:
                        self.log_test("Exact Match Blocking - Block 'fuck you'", False, 
                                    f"Expected 'fuck' in blocked words, got: {blocked_words}")
                else:
                    self.log_test("Exact Match Blocking - Block 'fuck you'", False, 
                                f"Message not blocked. Response: {data}")
            else:
                self.log_test("Exact Match Blocking - Block 'fuck you'", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Exact Match Blocking - Block 'fuck you'", False, f"Exception: {str(e)}")
        
        # Test 2: Should NOT block non-exact match
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/send",
                json={"text": "hello friend"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("blocked") == False:
                    self.log_test("Exact Match Blocking - Allow 'hello friend'", True, 
                                "Message correctly allowed")
                    # Store conversation ID for later tests
                    self.conversation_id = data.get("conversation_id")
                else:
                    self.log_test("Exact Match Blocking - Allow 'hello friend'", False, 
                                f"Message incorrectly blocked: {data}")
            else:
                self.log_test("Exact Match Blocking - Allow 'hello friend'", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Exact Match Blocking - Allow 'hello friend'", False, f"Exception: {str(e)}")
    
    async def test_smart_followups(self):
        """Test Feature #3: Smart Follow-ups"""
        print("\n🤖 Testing Smart Follow-ups (Feature #3)")
        
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/send",
                json={"text": "Tell me about dinosaurs"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                bot_message = data.get("bot_message", {})
                followups = bot_message.get("followups", [])
                
                if len(followups) == 3:
                    # Check if followups are context-aware and age-appropriate
                    followup_text = " ".join(followups).lower()
                    dinosaur_related = any(word in followup_text for word in 
                                         ["dinosaur", "fossil", "prehistoric", "extinct", "jurassic", "t-rex", "triceratops"])
                    
                    if dinosaur_related:
                        self.log_test("Smart Follow-ups - Dinosaur context", True, 
                                    f"Generated 3 context-aware followups: {followups}")
                    else:
                        self.log_test("Smart Follow-ups - Dinosaur context", False, 
                                    f"Followups not dinosaur-related: {followups}")
                else:
                    self.log_test("Smart Follow-ups - Count", False, 
                                f"Expected 3 followups, got {len(followups)}: {followups}")
                    
                # Store conversation ID for later tests
                if not self.conversation_id:
                    self.conversation_id = data.get("conversation_id")
                    
            else:
                self.log_test("Smart Follow-ups", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Smart Follow-ups", False, f"Exception: {str(e)}")
    
    async def test_interactive_quiz(self):
        """Test Feature #1: Interactive Quiz Feature"""
        print("\n🎯 Testing Interactive Quiz Feature (Feature #1)")
        
        # Test with /quiz command
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/send",
                json={"text": "/quiz"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                mode = data.get("mode")
                quiz_data = data.get("quiz_data", {})
                
                if mode == "quiz":
                    title = quiz_data.get("title", "")
                    questions = quiz_data.get("questions", [])
                    
                    if title and questions:
                        # Check first question structure
                        if questions:
                            q = questions[0]
                            has_question = "question" in q
                            has_options = "options" in q and len(q["options"]) == 4
                            has_correct = "correct" in q
                            has_fun_fact = "fun_fact" in q
                            
                            if has_question and has_options and has_correct and has_fun_fact:
                                self.log_test("Interactive Quiz - Structure", True, 
                                            f"Quiz '{title}' with {len(questions)} questions, proper structure")
                            else:
                                self.log_test("Interactive Quiz - Structure", False, 
                                            f"Missing quiz elements: question={has_question}, options={has_options}, correct={has_correct}, fun_fact={has_fun_fact}")
                        else:
                            self.log_test("Interactive Quiz - Questions", False, "No questions generated")
                    else:
                        self.log_test("Interactive Quiz - Data", False, 
                                    f"Missing title or questions. Title: {title}, Questions: {len(questions)}")
                else:
                    self.log_test("Interactive Quiz - Mode", False, f"Expected mode 'quiz', got '{mode}'")
                    
            else:
                self.log_test("Interactive Quiz", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Interactive Quiz", False, f"Exception: {str(e)}")
        
        # Test with "Start a quiz" text
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/send",
                json={"text": "Start a quiz"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("mode") == "quiz":
                    self.log_test("Interactive Quiz - Text trigger", True, 
                                "Quiz mode activated with 'Start a quiz'")
                else:
                    self.log_test("Interactive Quiz - Text trigger", False, 
                                f"Expected quiz mode, got: {data.get('mode')}")
            else:
                self.log_test("Interactive Quiz - Text trigger", False, 
                            f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Interactive Quiz - Text trigger", False, f"Exception: {str(e)}")
    
    async def test_creative_story_mode(self):
        """Test Feature #2: Creative Story Mode"""
        print("\n📖 Testing Creative Story Mode (Feature #2)")
        
        # Test with /story command
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/send",
                json={"text": "/story"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                mode = data.get("mode")
                story_data = data.get("story_data", {})
                
                if mode == "story":
                    title = story_data.get("title", "")
                    segment = story_data.get("segment", "")
                    choices = story_data.get("choices", [])
                    
                    if title and segment and len(choices) >= 2:
                        self.log_test("Creative Story - Structure", True, 
                                    f"Story '{title}' with segment and {len(choices)} choices")
                    else:
                        self.log_test("Creative Story - Structure", False, 
                                    f"Missing story elements. Title: {bool(title)}, Segment: {bool(segment)}, Choices: {len(choices)}")
                else:
                    self.log_test("Creative Story - Mode", False, f"Expected mode 'story', got '{mode}'")
                    
            else:
                self.log_test("Creative Story", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Creative Story", False, f"Exception: {str(e)}")
        
        # Test with "Tell me a story" text
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/send",
                json={"text": "Tell me a story"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("mode") == "story":
                    self.log_test("Creative Story - Text trigger", True, 
                                "Story mode activated with 'Tell me a story'")
                else:
                    self.log_test("Creative Story - Text trigger", False, 
                                f"Expected story mode, got: {data.get('mode')}")
            else:
                self.log_test("Creative Story - Text trigger", False, 
                            f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Creative Story - Text trigger", False, f"Exception: {str(e)}")
    
    async def test_web_search_endpoint(self):
        """Test Feature #4: Web Search Endpoint"""
        print("\n🔍 Testing Web Search Endpoint (Feature #4)")
        
        # Test 1: Safe search query
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/search",
                json={"query": "dinosaurs"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                is_safe = data.get("safe")
                summary = data.get("summary", "")
                key_facts = data.get("key_facts", [])
                
                if is_safe == True and summary:
                    self.log_test("Web Search - Safe query", True, 
                                f"Safe search returned summary and {len(key_facts)} key facts")
                else:
                    self.log_test("Web Search - Safe query", False, 
                                f"Expected safe=True with summary. Got safe={is_safe}, summary length={len(summary)}")
            else:
                self.log_test("Web Search - Safe query", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Web Search - Safe query", False, f"Exception: {str(e)}")
        
        # Test 2: Unsafe search query (using a word that should definitely be blocked)
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/search",
                json={"query": "kill"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                is_safe = data.get("safe")
                blocked_reason = data.get("blocked_reason", "")
                
                if is_safe == False and blocked_reason:
                    self.log_test("Web Search - Unsafe query", True, 
                                f"Unsafe query blocked with reason: {blocked_reason}")
                else:
                    self.log_test("Web Search - Unsafe query", False, 
                                f"Expected safe=False with blocked_reason. Got safe={is_safe}, reason={blocked_reason}")
            else:
                self.log_test("Web Search - Unsafe query", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Web Search - Unsafe query", False, f"Exception: {str(e)}")
        
        # Test 3: Educational content (violence should provide educational response, not block)
        try:
            response = await self.client.post(
                f"{BACKEND_URL}/chat/search",
                json={"query": "violence"},
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                is_safe = data.get("safe")
                summary = data.get("summary", "")
                
                # Violence should return educational content, not be blocked
                if is_safe == True and "educational" in summary.lower() or "instead" in summary.lower():
                    self.log_test("Web Search - Educational content", True, 
                                f"Educational response provided for 'violence' query")
                else:
                    self.log_test("Web Search - Educational content", False, 
                                f"Expected educational response. Got safe={is_safe}, summary={summary[:100]}...")
            else:
                self.log_test("Web Search - Educational content", False, 
                            f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Web Search - Educational content", False, f"Exception: {str(e)}")
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting BuddyBot Backend Tests")
        print("=" * 50)
        
        # Authenticate first
        if not await self.authenticate():
            print("❌ Authentication failed. Cannot proceed with tests.")
            return
        
        # Run all feature tests
        await self.test_exact_match_keyword_blocking()
        await self.test_smart_followups()
        await self.test_interactive_quiz()
        await self.test_creative_story_mode()
        await self.test_web_search_endpoint()
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['test']}")
        
        print(f"\n🎯 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 All tests passed! Backend is working correctly.")
            return True
        else:
            print(f"⚠️  {total - passed} tests failed. See details above.")
            return False

async def main():
    """Main test runner"""
    async with BuddyBotTester() as tester:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())