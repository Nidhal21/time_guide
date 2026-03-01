import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

const ChatMessage = ({ role, content, timestamp }: ChatMessageProps) => {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex gap-3 px-4 py-6 ${isUser ? "bg-chat-user" : "bg-chat-ai"}`}
    >
      <div className="mx-auto flex w-full max-w-3xl gap-4">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
            isUser ? "gradient-primary" : "gradient-secondary"
          }`}
        >
          {isUser ? (
            <User className="h-4 w-4 text-primary-foreground" />
          ) : (
            <Bot className="h-4 w-4 text-secondary-foreground" />
          )}
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold font-display">
              {isUser ? "Vous" : "UniBot"}
            </span>
            {timestamp && (
              <span className="text-xs text-muted-foreground">{timestamp}</span>
            )}
          </div>
          <div className={`text-sm leading-relaxed whitespace-pre-wrap ${isUser ? "text-chat-user-foreground" : "text-chat-ai-foreground"}`}>
            {content}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ChatMessage;
