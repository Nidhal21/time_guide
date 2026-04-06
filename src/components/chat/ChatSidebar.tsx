import { motion, AnimatePresence } from "framer-motion";
import { Plus, MessageSquare, X, Trash2 } from "lucide-react";
import { useState, useEffect, useRef } from "react";

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  currentMessages: any[];
  onNewChat: () => void;
  onLoadConversation: (messages: any[]) => void;
  storageKey: string;
}

interface Conversation {
  id: string;
  title: string;
  date: string;
  messages: any[];
}

const ChatSidebar = ({ isOpen, onToggle, currentMessages, onNewChat, onLoadConversation, storageKey }: ChatSidebarProps) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const currentConversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    currentConversationIdRef.current = null;
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      setConversations(JSON.parse(saved));
    } else {
      setConversations([]);
    }
  }, [storageKey]);

  useEffect(() => {
    if (currentMessages.length === 0) {
      currentConversationIdRef.current = null;
      return;
    }

    if (currentMessages.length > 0) {
      const title = currentMessages[0]?.content.substring(0, 30) + '...' || 'Nouvelle conversation';
      const convId = currentConversationIdRef.current ?? Date.now().toString();
      currentConversationIdRef.current = convId;

      const newConv: Conversation = {
        id: convId,
        title,
        date: new Date().toLocaleDateString('fr-FR'),
        messages: currentMessages
      };

      setConversations((prev) => {
        const existingIndex = prev.findIndex((c) => c.id === convId);
        const next = [...prev];

        if (existingIndex >= 0) {
          next[existingIndex] = newConv;
        } else {
          next.unshift(newConv);
        }

        const sliced = next.slice(0, 10);
        localStorage.setItem(storageKey, JSON.stringify(sliced));
        return sliced;
      });
    }
  }, [currentMessages, storageKey]);

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = conversations.filter(c => c.id !== id);
    setConversations(updated);
    localStorage.setItem(storageKey, JSON.stringify(updated));
  };

  const handleNewChat = () => {
    onNewChat();
    if (window.innerWidth < 1024) {
      onToggle();
    }
  };

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
            className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm lg:hidden"
          />
        )}
      </AnimatePresence>

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-border bg-card transition-transform duration-300 lg:static lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <h3 className="font-display text-sm font-semibold text-foreground">Conversations</h3>
          <div className="flex gap-1">
            <button 
              onClick={handleNewChat}
              className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title="Nouvelle conversation"
            >
              <Plus className="h-4 w-4" />
            </button>
            <button
              onClick={onToggle}
              className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:hidden"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 chat-scrollbar">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Aucune conversation
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className="group relative flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted"
              >
                <button
                  onClick={() => {
                    onLoadConversation(conv.messages);
                    if (window.innerWidth < 1024) onToggle();
                  }}
                  className="flex flex-1 items-center gap-3 min-w-0"
                >
                  <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-foreground">{conv.title}</p>
                    <p className="text-xs text-muted-foreground">{conv.date}</p>
                  </div>
                </button>
                <button
                  onClick={(e) => handleDelete(conv.id, e)}
                  className="opacity-0 group-hover:opacity-100 rounded p-1 text-muted-foreground hover:text-destructive transition-opacity"
                  title="Supprimer"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>
    </>
  );
};

export default ChatSidebar;
