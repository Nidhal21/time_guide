import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import TypingIndicator from "@/components/chat/TypingIndicator";
import WelcomeScreen from "@/components/chat/WelcomeScreen";
import ChatSidebar from "@/components/chat/ChatSidebar";
import { useAuth } from "@/contexts/AuthContext";
import { getApiBaseUrl } from "@/lib/utils";
import { LogOut, MessageSquareText, ShieldCheck } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const API_URL = getApiBaseUrl();

const Chat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { user, isAdmin, signOut } = useAuth();
  const navigate = useNavigate();
  const conversationStorageKey = user ? `conversations:${user.id}` : "conversations:guest";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = async (content: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // Build history from last 3 messages
      const history = messages.slice(-3).map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          user_role: "student",
          history: history
        })
      });

      const data = await response.json();
      
      const aiMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.response,
        timestamp: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (error) {
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Erreur de connexion au serveur. Veuillez réessayer.",
        timestamp: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
  };

  const handleLoadConversation = (loadedMessages: Message[]) => {
    setMessages(loadedMessages);
  };

  const handleSignOut = async () => {
    await signOut();
    setMessages([]);
    navigate("/auth", { replace: true });
  };

  return (
    <div className="relative flex h-screen overflow-hidden bg-[linear-gradient(180deg,#f8fafc_0%,#eef4fb_48%,#f8fafc_100%)]">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-8rem] top-[-7rem] h-72 w-72 rounded-full bg-orange-200/35 blur-3xl" />
        <div className="absolute right-[-6rem] top-20 h-80 w-80 rounded-full bg-sky-200/35 blur-3xl" />
        <div className="absolute bottom-[-10rem] left-1/3 h-80 w-80 rounded-full bg-amber-100/60 blur-3xl" />
      </div>

      <ChatSidebar 
        isOpen={sidebarOpen} 
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        currentMessages={messages}
        onNewChat={handleNewChat}
        onLoadConversation={handleLoadConversation}
        storageKey={conversationStorageKey}
      />

      <div className="relative z-10 flex flex-1 flex-col">
        {/* Header */}
        <header className="border-b border-slate-200/70 bg-white/80 px-4 py-3 backdrop-blur xl:px-6">
          <div className="mx-auto flex w-full max-w-5xl items-center gap-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-xl p-2 text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground lg:hidden"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl gradient-hero shadow-glow-primary">
              <svg className="h-4 w-4 text-primary-foreground" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <h2 className="text-sm font-semibold font-display text-foreground sm:text-base">Enet'Bot</h2>
              <p className="text-xs text-slate-500">Conversation universitaire ENET'Com</p>
            </div>
          </div>
          <div className="ml-2 hidden items-center gap-2 rounded-full border border-slate-200 bg-white/75 px-3 py-1.5 text-xs text-slate-600 shadow-sm md:flex">
            <MessageSquareText className="h-3.5 w-3.5 text-sky-600" />
            Posez vos questions sur les classes, salles, enseignants et calendrier
          </div>
          <div className="ml-auto flex items-center gap-2">
            {isAdmin && (
              <Link
                to="/admin"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-foreground shadow-sm transition-colors hover:bg-slate-50"
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                Espace admin
              </Link>
            )}
            {user ? (
              <button
                onClick={handleSignOut}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-foreground shadow-sm transition-colors hover:bg-slate-50"
              >
                <LogOut className="h-3.5 w-3.5" />
                Deconnexion
              </button>
            ) : (
              <Link
                to="/auth"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-foreground shadow-sm transition-colors hover:bg-slate-50"
              >
                Connexion
              </Link>
            )}
          </div>
          </div>
        </header>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-4 chat-scrollbar sm:px-5 lg:px-8">
          <div className="mx-auto flex min-h-full w-full max-w-5xl flex-col">
            {messages.length === 0 ? (
              <WelcomeScreen onSuggestionClick={handleSend} />
            ) : (
              <div className="flex flex-1 flex-col gap-4 pb-4 pt-2">
                {messages.map((msg) => (
                  <ChatMessage key={msg.id} role={msg.role} content={msg.content} timestamp={msg.timestamp} />
                ))}
                {isLoading && <TypingIndicator />}
              </div>
            )}
          </div>
        </div>

        {/* Input */}
        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );
};

export default Chat;
