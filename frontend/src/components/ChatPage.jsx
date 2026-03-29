import { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import { Send, Plus, MessageCircle, Shield, ChevronLeft, LogOut, Sparkles, BookOpen, Search, HelpCircle } from "lucide-react";
import { useAuth } from "./AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Configure axios to send credentials (cookies)
axios.defaults.withCredentials = true;

const BOT_AVATAR = "https://static.prod-images.emergentagent.com/jobs/c981f2d7-a198-4751-9292-bd3ea3733509/images/d376ea840d4cf39f522230889ca79fd1bbc7322d0f233bce72b70b50dca8ebdc.png";

export default function ChatPage() {
  const { user, logout } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentMode, setCurrentMode] = useState("chat"); // chat, quiz, story
  const [quizState, setQuizState] = useState(null);
  const [storyState, setStoryState] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const fetchConversations = useCallback(async () => {
    try {
      const token = localStorage.getItem("buddybot_token");
      const res = await axios.get(`${API}/chat/conversations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setConversations(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
    // Try to restore last active conversation
    const lastConv = localStorage.getItem("buddybot_active_conv");
    if (lastConv) {
      loadConversation(lastConv);
    }
  }, [fetchConversations]);

  const loadConversation = async (convId) => {
    try {
      const token = localStorage.getItem("buddybot_token");
      const res = await axios.get(`${API}/chat/conversations/${convId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setMessages(res.data.messages);
      setActiveConvId(convId);
      localStorage.setItem("buddybot_active_conv", convId);
      setCurrentMode("chat");
      setQuizState(null);
      setStoryState(null);
    } catch (e) {
      console.error(e);
    }
  };

  const startNewChat = () => {
    setActiveConvId(null);
    setMessages([]);
    setCurrentMode("chat");
    setQuizState(null);
    setStoryState(null);
    localStorage.removeItem("buddybot_active_conv");
    inputRef.current?.focus();
  };

  const sendMessage = async (overrideText = null) => {
    const text = overrideText || input.trim();
    if (!text) return;

    setInput("");
    setLoading(true);

    const tempUserMsg = { id: `temp-${Date.now()}`, role: "user", text, blocked: false };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const token = localStorage.getItem("buddybot_token");
      const res = await axios.post(
        `${API}/chat/send`,
        { conversation_id: activeConvId, text },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      const { conversation_id, user_message, bot_message, mode, quiz_data, story_data } = res.data;

      if (!activeConvId && conversation_id) {
        setActiveConvId(conversation_id);
        localStorage.setItem("buddybot_active_conv", conversation_id);
      }

      setCurrentMode(mode || "chat");

      // Handle quiz mode
      if (mode === "quiz" && quiz_data) {
        setQuizState({
          ...quiz_data,
          currentQuestion: 0,
          score: 0,
          answered: false
        });
      }

      // Handle story mode
      if (mode === "story" && story_data) {
        setStoryState(story_data);
      }

      // Update messages with bot response including followups
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempUserMsg.id);
        return [...filtered, user_message, { ...bot_message, followups: bot_message.followups || [] }];
      });

      fetchConversations();
    } catch (e) {
      console.error(e);
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      setLoading(false);
    }
  };

  const handleFollowupClick = (followup) => {
    setInput(followup);
    sendMessage(followup);
  };

  const handleQuizAnswer = async (answer) => {
    if (!quizState || quizState.answered) return;
    
    const currentQ = quizState.questions[quizState.currentQuestion];
    const isCorrect = answer === currentQ.correct;
    
    setQuizState(prev => ({
      ...prev,
      answered: true,
      lastAnswer: answer,
      lastCorrect: isCorrect,
      score: isCorrect ? prev.score + 1 : prev.score
    }));

    // Add feedback message
    const feedbackMsg = {
      id: `quiz-feedback-${Date.now()}`,
      role: "assistant",
      text: isCorrect 
        ? `🎉 **Correct!** Great job! ${currentQ.fun_fact}`
        : `Not quite! The correct answer was **${currentQ.correct}**. ${currentQ.fun_fact}`,
      isQuizFeedback: true
    };
    setMessages(prev => [...prev, feedbackMsg]);
  };

  const handleNextQuestion = () => {
    if (!quizState) return;
    
    const nextQ = quizState.currentQuestion + 1;
    
    if (nextQ >= quizState.questions.length) {
      // Quiz complete
      const finalMsg = {
        id: `quiz-complete-${Date.now()}`,
        role: "assistant",
        text: `🏆 **Quiz Complete!** You scored **${quizState.score + (quizState.lastCorrect ? 1 : 0)}/${quizState.total_questions}**! Great job, superstar! 🌟`,
        followups: ["Start another quiz!", "Tell me a story", "Let's talk about something else"]
      };
      setMessages(prev => [...prev, finalMsg]);
      setQuizState(null);
      setCurrentMode("chat");
    } else {
      // Next question
      const nextQuestion = quizState.questions[nextQ];
      const questionMsg = {
        id: `quiz-q${nextQ}-${Date.now()}`,
        role: "assistant",
        text: `**Question ${nextQ + 1}:** ${nextQuestion.question}\n\nA) ${nextQuestion.options.A}\nB) ${nextQuestion.options.B}\nC) ${nextQuestion.options.C}\nD) ${nextQuestion.options.D}`,
        isQuizQuestion: true
      };
      setMessages(prev => [...prev, questionMsg]);
      setQuizState(prev => ({
        ...prev,
        currentQuestion: nextQ,
        answered: false,
        lastAnswer: null,
        lastCorrect: null
      }));
    }
  };

  const handleStoryChoice = async (choiceIndex) => {
    if (!storyState) return;
    
    setLoading(true);
    try {
      const token = localStorage.getItem("buddybot_token");
      const res = await axios.post(
        `${API}/chat/story/choice`,
        { conversation_id: activeConvId, choice_index: choiceIndex },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      const { story_data, segment, choices, status } = res.data;
      
      // Add choice message
      const choiceMsg = {
        id: `story-choice-${Date.now()}`,
        role: "user",
        text: `I choose: ${storyState.choices[choiceIndex - 1]}`
      };
      
      // Add story continuation
      const storyMsg = {
        id: `story-cont-${Date.now()}`,
        role: "assistant",
        text: segment,
        isStoryContinuation: true
      };
      
      setMessages(prev => [...prev, choiceMsg, storyMsg]);
      
      if (status === "END") {
        setStoryState(null);
        setCurrentMode("chat");
        // Add ending message
        const endMsg = {
          id: `story-end-${Date.now()}`,
          role: "assistant",
          text: "🎬 **The End!** What an amazing adventure! Would you like another story?",
          followups: ["Tell me another story!", "Start a quiz", "Let's chat about something else"]
        };
        setMessages(prev => [...prev, endMsg]);
      } else {
        setStoryState(story_data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Quick action buttons
  const QuickActions = () => (
    <div className="flex flex-wrap gap-2 justify-center mb-4">
      <button
        onClick={() => sendMessage("/quiz")}
        className="flex items-center gap-2 px-4 py-2 bg-amber-100 hover:bg-amber-200 text-amber-800 rounded-full font-semibold text-sm transition-all"
      >
        <Sparkles className="w-4 h-4" />
        Start Quiz
      </button>
      <button
        onClick={() => sendMessage("Tell me a story")}
        className="flex items-center gap-2 px-4 py-2 bg-purple-100 hover:bg-purple-200 text-purple-800 rounded-full font-semibold text-sm transition-all"
      >
        <BookOpen className="w-4 h-4" />
        Story Time
      </button>
      <button
        onClick={() => sendMessage("What can you help me learn about?")}
        className="flex items-center gap-2 px-4 py-2 bg-emerald-100 hover:bg-emerald-200 text-emerald-800 rounded-full font-semibold text-sm transition-all"
      >
        <Search className="w-4 h-4" />
        Learn Something
      </button>
    </div>
  );

  // Follow-up suggestions component
  const FollowupChips = ({ followups, onSelect }) => {
    if (!followups || followups.length === 0) return null;
    
    return (
      <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-emerald-200">
        <HelpCircle className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-1" />
        {followups.map((followup, idx) => (
          <button
            key={idx}
            onClick={() => onSelect(followup)}
            className="px-3 py-1.5 bg-white/80 hover:bg-emerald-50 text-emerald-700 rounded-full text-sm font-medium border border-emerald-200 hover:border-emerald-400 transition-all"
          >
            {followup}
          </button>
        ))}
      </div>
    );
  };

  // Quiz answer buttons
  const QuizButtons = () => {
    if (!quizState || currentMode !== "quiz") return null;
    
    if (quizState.answered) {
      return (
        <div className="flex justify-center mt-4">
          <button
            onClick={handleNextQuestion}
            className="px-6 py-3 bg-sky-500 hover:bg-sky-600 text-white rounded-full font-bold text-lg shadow-lg transition-all"
          >
            {quizState.currentQuestion + 1 >= quizState.total_questions ? "See Results! 🏆" : "Next Question →"}
          </button>
        </div>
      );
    }
    
    return (
      <div className="grid grid-cols-2 gap-3 mt-4 max-w-md mx-auto">
        {["A", "B", "C", "D"].map((opt) => (
          <button
            key={opt}
            onClick={() => handleQuizAnswer(opt)}
            className="px-6 py-4 bg-white hover:bg-sky-50 border-2 border-sky-200 hover:border-sky-400 text-sky-800 rounded-2xl font-bold text-xl transition-all shadow-sm hover:shadow-md"
          >
            {opt}
          </button>
        ))}
      </div>
    );
  };

  // Story choice buttons
  const StoryChoices = () => {
    if (!storyState || !storyState.choices || storyState.choices.length === 0) return null;
    
    return (
      <div className="space-y-2 mt-4">
        <p className="text-center text-purple-600 font-semibold text-sm">What do you want to do?</p>
        {storyState.choices.map((choice, idx) => (
          <button
            key={idx}
            onClick={() => handleStoryChoice(idx + 1)}
            disabled={loading}
            className="w-full px-5 py-3 bg-purple-100 hover:bg-purple-200 text-purple-800 rounded-xl font-medium text-left transition-all border-2 border-purple-200 hover:border-purple-400 disabled:opacity-50"
          >
            <span className="font-bold">{idx + 1}.</span> {choice}
          </button>
        ))}
      </div>
    );
  };

  return (
    <div
      data-testid="chat-page"
      className="h-screen flex bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-sky-100 via-white to-slate-50"
    >
      {/* Sidebar */}
      <aside
        data-testid="chat-sidebar"
        className={`${
          sidebarOpen ? "w-72" : "w-0"
        } transition-all duration-300 overflow-hidden bg-white/70 backdrop-blur-xl border-r border-white/40 flex flex-col`}
      >
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center gap-3 mb-5">
            <img
              src={BOT_AVATAR}
              alt="BuddyBot"
              className="w-11 h-11 rounded-full border-2 border-white shadow-md"
            />
            <h1 className="font-['Nunito'] text-2xl font-extrabold text-sky-900 tracking-tight">
              BuddyBot
            </h1>
          </div>
          <button
            data-testid="new-chat-btn"
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 bg-sky-400 hover:bg-sky-500 text-white rounded-full py-3.5 px-5 text-lg font-bold shadow-[0_4px_0_0_rgba(14,165,233,0.3)] hover:translate-y-[2px] hover:shadow-[0_2px_0_0_rgba(14,165,233,0.3)] active:translate-y-[4px] active:shadow-none transition-all duration-150"
          >
            <Plus className="w-5 h-5" strokeWidth={3} />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2">
          {conversations.map((c) => (
            <button
              key={c.id}
              data-testid={`conversation-item-${c.id}`}
              onClick={() => loadConversation(c.id)}
              className={`w-full text-left p-3.5 rounded-2xl transition-all duration-200 flex items-center gap-3 ${
                activeConvId === c.id
                  ? "bg-sky-100 text-sky-900 shadow-sm"
                  : "hover:bg-slate-100 text-slate-600"
              }`}
            >
              <MessageCircle
                className={`w-5 h-5 flex-shrink-0 ${
                  activeConvId === c.id ? "text-sky-500" : "text-slate-400"
                }`}
                strokeWidth={2.5}
              />
              <span className="truncate text-base font-medium">{c.title}</span>
              {c.has_flags && (
                <span className="ml-auto flex-shrink-0 w-2.5 h-2.5 bg-rose-400 rounded-full" />
              )}
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="text-center text-slate-400 text-base font-medium mt-8">
              No chats yet! Start one above
            </p>
          )}
        </div>

        <div className="p-4 border-t border-slate-100 space-y-2">
          {user && (
            <div className="flex items-center gap-2 p-2 text-sm text-slate-600">
              <div className="w-8 h-8 rounded-full bg-sky-100 flex items-center justify-center text-sky-600 font-bold">
                {user.name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span className="truncate font-medium">{user.name || user.email}</span>
            </div>
          )}
          <a
            href="/parent"
            data-testid="parent-dashboard-link"
            className="flex items-center gap-2.5 text-emerald-700 hover:text-emerald-800 font-semibold text-base transition-colors p-2.5 rounded-xl hover:bg-emerald-50"
          >
            <Shield className="w-5 h-5" strokeWidth={2.5} />
            Parent Dashboard
          </a>
          <button
            onClick={logout}
            className="w-full flex items-center gap-2.5 text-rose-600 hover:text-rose-700 font-semibold text-base transition-colors p-2.5 rounded-xl hover:bg-rose-50"
          >
            <LogOut className="w-5 h-5" strokeWidth={2.5} />
            Log Out
          </button>
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header
          data-testid="chat-header"
          className="flex items-center gap-4 px-6 py-4 bg-white/60 backdrop-blur-xl border-b border-white/40"
        >
          <button
            data-testid="toggle-sidebar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-500"
          >
            <ChevronLeft
              className={`w-6 h-6 transition-transform ${
                sidebarOpen ? "" : "rotate-180"
              }`}
              strokeWidth={2.5}
            />
          </button>
          <img
            src={BOT_AVATAR}
            alt="BuddyBot"
            className="w-10 h-10 rounded-full border-2 border-white shadow-sm float-animation"
          />
          <div>
            <h2 className="font-['Nunito'] text-xl font-bold text-slate-800">
              BuddyBot
              {currentMode === "quiz" && <span className="ml-2 text-amber-500">🎯 Quiz Mode</span>}
              {currentMode === "story" && <span className="ml-2 text-purple-500">📖 Story Mode</span>}
            </h2>
            <p className="text-sm font-medium text-emerald-500">
              Online and ready to chat!
            </p>
          </div>
        </header>

        {/* Messages */}
        <div
          data-testid="messages-container"
          className="flex-1 overflow-y-auto custom-scrollbar px-4 md:px-8 py-6"
        >
          <div className="max-w-3xl mx-auto space-y-5">
            {messages.length === 0 && !loading && (
              <div data-testid="empty-chat-state" className="flex flex-col items-center justify-center h-full pt-20">
                <img
                  src={BOT_AVATAR}
                  alt="BuddyBot"
                  className="w-28 h-28 rounded-full border-4 border-white shadow-lg mb-6 float-animation"
                />
                <h2 className="font-['Nunito'] text-3xl font-extrabold text-sky-900 mb-3">
                  Hi there, friend!
                </h2>
                <p className="text-lg font-medium text-slate-500 text-center max-w-md mb-6">
                  I'm BuddyBot, your friendly AI buddy! Ask me anything — I love talking about animals, space, games, and all sorts of fun stuff!
                </p>
                <QuickActions />
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={msg.id || idx}
                data-testid={`message-${msg.role}-${idx}`}
                className={`flex items-end gap-3 bubble-enter ${
                  msg.role === "user" ? "flex-row-reverse" : ""
                }`}
                style={{ animationDelay: `${idx * 0.05}s` }}
              >
                {msg.role === "assistant" && (
                  <img
                    src={BOT_AVATAR}
                    alt="BuddyBot"
                    className="w-10 h-10 rounded-full border-2 border-white shadow-sm flex-shrink-0"
                  />
                )}
                <div
                  className={`max-w-[75%] p-4 md:p-5 text-lg font-medium leading-relaxed ${
                    msg.role === "user"
                      ? "bg-sky-100 text-sky-900 rounded-[2rem] rounded-br-lg"
                      : "bg-emerald-100 text-emerald-900 rounded-[2rem] rounded-bl-lg"
                  } ${msg.blocked ? "opacity-60 line-through" : ""}`}
                >
                  <div className="whitespace-pre-wrap">{msg.text}</div>
                  {msg.blocked && (
                    <span className="block text-sm text-rose-500 font-semibold mt-2 no-underline" style={{textDecoration:'none'}}>
                      This message was filtered
                    </span>
                  )}
                  {/* Follow-up suggestions (Feature #3) */}
                  {msg.role === "assistant" && msg.followups && msg.followups.length > 0 && (
                    <FollowupChips followups={msg.followups} onSelect={handleFollowupClick} />
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="w-10 h-10 rounded-full bg-amber-200 flex items-center justify-center flex-shrink-0 border-2 border-white shadow-sm text-xl">
                    <span role="img" aria-label="child">&#x1F9D2;</span>
                  </div>
                )}
              </div>
            ))}

            {/* Quiz Answer Buttons (Feature #1) */}
            {currentMode === "quiz" && quizState && <QuizButtons />}

            {/* Story Choice Buttons (Feature #2) */}
            {currentMode === "story" && storyState && <StoryChoices />}

            {loading && (
              <div data-testid="typing-indicator" className="flex items-end gap-3 bubble-enter">
                <img
                  src={BOT_AVATAR}
                  alt="BuddyBot"
                  className="w-10 h-10 rounded-full border-2 border-white shadow-sm"
                />
                <div className="bg-emerald-100 rounded-[2rem] rounded-bl-lg p-5 flex gap-1.5">
                  <span className="typing-dot w-3 h-3 bg-emerald-400 rounded-full inline-block" />
                  <span className="typing-dot w-3 h-3 bg-emerald-400 rounded-full inline-block" />
                  <span className="typing-dot w-3 h-3 bg-emerald-400 rounded-full inline-block" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="px-4 md:px-8 pb-5 pt-3">
          {/* Quick actions when not in special mode */}
          {messages.length > 0 && currentMode === "chat" && (
            <div className="max-w-3xl mx-auto mb-3">
              <QuickActions />
            </div>
          )}
          <div
            data-testid="chat-input-area"
            className="max-w-3xl mx-auto flex items-center gap-3 bg-white rounded-full border-2 border-slate-200 p-2 pl-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] focus-within:border-sky-400 focus-within:ring-4 focus-within:ring-sky-100 transition-all"
          >
            <input
              ref={inputRef}
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                currentMode === "quiz" ? "Type your answer or ask a question..." :
                currentMode === "story" ? "Or type something to continue the story..." :
                "Type your message here..."
              }
              className="flex-1 bg-transparent outline-none text-lg font-medium text-slate-800 placeholder:text-slate-400"
              disabled={loading}
            />
            <button
              data-testid="send-message-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className="bg-sky-400 hover:bg-sky-500 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-full p-3.5 shadow-[0_4px_0_0_rgba(14,165,233,0.3)] hover:translate-y-[2px] hover:shadow-[0_2px_0_0_rgba(14,165,233,0.3)] active:translate-y-[4px] active:shadow-none disabled:shadow-none disabled:translate-y-0 transition-all duration-150"
            >
              <Send className="w-5 h-5" strokeWidth={3} />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
